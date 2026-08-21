"""Manual BRAPI opportunity-rule calibration command.

Example:
    python -m app.calibrate_opportunity --history-days 730 --max-assets 5

The command is read-only against Supabase and never sends Telegram messages,
calls Gemini, changes GitHub variables, or executes trades.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.backtesting.calibration import (
    CalibrationConfig,
    build_observation_partitions,
    calibrate_partitions,
    result_to_dict,
)
from app.config.settings import get_settings
from app.database.client import create_supabase_client
from app.database.repositories import ProviderSymbolRepository
from app.market_data.contracts import HistoryRequest
from app.market_data.http import ProviderHttpClient
from app.market_data.models import CandleInterval
from app.market_data.providers.brapi import BrapiProvider


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
    if args.history_days < 180:
        raise SystemExit("--history-days deve ser >= 180")
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
    start = end - timedelta(days=args.history_days)
    candles_by_asset = {}

    try:
        for mapping in mappings:
            try:
                candles = provider.get_history(
                    HistoryRequest(
                        asset_id=mapping.asset_id,
                        provider_symbol=mapping.provider_symbol,
                        interval=CandleInterval.ONE_DAY,
                        start=start,
                        end=end,
                    )
                )
            except Exception as exc:
                print(
                    f"SKIP {mapping.provider_symbol}: "
                    f"{exc.__class__.__name__}"
                )
                continue
            if candles:
                candles_by_asset[mapping.asset_id] = tuple(candles)
                print(
                    f"OK {mapping.provider_symbol}: "
                    f"{len(candles)} candles"
                )
    finally:
        provider.close()

    if not candles_by_asset:
        raise SystemExit("Nenhum histórico BRAPI pôde ser carregado")

    partitions = build_observation_partitions(
        candles_by_asset,
        config=config,
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
