from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.market_data.models import DataQuality


class OpportunityLevel(StrEnum):
    NONE = "NONE"
    WATCH = "WATCH"
    INTERESTING = "INTERESTING"
    HIGH_INTEREST = "HIGH_INTEREST"


class MetricOperator(StrEnum):
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"


class EvidenceCategory(StrEnum):
    TREND = "TREND"
    MOMENTUM = "MOMENTUM"
    RISK = "RISK"
    VOLUME = "VOLUME"
    AI_CONTEXT = "AI_CONTEXT"


@dataclass(frozen=True, slots=True)
class MetricRule:
    metric_name: str
    operator: MetricOperator
    threshold: Decimal
    weight: Decimal
    evidence_category: str


@dataclass(frozen=True, slots=True)
class OpportunityPolicy:
    version: str
    rules: tuple[MetricRule, ...]
    minimum_categories: int = 2
    max_ai_weight: Decimal = Decimal("0")
    max_age: timedelta = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class OpportunityAssessment:
    level: OpportunityLevel
    score: Decimal
    evidence_count: int
    reasons: tuple[str, ...]


class OpportunityEngine:
    def __init__(self, policy: OpportunityPolicy):
        self._policy = policy

    @property
    def policy(self) -> OpportunityPolicy:
        return self._policy

    def assess(
        self,
        *,
        metrics: dict[str, Decimal],
        price_quality: DataQuality,
        reference_at: datetime,
        evaluated_at: datetime,
    ) -> OpportunityAssessment:
        if (
            price_quality is not DataQuality.VALID
            or reference_at.tzinfo is None
            or evaluated_at.tzinfo is None
            or evaluated_at.astimezone(UTC) - reference_at.astimezone(UTC)
            > self._policy.max_age
        ):
            return OpportunityAssessment(
                OpportunityLevel.NONE,
                Decimal("0"),
                0,
                ("quality_or_timestamp_invalid",),
            )

        matched_rules = self.matched_rules(metrics)
        score = sum((rule.weight for rule in matched_rules), Decimal("0"))
        categories = {rule.evidence_category for rule in matched_rules}
        reasons = [rule.metric_name for rule in matched_rules]

        score = min(Decimal("100"), score)
        count = len(categories)
        if count == 0:
            level = OpportunityLevel.NONE
        elif count < self._policy.minimum_categories:
            level = OpportunityLevel.WATCH
        elif score >= Decimal("70"):
            level = OpportunityLevel.HIGH_INTEREST
        elif score >= Decimal("40"):
            level = OpportunityLevel.INTERESTING
        else:
            level = OpportunityLevel.WATCH
        return OpportunityAssessment(level, score, count, tuple(reasons))

    def matched_rules(self, metrics: dict[str, Decimal]) -> tuple[MetricRule, ...]:
        return tuple(
            rule
            for rule in self._policy.rules
            if rule.metric_name in metrics
            and {
                MetricOperator.GT: metrics[rule.metric_name] > rule.threshold,
                MetricOperator.GTE: metrics[rule.metric_name] >= rule.threshold,
                MetricOperator.LT: metrics[rule.metric_name] < rule.threshold,
                MetricOperator.LTE: metrics[rule.metric_name] <= rule.threshold,
            }[rule.operator]
        )


class OpportunityRepository(Protocol):
    def create(self, **payload): ...


class OpportunityService:
    def __init__(self, *, engine: OpportunityEngine, repository: OpportunityRepository) -> None:
        self._engine = engine
        self._repository = repository

    @property
    def engine(self) -> OpportunityEngine:
        return self._engine

    def assess(
        self,
        *,
        asset_id: UUID,
        analysis_id: UUID,
        metrics: dict[str, Decimal],
        quote_quality: DataQuality,
        reference_at: datetime,
        evaluated_at: datetime,
        ai_run_id: UUID | None = None,
    ) -> OpportunityAssessment:
        result = self._engine.assess(
            metrics=metrics,
            price_quality=quote_quality,
            reference_at=reference_at,
            evaluated_at=evaluated_at,
        )
        self.record(
            asset_id=asset_id,
            analysis_id=analysis_id,
            assessment=result,
            evaluated_at=evaluated_at,
            ai_run_id=ai_run_id,
        )
        return result

    def record(
        self,
        *,
        asset_id: UUID,
        analysis_id: UUID,
        assessment: OpportunityAssessment,
        evaluated_at: datetime,
        ai_run_id: UUID | None = None,
    ):
        return self._repository.create(
            asset_id=asset_id,
            analysis_id=analysis_id,
            ai_run_id=ai_run_id,
            level=assessment.level.value,
            score=str(assessment.score),
            evidence_count=assessment.evidence_count,
            evaluated_at=evaluated_at,
            policy_version=self._engine.policy.version,
            evidence=list(assessment.reasons),
        )
