"""Audit-first lifecycle for calibrated opportunity policies.

This module deliberately has no provider, Telegram, Gemini, broker, or database
client dependency.  It evaluates an already frozen deterministic policy and
keeps historical calibration separate from future shadow evidence.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from random import Random
from uuid import UUID

from app.backtesting.calibration import CalibrationObservation
from app.market_data.models import DataQuality
from app.opportunity import OpportunityEngine, OpportunityLevel, OpportunityPolicy


ZERO = Decimal("0")
HALF = Decimal("0.5")
_CONFIDENCE_LOW = Decimal("0.025")
_CONFIDENCE_HIGH = Decimal("0.975")


@dataclass(frozen=True, slots=True)
class ReturnStats:
    observations: int
    signals: int
    positive_outcomes: int
    gross_hit_rate: Decimal
    gross_average_forward_return: Decimal
    gross_best_forward_return: Decimal
    gross_worst_forward_return: Decimal
    net_hit_rate: Decimal
    net_average_forward_return: Decimal
    net_best_forward_return: Decimal
    net_worst_forward_return: Decimal


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    low: Decimal
    high: Decimal


@dataclass(frozen=True, slots=True)
class BootstrapSummary:
    seed: int
    samples: int
    hit_rate: ConfidenceInterval
    average_forward_return: ConfidenceInterval
    net_average_forward_return: ConfidenceInterval


@dataclass(frozen=True, slots=True)
class RobustnessReport:
    round_trip_cost_bps: Decimal
    cost_per_signal: Decimal
    overall: ReturnStats
    by_asset: dict[UUID, ReturnStats]
    signals_by_asset: dict[UUID, int]
    signal_share_by_asset: dict[UUID, Decimal]
    max_asset_signal_share: Decimal
    top_3_assets_by_signals: tuple[tuple[UUID, int], ...]
    signals_by_month: dict[str, int]
    positive_signals_by_month: dict[str, int]
    average_return_by_month: dict[str, Decimal]
    bootstrap: BootstrapSummary


@dataclass(frozen=True, slots=True)
class FutureEvidence:
    signals: int
    positive_outcomes: int
    gross_hit_rate: Decimal
    gross_average_return: Decimal
    net_average_return: Decimal
    first_prediction_at: datetime | None
    last_realized_at: datetime | None
    assets: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class ProductionGatePolicy:
    """Explicit future-evidence requirements, independent from calibration."""

    min_future_signals: int = 20
    minimum_hit_rate: Decimal = HALF

    def __post_init__(self) -> None:
        if isinstance(self.min_future_signals, bool) or self.min_future_signals <= 0:
            raise ValueError("min_future_signals deve ser inteiro positivo")
        if not ZERO <= self.minimum_hit_rate <= Decimal("1"):
            raise ValueError("minimum_hit_rate deve estar entre 0 e 1")


def policy_signal_observations(
    observations: tuple[CalibrationObservation, ...],
    *,
    policy: OpportunityPolicy,
) -> tuple[CalibrationObservation, ...]:
    """Return only signals produced by a fixed policy; never select rules."""

    engine = OpportunityEngine(policy)
    signals: list[CalibrationObservation] = []
    for observation in observations:
        assessment = engine.assess(
            metrics=observation.metric_map(),
            price_quality=DataQuality.VALID,
            reference_at=observation.signal_at,
            evaluated_at=observation.signal_at,
            ai_positive=False,
        )
        if assessment.level in (OpportunityLevel.INTERESTING, OpportunityLevel.HIGH_INTEREST):
            signals.append(observation)
    return tuple(signals)


def build_robustness_report(
    observations: tuple[CalibrationObservation, ...],
    *,
    policy: OpportunityPolicy,
    round_trip_cost_bps: Decimal = Decimal("20"),
    bootstrap_seed: int = 0,
    bootstrap_samples: int = 1_000,
) -> RobustnessReport:
    """Evaluate a frozen policy without mutating candles or thresholds."""

    _validate_cost(round_trip_cost_bps)
    _validate_bootstrap(bootstrap_seed, bootstrap_samples)
    cost = round_trip_cost_bps / Decimal("10000")
    signals = policy_signal_observations(observations, policy=policy)
    by_asset: dict[UUID, tuple[CalibrationObservation, ...]] = {}
    grouped: dict[UUID, list[CalibrationObservation]] = defaultdict(list)
    for observation in signals:
        grouped[observation.asset_id].append(observation)
    for asset_id, asset_signals in grouped.items():
        by_asset[asset_id] = tuple(asset_signals)

    counts = {asset_id: len(items) for asset_id, items in by_asset.items()}
    total = len(signals)
    shares = {
        asset_id: Decimal(count) / Decimal(total) if total else ZERO
        for asset_id, count in counts.items()
    }
    months: dict[str, list[CalibrationObservation]] = defaultdict(list)
    for observation in signals:
        months[observation.signal_at.astimezone(UTC).strftime("%Y-%m")].append(observation)

    return RobustnessReport(
        round_trip_cost_bps=round_trip_cost_bps,
        cost_per_signal=cost,
        overall=_return_stats(tuple(observations), signals, cost=cost),
        by_asset={
            asset_id: _return_stats(
                tuple(item for item in observations if item.asset_id == asset_id),
                asset_signals,
                cost=cost,
            )
            for asset_id, asset_signals in by_asset.items()
        },
        signals_by_asset=counts,
        signal_share_by_asset=shares,
        max_asset_signal_share=max(shares.values(), default=ZERO),
        top_3_assets_by_signals=tuple(
            sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))[:3]
        ),
        signals_by_month={month: len(items) for month, items in sorted(months.items())},
        positive_signals_by_month={
            month: sum(item.forward_return > ZERO for item in items)
            for month, items in sorted(months.items())
        },
        average_return_by_month={
            month: sum((item.forward_return for item in items), ZERO) / Decimal(len(items))
            for month, items in sorted(months.items())
        },
        bootstrap=_bootstrap(signals, cost=cost, seed=bootstrap_seed, samples=bootstrap_samples),
    )


def future_evidence_from_realized(predictions: tuple[object, ...]) -> FutureEvidence:
    """Summarise only predictions that already have a persisted realized outcome."""

    realized = tuple(item for item in predictions if getattr(item, "realized_at", None) is not None)
    returns = tuple(getattr(item, "gross_return") for item in realized)
    net_returns = tuple(getattr(item, "net_return") for item in realized)
    return FutureEvidence(
        signals=len(realized),
        positive_outcomes=sum(item > ZERO for item in returns),
        gross_hit_rate=(Decimal(sum(item > ZERO for item in returns)) / Decimal(len(returns)) if returns else ZERO),
        gross_average_return=(sum(returns, ZERO) / Decimal(len(returns)) if returns else ZERO),
        net_average_return=(sum(net_returns, ZERO) / Decimal(len(net_returns)) if net_returns else ZERO),
        first_prediction_at=min((getattr(item, "predicted_at") for item in realized), default=None),
        last_realized_at=max((getattr(item, "realized_at") for item in realized), default=None),
        assets=tuple(sorted({getattr(item, "asset_id") for item in realized}, key=str)),
    )


def production_ready(
    *,
    calibration_release_ready: bool,
    policy_active: bool,
    evidence: FutureEvidence,
    gate: ProductionGatePolicy = ProductionGatePolicy(),
) -> bool:
    """Return policy readiness from evidence, independent of operator enablement.

    ``AUTOMATION_ENABLED`` is deliberately not an input: it is an operational
    switch, never statistical evidence.  Alert execution must still require it
    separately.
    """

    return bool(
        calibration_release_ready
        and policy_active
        and evidence.signals >= gate.min_future_signals
        and evidence.gross_hit_rate >= gate.minimum_hit_rate
        and evidence.net_average_return > ZERO
    )


def _return_stats(
    observations: tuple[CalibrationObservation, ...],
    signals: tuple[CalibrationObservation, ...],
    *,
    cost: Decimal,
) -> ReturnStats:
    gross = tuple(item.forward_return for item in signals)
    net = tuple(item - cost for item in gross)
    count = len(gross)
    return ReturnStats(
        observations=len(observations),
        signals=count,
        positive_outcomes=sum(item > ZERO for item in gross),
        gross_hit_rate=Decimal(sum(item > ZERO for item in gross)) / Decimal(count) if count else ZERO,
        gross_average_forward_return=sum(gross, ZERO) / Decimal(count) if count else ZERO,
        gross_best_forward_return=max(gross, default=ZERO),
        gross_worst_forward_return=min(gross, default=ZERO),
        net_hit_rate=Decimal(sum(item > ZERO for item in net)) / Decimal(count) if count else ZERO,
        net_average_forward_return=sum(net, ZERO) / Decimal(count) if count else ZERO,
        net_best_forward_return=max(net, default=ZERO),
        net_worst_forward_return=min(net, default=ZERO),
    )


def _bootstrap(
    signals: tuple[CalibrationObservation, ...], *, cost: Decimal, seed: int, samples: int
) -> BootstrapSummary:
    if not signals:
        zero = ConfidenceInterval(ZERO, ZERO)
        return BootstrapSummary(seed, samples, zero, zero, zero)
    random = Random(seed)
    hit_rates: list[Decimal] = []
    averages: list[Decimal] = []
    net_averages: list[Decimal] = []
    for _ in range(samples):
        returns = [signals[random.randrange(len(signals))].forward_return for _ in signals]
        hit_rates.append(Decimal(sum(item > ZERO for item in returns)) / Decimal(len(returns)))
        average = sum(returns, ZERO) / Decimal(len(returns))
        averages.append(average)
        net_averages.append(average - cost)
    return BootstrapSummary(
        seed,
        samples,
        _interval(hit_rates),
        _interval(averages),
        _interval(net_averages),
    )


def _interval(values: list[Decimal]) -> ConfidenceInterval:
    ordered = sorted(values)
    return ConfidenceInterval(
        ordered[int(Decimal(len(ordered) - 1) * _CONFIDENCE_LOW)],
        ordered[int(Decimal(len(ordered) - 1) * _CONFIDENCE_HIGH)],
    )


def _validate_cost(cost: Decimal) -> None:
    if not isinstance(cost, Decimal) or not cost.is_finite() or cost < ZERO:
        raise ValueError("round_trip_cost_bps deve ser Decimal finito não negativo")


def _validate_bootstrap(seed: int, samples: int) -> None:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("bootstrap_seed deve ser inteiro")
    if isinstance(samples, bool) or not isinstance(samples, int) or samples <= 0:
        raise ValueError("bootstrap_samples deve ser inteiro positivo")
