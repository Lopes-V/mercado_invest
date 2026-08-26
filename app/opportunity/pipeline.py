from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.market_data.models import DataQuality

from .core import MetricOperator, OpportunityAssessment, OpportunityEngine


@dataclass(frozen=True, slots=True)
class PreFilteredOpportunity:
    symbol: str
    metrics: dict[str, Decimal]
    assessment: OpportunityAssessment
    matched_rules: tuple[str, ...]
    presentation_rank: tuple[Decimal, int, Decimal, str]


class OpportunityPreFilter:
    """Runs the sole financial engine and derives a non-financial display rank."""

    def __init__(self, engine: OpportunityEngine) -> None:
        self._engine = engine

    @property
    def policy(self):
        return self._engine.policy

    def assess(
        self,
        *,
        metrics: dict[str, Decimal],
        quote_quality: DataQuality,
        reference_at: datetime,
        evaluated_at: datetime,
        symbol: str,
    ) -> PreFilteredOpportunity:
        assessment = self._engine.assess(
            metrics=metrics,
            price_quality=quote_quality,
            reference_at=reference_at,
            evaluated_at=evaluated_at,
        )
        matched = self._engine.matched_rules(metrics)
        proximity = self._proximity(metrics)
        return PreFilteredOpportunity(
            symbol=symbol,
            metrics=dict(metrics),
            assessment=assessment,
            matched_rules=tuple(rule.metric_name for rule in matched),
            presentation_rank=(
                assessment.score,
                assessment.evidence_count,
                proximity,
                symbol,
            ),
        )

    def _proximity(self, metrics: dict[str, Decimal]) -> Decimal:
        values: list[Decimal] = []
        for rule in self._engine.policy.rules:
            value = metrics.get(rule.metric_name)
            if value is None:
                continue
            threshold = rule.threshold
            if rule.operator in (MetricOperator.GT, MetricOperator.GTE):
                if threshold <= 0:
                    continue
                ratio = value / threshold
            else:
                if value <= 0 or threshold <= 0:
                    continue
                ratio = threshold / value
            values.append(min(Decimal("1"), max(Decimal("0"), ratio)))
        return sum(values, Decimal("0")) / Decimal(len(values)) if values else Decimal("0")
