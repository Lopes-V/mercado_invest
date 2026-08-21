"""Deterministic walk-forward calibration for opportunity rules.

Training observations derive candidate thresholds. Validation observations select
one candidate. The final test partition is used only once, after selection, as a
holdout gate. No AI, Telegram, trading, persistence, or secret mutation occurs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import combinations
from typing import Iterable, Mapping
from uuid import UUID

from app.analysis import AnalysisEngine
from app.market_data.models import Candle, DataQuality
from app.opportunity import (
    EvidenceCategory,
    MetricOperator,
    MetricRule,
    OpportunityEngine,
    OpportunityLevel,
    OpportunityPolicy,
)


ZERO = Decimal("0")
HALF = Decimal("0.5")


@dataclass(frozen=True, slots=True)
class CalibrationConfig:
    analysis_lookback_days: int = 30
    analysis_period: int = 14
    forward_horizon: int = 5
    train_ratio: Decimal = Decimal("0.60")
    validation_ratio: Decimal = Decimal("0.20")
    min_signals: int = 8
    rule_weight: Decimal = Decimal("20")

    def __post_init__(self) -> None:
        for field in (
            "analysis_lookback_days",
            "analysis_period",
            "forward_horizon",
            "min_signals",
        ):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{field} deve ser inteiro positivo")

        for field in ("train_ratio", "validation_ratio", "rule_weight"):
            value = getattr(self, field)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ValueError(f"{field} deve ser Decimal finito")

        if not ZERO < self.train_ratio < Decimal("1"):
            raise ValueError("train_ratio deve estar entre 0 e 1")
        if not ZERO < self.validation_ratio < Decimal("1"):
            raise ValueError("validation_ratio deve estar entre 0 e 1")
        if self.train_ratio + self.validation_ratio >= Decimal("1"):
            raise ValueError("train_ratio + validation_ratio deve deixar holdout de teste")
        if not ZERO < self.rule_weight <= Decimal("100"):
            raise ValueError("rule_weight deve estar entre 0 e 100")


@dataclass(frozen=True, slots=True)
class CalibrationObservation:
    asset_id: UUID
    signal_at: datetime
    outcome_at: datetime
    metrics: tuple[tuple[str, Decimal], ...]
    forward_return: Decimal

    def __post_init__(self) -> None:
        if self.signal_at.tzinfo is None or self.outcome_at.tzinfo is None:
            raise ValueError("timestamps de observation devem possuir timezone")
        if self.outcome_at <= self.signal_at:
            raise ValueError("outcome_at deve ser posterior a signal_at")
        if not isinstance(self.forward_return, Decimal) or not self.forward_return.is_finite():
            raise ValueError("forward_return deve ser Decimal finito")
        names: set[str] = set()
        for name, value in self.metrics:
            if not isinstance(name, str) or not name.strip():
                raise ValueError("metric name inválido")
            if name in names:
                raise ValueError("metric names duplicados")
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ValueError("metric value deve ser Decimal finito")
            names.add(name)

    def metric_map(self) -> dict[str, Decimal]:
        return dict(self.metrics)


@dataclass(frozen=True, slots=True)
class CandidateStats:
    signals: int
    positive_outcomes: int
    hit_rate: Decimal
    average_forward_return: Decimal
    best_forward_return: Decimal
    worst_forward_return: Decimal


@dataclass(frozen=True, slots=True)
class CalibrationCandidate:
    rules: tuple[MetricRule, MetricRule]
    train: CandidateStats
    validation: CandidateStats


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    train_observations: int
    validation_observations: int
    test_observations: int
    generated_candidates: int
    qualified_candidates: int
    selected: CalibrationCandidate | None
    test: CandidateStats | None
    release_ready: bool

    def rules_json(self) -> str | None:
        if not self.release_ready or self.selected is None:
            return None
        return rules_to_json(self.selected.rules)


@dataclass(frozen=True, slots=True)
class ObservationPartitions:
    train: tuple[CalibrationObservation, ...]
    validation: tuple[CalibrationObservation, ...]
    test: tuple[CalibrationObservation, ...]
    global_train_end: datetime | None = None
    global_validation_end: datetime | None = None


@dataclass(frozen=True, slots=True)
class _Blueprint:
    metric_name: str
    operator: MetricOperator
    evidence_category: EvidenceCategory
    quantiles: tuple[Decimal, ...]


_BLUEPRINTS = (
    _Blueprint(
        "RETURN",
        MetricOperator.GT,
        EvidenceCategory.TREND,
        (Decimal("0.60"), Decimal("0.70")),
    ),
    _Blueprint(
        "RETURN",
        MetricOperator.LT,
        EvidenceCategory.TREND,
        (Decimal("0.30"), Decimal("0.40")),
    ),
    _Blueprint(
        "RSI",
        MetricOperator.GT,
        EvidenceCategory.MOMENTUM,
        (Decimal("0.60"), Decimal("0.70")),
    ),
    _Blueprint(
        "RSI",
        MetricOperator.LT,
        EvidenceCategory.MOMENTUM,
        (Decimal("0.30"), Decimal("0.40")),
    ),
    _Blueprint(
        "VOLATILITY",
        MetricOperator.LT,
        EvidenceCategory.RISK,
        (Decimal("0.30"), Decimal("0.40"), Decimal("0.50")),
    ),
    _Blueprint(
        "MAX_DRAWDOWN",
        MetricOperator.LT,
        EvidenceCategory.RISK,
        (Decimal("0.30"), Decimal("0.40"), Decimal("0.50")),
    ),
)


def prepare_historical_candles(candles: Iterable[Candle]) -> tuple[Candle, ...]:
    """Mark provider-normalized historical observations as replay-valid.

    This does not assert that an old candle is fresh *today*. It means the
    structurally validated historical observation is eligible for historical
    replay at its own timestamp. Current-data freshness remains the live
    QualityEngine's responsibility.
    """

    ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
    seen: set[datetime] = set()
    prepared: list[Candle] = []

    for candle in ordered:
        if candle.timestamp in seen:
            raise ValueError("histórico possui timestamps duplicados")
        seen.add(candle.timestamp)
        if min(candle.open, candle.high, candle.low, candle.close) <= ZERO:
            raise ValueError("backtest exige OHLC estritamente positivo")
        prepared.append(
            Candle(
                asset_id=candle.asset_id,
                provider_symbol=candle.provider_symbol,
                timestamp=candle.timestamp,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                interval=candle.interval,
                provider=candle.provider,
                received_at=candle.received_at,
                quality=DataQuality.VALID,
                adjusted_close=candle.adjusted_close,
            )
        )

    return tuple(prepared)


def build_observation_partitions(
    candles_by_asset: Mapping[UUID, Iterable[Candle]],
    *,
    config: CalibrationConfig,
    engine: AnalysisEngine | None = None,
) -> ObservationPartitions:
    """Build partitions from shared global chronological cutoffs.

    The cutoffs are derived from the sorted, distinct candle timestamps across
    every eligible asset.  An asset with a shorter provider window may therefore
    contribute only to the final holdout; it is never assigned an artificial
    per-asset training period that overlaps another asset's global holdout.
    """

    analysis_engine = engine or AnalysisEngine()
    train: list[CalibrationObservation] = []
    validation: list[CalibrationObservation] = []
    test: list[CalibrationObservation] = []

    minimum_candles = config.analysis_period + config.forward_horizon + 3
    prepared_by_asset = {}
    for asset_id, raw_candles in candles_by_asset.items():
        candles = prepare_historical_candles(raw_candles)
        if len(candles) >= minimum_candles:
            prepared_by_asset[asset_id] = candles
    dates = tuple(
        sorted(
            {
                candle.timestamp
                for candles in prepared_by_asset.values()
                for candle in candles
            }
        )
    )
    if not dates:
        return ObservationPartitions((), (), ())

    train_end = _global_cutoff(dates, config.train_ratio)
    validation_end = _global_cutoff(
        dates,
        config.train_ratio + config.validation_ratio,
    )

    for asset_id, candles in prepared_by_asset.items():
        observations = _asset_observations(
            candles,
            asset_id=asset_id,
            config=config,
            engine=analysis_engine,
        )
        for observation in observations:
            if observation.signal_at <= train_end and observation.outcome_at <= train_end:
                train.append(observation)
            elif (
                observation.signal_at > train_end
                and observation.signal_at <= validation_end
                and observation.outcome_at <= validation_end
            ):
                validation.append(observation)
            elif observation.signal_at > validation_end:
                test.append(observation)

    return ObservationPartitions(
        train=tuple(sorted(train, key=lambda item: (item.signal_at, str(item.asset_id)))),
        validation=tuple(
            sorted(validation, key=lambda item: (item.signal_at, str(item.asset_id)))
        ),
        test=tuple(sorted(test, key=lambda item: (item.signal_at, str(item.asset_id)))),
        global_train_end=train_end,
        global_validation_end=validation_end,
    )


def _global_cutoff(dates: tuple[datetime, ...], ratio: Decimal) -> datetime:
    """Return a chronological global cutoff using the common date timeline."""

    return dates[int(Decimal(len(dates) - 1) * ratio)]


def _asset_observations(
    candles: tuple[Candle, ...],
    *,
    asset_id: UUID,
    config: CalibrationConfig,
    engine: AnalysisEngine,
) -> list[CalibrationObservation]:
    observations: list[CalibrationObservation] = []

    for index in range(config.analysis_period - 1, len(candles) - config.forward_horizon):
        signal_candle = candles[index]
        window_start = signal_candle.timestamp - timedelta(
            days=config.analysis_lookback_days
        )
        window = tuple(
            item
            for item in candles[: index + 1]
            if item.timestamp >= window_start
        )
        if len(window) < config.analysis_period:
            continue

        result = engine.analyze(window, period=config.analysis_period)
        outcome = candles[index + config.forward_horizon]
        forward_return = (outcome.close - signal_candle.close) / signal_candle.close
        observations.append(
            CalibrationObservation(
                asset_id=asset_id,
                signal_at=signal_candle.timestamp,
                outcome_at=outcome.timestamp,
                metrics=tuple((metric.name, metric.value) for metric in result.metrics),
                forward_return=forward_return,
            )
        )

    return observations


def calibrate_partitions(
    partitions: ObservationPartitions,
    *,
    config: CalibrationConfig,
) -> CalibrationResult:
    rules = generate_candidate_rules(partitions.train, rule_weight=config.rule_weight)
    candidates: list[CalibrationCandidate] = []

    for pair in combinations(rules, 2):
        if pair[0].evidence_category == pair[1].evidence_category:
            continue
        train_stats = evaluate_rules(partitions.train, pair)
        validation_stats = evaluate_rules(partitions.validation, pair)
        if not _qualifies(train_stats, config.min_signals):
            continue
        if not _qualifies(validation_stats, config.min_signals):
            continue
        candidates.append(
            CalibrationCandidate(
                rules=(pair[0], pair[1]),
                train=train_stats,
                validation=validation_stats,
            )
        )

    candidates.sort(key=_candidate_sort_key, reverse=True)
    selected = candidates[0] if candidates else None
    test_stats = (
        evaluate_rules(partitions.test, selected.rules)
        if selected is not None
        else None
    )
    release_ready = bool(
        test_stats is not None and _qualifies(test_stats, config.min_signals)
    )

    return CalibrationResult(
        train_observations=len(partitions.train),
        validation_observations=len(partitions.validation),
        test_observations=len(partitions.test),
        generated_candidates=sum(
            1
            for pair in combinations(rules, 2)
            if pair[0].evidence_category != pair[1].evidence_category
        ),
        qualified_candidates=len(candidates),
        selected=selected,
        test=test_stats,
        release_ready=release_ready,
    )


def generate_candidate_rules(
    train: Iterable[CalibrationObservation],
    *,
    rule_weight: Decimal,
) -> tuple[MetricRule, ...]:
    observations = tuple(train)
    values_by_metric: dict[str, list[Decimal]] = {}
    for observation in observations:
        for name, value in observation.metrics:
            values_by_metric.setdefault(name, []).append(value)

    generated: list[MetricRule] = []
    seen: set[tuple[str, MetricOperator, Decimal, str]] = set()

    for blueprint in _BLUEPRINTS:
        values = values_by_metric.get(blueprint.metric_name)
        if not values:
            continue
        for quantile in blueprint.quantiles:
            threshold = _quantile(values, quantile)
            key = (
                blueprint.metric_name,
                blueprint.operator,
                threshold,
                blueprint.evidence_category.value,
            )
            if key in seen:
                continue
            seen.add(key)
            generated.append(
                MetricRule(
                    metric_name=blueprint.metric_name,
                    operator=blueprint.operator,
                    threshold=threshold,
                    weight=rule_weight,
                    evidence_category=blueprint.evidence_category.value,
                )
            )

    return tuple(generated)


def evaluate_rules(
    observations: Iterable[CalibrationObservation],
    rules: tuple[MetricRule, MetricRule],
) -> CandidateStats:
    policy = OpportunityPolicy(
        version="calibration",
        rules=rules,
        minimum_categories=2,
        max_ai_weight=ZERO,
        max_age=timedelta(minutes=1),
    )
    engine = OpportunityEngine(policy)
    returns: list[Decimal] = []

    for observation in observations:
        assessment = engine.assess(
            metrics=observation.metric_map(),
            price_quality=DataQuality.VALID,
            reference_at=observation.signal_at,
            evaluated_at=observation.signal_at,
            ai_positive=False,
        )
        if assessment.level in (
            OpportunityLevel.INTERESTING,
            OpportunityLevel.HIGH_INTEREST,
        ):
            returns.append(observation.forward_return)

    if not returns:
        return CandidateStats(0, 0, ZERO, ZERO, ZERO, ZERO)

    positive = sum(item > ZERO for item in returns)
    count = len(returns)
    return CandidateStats(
        signals=count,
        positive_outcomes=positive,
        hit_rate=Decimal(positive) / Decimal(count),
        average_forward_return=sum(returns, ZERO) / Decimal(count),
        best_forward_return=max(returns),
        worst_forward_return=min(returns),
    )


def _qualifies(stats: CandidateStats, min_signals: int) -> bool:
    return (
        stats.signals >= min_signals
        and stats.hit_rate >= HALF
        and stats.average_forward_return > ZERO
    )


def _candidate_sort_key(candidate: CalibrationCandidate) -> tuple[Decimal, Decimal, int, Decimal]:
    robust_hit_rate = min(candidate.train.hit_rate, candidate.validation.hit_rate)
    robust_average_return = min(
        candidate.train.average_forward_return,
        candidate.validation.average_forward_return,
    )
    return (
        robust_hit_rate,
        robust_average_return,
        candidate.validation.signals,
        candidate.validation.worst_forward_return,
    )


def _quantile(values: Iterable[Decimal], q: Decimal) -> Decimal:
    ordered = tuple(sorted(values))
    if not ordered:
        raise ValueError("quantile requer valores")
    if not ZERO <= q <= Decimal("1"):
        raise ValueError("q deve estar entre 0 e 1")
    if len(ordered) == 1:
        return ordered[0]

    position = Decimal(len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - Decimal(lower)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def rules_to_json(rules: tuple[MetricRule, MetricRule]) -> str:
    return json.dumps(
        [
            {
                "metric_name": rule.metric_name,
                "operator": rule.operator.value,
                "threshold": str(rule.threshold),
                "weight": str(rule.weight),
                "evidence_category": rule.evidence_category,
            }
            for rule in rules
        ],
        separators=(",", ":"),
        ensure_ascii=False,
    )


def result_to_dict(result: CalibrationResult) -> dict[str, object]:
    def stats(value: CandidateStats | None) -> dict[str, object] | None:
        if value is None:
            return None
        return {
            "signals": value.signals,
            "positive_outcomes": value.positive_outcomes,
            "hit_rate": str(value.hit_rate),
            "average_forward_return": str(value.average_forward_return),
            "best_forward_return": str(value.best_forward_return),
            "worst_forward_return": str(value.worst_forward_return),
        }

    selected_rules = (
        json.loads(rules_to_json(result.selected.rules))
        if result.selected is not None
        else None
    )
    return {
        "train_observations": result.train_observations,
        "validation_observations": result.validation_observations,
        "test_observations": result.test_observations,
        "generated_candidates": result.generated_candidates,
        "qualified_candidates": result.qualified_candidates,
        "release_ready": result.release_ready,
        "selected_rules": selected_rules,
        "train_stats": stats(result.selected.train if result.selected else None),
        "validation_stats": stats(
            result.selected.validation if result.selected else None
        ),
        "test_stats": stats(result.test),
        "opportunity_rules_json": result.rules_json(),
    }
