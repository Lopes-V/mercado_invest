"""Non-trading future validation for frozen opportunity policies."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.market_data.models import DataQuality
from app.opportunity import OpportunityAssessment, OpportunityLevel


ZERO = Decimal("0")


class ShadowRepository(Protocol):
    def create(self, **payload: object): ...
    def get_by_prediction_key(self, key: str): ...
    def list_pending_due(self, *, before: datetime): ...
    def record_outcome(self, **payload: object): ...


class RealizedPriceSource(Protocol):
    def first_price_at_or_after(self, *, asset_id: UUID, provider: str, interval: str, at_or_after: datetime): ...


@dataclass(frozen=True, slots=True)
class ShadowPredictionInput:
    policy_id: UUID
    policy_version: str
    asset_id: UUID
    provider: str
    interval: str
    predicted_at: datetime
    outcome_due_at: datetime
    reference_price: Decimal
    quality: DataQuality
    assessment: OpportunityAssessment
    metrics: dict[str, Decimal]
    round_trip_cost_bps: Decimal


class ShadowService:
    """Persist predictions and settle them later; it has no alert/trading dependency."""

    @staticmethod
    def prediction_key(item: ShadowPredictionInput) -> str:
        return f"{item.policy_version}:{item.asset_id}:{item.provider}:{item.interval}:{item.predicted_at.isoformat()}"

    def __init__(self, *, repository: ShadowRepository) -> None:
        self._repository = repository

    def record_prediction(self, item: ShadowPredictionInput):
        if item.quality is not DataQuality.VALID:
            raise ValueError("shadow exige quality VALID")
        if item.outcome_due_at <= item.predicted_at:
            raise ValueError("outcome_due_at deve ser posterior à previsão")
        if item.reference_price <= ZERO:
            raise ValueError("reference_price deve ser positivo")
        if item.round_trip_cost_bps < ZERO:
            raise ValueError("round_trip_cost_bps não pode ser negativo")
        key = self.prediction_key(item)
        existing = self._repository.get_by_prediction_key(key)
        if existing is not None:
            return existing
        return self._repository.create(
            policy_id=item.policy_id,
            asset_id=item.asset_id,
            provider=item.provider,
            interval=item.interval,
            prediction_key=key,
            predicted_at=item.predicted_at,
            outcome_due_at=item.outcome_due_at,
            reference_price=item.reference_price,
            quality=item.quality.value,
            opportunity_level=item.assessment.level.value,
            opportunity_score=item.assessment.score,
            metrics=json.dumps({name: str(value) for name, value in sorted(item.metrics.items())}),
            round_trip_cost_bps=item.round_trip_cost_bps,
        )

    def settle_due(self, *, now: datetime, prices: RealizedPriceSource) -> tuple[object, ...]:
        """Use only a price timestamped at/after the pre-recorded due instant."""

        settled: list[object] = []
        for prediction in self._repository.list_pending_due(before=now):
            price_row = prices.first_price_at_or_after(
                asset_id=prediction.asset_id,
                provider=prediction.provider,
                interval=prediction.interval,
                at_or_after=prediction.outcome_due_at,
            )
            if price_row is None:
                continue
            if price_row.observed_at < prediction.outcome_due_at:
                raise ValueError("outcome shadow não pode usar preço anterior ao horizonte")
            if price_row.quality != DataQuality.VALID.value:
                continue
            gross = (price_row.close - prediction.reference_price) / prediction.reference_price
            net = gross - (prediction.round_trip_cost_bps / Decimal("10000"))
            settled.append(
                self._repository.record_outcome(
                    prediction_id=prediction.id,
                    realized_at=price_row.observed_at,
                    realized_price=price_row.close,
                    gross_return=gross,
                    net_return=net,
                    realized_positive=gross > ZERO,
                )
            )
        return tuple(settled)
