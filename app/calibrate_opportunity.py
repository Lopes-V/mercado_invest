"""Manual BRAPI opportunity-rule calibration command.

Example:
    python -m app.calibrate_opportunity --history-days 730 --max-assets 5

The command is read-only against Supabase and never sends Telegram messages,
calls Gemini, changes GitHub variables, or executes trades.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Mapping
from uuid import UUID

from app.backtesting.calibration import (
    CalibrationConfig,
    ObservationPartitions,
    build_observation_partitions,
    calibrate_partitions,
    result_to_dict,
)
from app.config.settings import get_settings
from app.database.client import create_supabase_client
from app.database.repositories import ProviderSymbolRepository
from app.market_data.contracts import HistoryRequest
from app.market_data.errors import ProviderError, ProviderHttpError
from app.market_data.http import ProviderHttpClient
from app.market_data.models import Candle, CandleInterval
from app.market_data.providers.brapi import BrapiProvider


_HISTORY_FALLBACK_DAYS = (365, 180, 90, 30)
_BRAPI_WINDOW_LIMIT_CODES = frozenset({"INVALID_RANGE", "DATE_WINDOW_EXCEEDED"})


class CalibrationHistoryError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class LoadedHistory:
    candles: tuple[Candle, ...]
    requested_days: int
    loaded_window_days: int
    fallback_code: str | None


def history_window_candidates(requested_days: int) -> tuple[int, ...]:
    if isinstance(requested_days, bool) or not isinstance(requested_days, int):
        raise ValueError("history_days deve ser inteiro")
    if requested_days <= 0:
        raise ValueError("history_days deve ser positivo")
    return tuple(
        dict.fromkeys(
            (requested_days,)
            + tuple(days for days in _HISTORY_FALLBACK_DAYS if days < requested_days)
        )
    )


def load_brapi_history_with_fallback(
    provider: BrapiProvider,
    *,
    asset_id: UUID,
    provider_symbol: str,
    end: datetime,
    history_days: int,
) -> LoadedHistory:
    """Load the largest requested BRAPI window accepted for this asset/plan.

    Only BRAPI's explicit range-limit codes may shorten the requested window.
    Authentication, rate-limit and malformed-response failures remain visible
    to the caller and never become a synthetic history.
    """

    candidates = history_window_candidates(history_days)
    fallback_code: str | None = None
    for window_days in candidates:
        try:
            candles = tuple(
                provider.get_history(
                    HistoryRequest(
                        asset_id=asset_id,
                        provider_symbol=provider_symbol,
                        interval=CandleInterval.ONE_DAY,
                        start=end - timedelta(days=window_days),
                        end=end,
                    )
                )
            )
        except ProviderHttpError as exc:
            if (
                exc.status_code == 400
                and exc.provider_code in _BRAPI_WINDOW_LIMIT_CODES
                and window_days != candidates[-1]
            ):
                fallback_code = exc.provider_code
                continue
            raise
        if not candles:
            raise CalibrationHistoryError("EMPTY_HISTORY")
        return LoadedHistory(
            candles=candles,
            requested_days=history_days,
            loaded_window_days=window_days,
            fallback_code=fallback_code,
        )
    raise CalibrationHistoryError("HISTORY_WINDOW_UNAVAILABLE")


def format_history_failure(symbol: str, exc: Exception) -> str:
    """Return an operational diagnostic without response body, URL, or token."""

    status = "none"
    code = "UNSPECIFIED"
    if isinstance(exc, ProviderHttpError):
        status = str(exc.status_code)
        code = exc.provider_code or code
    elif isinstance(exc, CalibrationHistoryError):
        code = exc.code
    return (
        f"SKIP {symbol}: status={status} type={type(exc).__name__} code={code}"
    )


def partition_report(
    partitions: ObservationPartitions,
    *,
    symbols_by_asset: Mapping[UUID, str],
) -> dict[str, object]:
    """Create an audit-friendly report for the shared chronological split."""

    def iso(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    def describe(items: tuple) -> dict[str, object]:
        counts: dict[str, int] = {}
        for item in items:
            symbol = symbols_by_asset.get(item.asset_id, str(item.asset_id))
            counts[symbol] = counts.get(symbol, 0) + 1
        return {
            "observations": len(items),
            "contributing_assets": len(counts),
            "observations_by_asset": dict(sorted(counts.items())),
            "first_signal_at": iso(min((item.signal_at for item in items), default=None)),
            "last_signal_at": iso(max((item.signal_at for item in items), default=None)),
            "first_outcome_at": iso(min((item.outcome_at for item in items), default=None)),
            "last_outcome_at": iso(max((item.outcome_at for item in items), default=None)),
        }

    return {
        "global_train_end": iso(partitions.global_train_end),
        "global_validation_end": iso(partitions.global_validation_end),
        "train": describe(partitions.train),
        "validation": describe(partitions.validation),
        "test": describe(partitions.test),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calibra regras de oportunidade em walk-forward com holdout final."
    )
    parser.add_argument("--history-days", type=int, default=730)
    parser.add_argument("--analysis-lookback-days", type=int, default=30)
    parser.add_argument("--analysis-period", type=int, default=14)
    parser.add_argument("--forward-horizon", type=int, default=5)
    parser.add_argument("--train-ratio", default="0.60")
    parser.add_argument("--validation-ratio", default="0.20")
    parser.add_argument("--min-signals", type=int, default=8)
    parser.add_argument("--max-assets", type=int, default=5)
    parser.add_argument(
        "--symbols",
        default="",
        help="Provider symbols separados por vírgula. Vazio usa mappings ativos.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Arquivo JSON opcional para relatório. Vazio imprime somente stdout.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.history_days < 90:
        raise SystemExit("--history-days deve ser >= 90")
    if args.max_assets <= 0:
        raise SystemExit("--max-assets deve ser positivo")

    config = CalibrationConfig(
        analysis_lookback_days=args.analysis_lookback_days,
        analysis_period=args.analysis_period,
        forward_horizon=args.forward_horizon,
        train_ratio=Decimal(args.train_ratio),
        validation_ratio=Decimal(args.validation_ratio),
        min_signals=args.min_signals,
    )

    settings = get_settings()
    client = create_supabase_client(settings)
    mappings = ProviderSymbolRepository(client).list_active_by_provider("brapi")

    requested = {
        item.strip().upper()
        for item in args.symbols.split(",")
        if item.strip()
    }
    if requested:
        mappings = tuple(
            item
            for item in mappings
            if item.provider_symbol.upper() in requested
        )
        missing = requested - {item.provider_symbol.upper() for item in mappings}
        if missing:
            raise SystemExit(
                "Symbols sem mapping BRAPI ativo: " + ",".join(sorted(missing))
            )

    mappings = mappings[: args.max_assets]
    if not mappings:
        raise SystemExit("Nenhum mapping BRAPI ativo disponível para calibração")

    http = ProviderHttpClient(base_url="https://brapi.dev", timeout_seconds=20)
    provider = BrapiProvider(http, token=settings.brapi_token)
    end = datetime.now(UTC)
    candles_by_asset: dict[UUID, tuple[Candle, ...]] = {}
    symbols_by_asset: dict[UUID, str] = {}
    history_by_symbol: dict[str, dict[str, int | str | None]] = {}

    try:
        for mapping in mappings:
            try:
                loaded = load_brapi_history_with_fallback(
                    provider,
                    asset_id=mapping.asset_id,
                    provider_symbol=mapping.provider_symbol,
                    end=end,
                    history_days=args.history_days,
                )
            except (ProviderError, CalibrationHistoryError) as exc:
                print(format_history_failure(mapping.provider_symbol, exc))
                continue
            candles_by_asset[mapping.asset_id] = loaded.candles
            symbols_by_asset[mapping.asset_id] = mapping.provider_symbol
            history_by_symbol[mapping.provider_symbol] = {
                "requested_days": loaded.requested_days,
                "loaded_window_days": loaded.loaded_window_days,
                "candles": len(loaded.candles),
                "fallback_code": loaded.fallback_code,
            }
            fallback_note = (
                f" (fallback {loaded.fallback_code})"
                if loaded.loaded_window_days < loaded.requested_days
                else ""
            )
            print(
                f"OK {mapping.provider_symbol}: {len(loaded.candles)} candles "
                f"window_days={loaded.loaded_window_days}{fallback_note}"
            )
    finally:
        provider.close()

    if not candles_by_asset:
        raise SystemExit("Nenhum histórico BRAPI pôde ser carregado")

    partitions = build_observation_partitions(
        candles_by_asset,
        config=config,
    )
    if not (partitions.train and partitions.validation and partitions.test):
        raise SystemExit(
            "Amostra histórica global insuficiente para treino, validação e holdout"
        )
    result = calibrate_partitions(partitions, config=config)
    report = {
        "methodology": {
            "provider": "brapi",
            "history_days": args.history_days,
            "analysis_lookback_days": config.analysis_lookback_days,
            "analysis_period": config.analysis_period,
            "forward_horizon_candles": config.forward_horizon,
            "train_ratio": str(config.train_ratio),
            "validation_ratio": str(config.validation_ratio),
            "test_ratio": str(
                Decimal("1") - config.train_ratio - config.validation_ratio
            ),
            "min_signals_per_partition": config.min_signals,
            "ai_used": False,
            "telegram_used": False,
            "trading_used": False,
            "history_by_symbol": history_by_symbol,
            "global_partitions": partition_report(
                partitions,
                symbols_by_asset=symbols_by_asset,
            ),
        },
        "result": result_to_dict(result),
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.output:
        output = Path(args.output)
        output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Relatório salvo em: {output}")

    if result.release_ready:
        print("\nRELEASE_READY=true")
        print("OPPORTUNITY_RULES_JSON=" + (result.rules_json() or ""))
    else:
        print("\nRELEASE_READY=false")
        print(
            "Evidência holdout insuficiente. "
            "Não substitua OPPORTUNITY_RULES_JSON."
        )


if __name__ == "__main__":
    main()
