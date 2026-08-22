"""Persistence boundary for frozen policies and future shadow evidence."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from supabase import Client

from app.database.models import (
    RepositoryDataError,
    _boolean,
    _datetime,
    _decimal,
    _nullable_datetime,
    _nullable_decimal,
    _text,
    _uuid,
)
from app.database.repositories._response import create_one, read_one_or_none


def _payload(**values: object) -> dict[str, object]:
    return {
        key: str(value) if isinstance(value, (UUID, Decimal)) else value.isoformat() if isinstance(value, datetime) else value
        for key, value in values.items()
    }


@dataclass(frozen=True, slots=True)
class FrozenOpportunityPolicyRecord:
    id: UUID
    policy_version: str
    created_at: datetime
    calibration_release_ready: bool
    status: str
    metric_rules: tuple[Mapping[str, object], ...]

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "FrozenOpportunityPolicyRecord":
        rules = payload.get("metric_rules")
        if (
            not isinstance(rules, list)
            or not rules
            or not all(isinstance(item, Mapping) for item in rules)
        ):
            raise RepositoryDataError("metric_rules inválidas no frozen policy")
        return cls(
            _uuid(payload, "id"),
            _text(payload, "policy_version"),
            _datetime(payload, "created_at"),
            _boolean(payload, "calibration_release_ready"),
            _text(payload, "status"),
            tuple(rules),
        )


@dataclass(frozen=True, slots=True)
class ShadowPredictionRecord:
    id: UUID
    policy_id: UUID
    asset_id: UUID
    provider: str
    interval: str
    prediction_key: str
    reference_at: datetime
    predicted_at: datetime
    outcome_due_at: datetime
    reference_price: Decimal
    quality: str
    round_trip_cost_bps: Decimal
    realized_at: datetime | None
    realized_price: Decimal | None
    gross_return: Decimal | None
    net_return: Decimal | None
    realized_positive: bool | None

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "ShadowPredictionRecord":
        positive = payload.get("realized_positive")
        if positive is not None and not isinstance(positive, bool):
            raise ValueError("realized_positive inválido")
        return cls(
            _uuid(payload, "id"), _uuid(payload, "policy_id"), _uuid(payload, "asset_id"), _text(payload, "provider"), _text(payload, "interval"), _text(payload, "prediction_key"),
            _datetime(payload, "reference_at"), _datetime(payload, "predicted_at"), _datetime(payload, "outcome_due_at"), _decimal(payload, "reference_price"), _text(payload, "quality"), _decimal(payload, "round_trip_cost_bps"),
            _nullable_datetime(payload, "realized_at"), _nullable_decimal(payload, "realized_price"),
            _nullable_decimal(payload, "gross_return"), _nullable_decimal(payload, "net_return"), positive,
        )


class FrozenOpportunityPolicyRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def create(self, **payload: object) -> FrozenOpportunityPolicyRecord:
        return create_one(self._client.table("frozen_opportunity_policies").insert(_payload(**payload)).execute(), operation="create frozen policy", parser=FrozenOpportunityPolicyRecord.from_payload)

    def get_by_version(self, policy_version: str) -> FrozenOpportunityPolicyRecord | None:
        return read_one_or_none(self._client.table("frozen_opportunity_policies").select("*").eq("policy_version", policy_version), operation="get frozen policy", parser=FrozenOpportunityPolicyRecord.from_payload)


class ShadowPredictionRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def create(self, **payload: object) -> ShadowPredictionRecord:
        return create_one(self._client.table("shadow_predictions").insert(_payload(**payload)).execute(), operation="create shadow prediction", parser=ShadowPredictionRecord.from_payload)

    def get_by_prediction_key(self, key: str) -> ShadowPredictionRecord | None:
        return read_one_or_none(self._client.table("shadow_predictions").select("*").eq("prediction_key", key), operation="get shadow prediction", parser=ShadowPredictionRecord.from_payload)

    def list_pending_due(self, *, before: datetime) -> tuple[ShadowPredictionRecord, ...]:
        response = self._client.table("shadow_predictions").select("*").is_("realized_at", "null").lte("outcome_due_at", before.isoformat()).order("outcome_due_at").execute()
        data = getattr(response, "data", None)
        if not isinstance(data, list) or not all(isinstance(item, Mapping) for item in data):
            raise RepositoryDataError("list pending shadow predictions retornou dados inválidos")
        return tuple(ShadowPredictionRecord.from_payload(item) for item in data)

    def list_realized_by_policy(self, policy_id: UUID) -> tuple[ShadowPredictionRecord, ...]:
        """Return only settled records for a frozen policy.

        Filtering after typed parsing keeps the PostgREST query portable while
        making the future-evidence boundary explicit: pending predictions never
        count as evidence.
        """

        records = self.list_by_policy(policy_id)
        return tuple(record for record in records if record.realized_at is not None)

    def list_by_policy(self, policy_id: UUID) -> tuple[ShadowPredictionRecord, ...]:
        """List a policy's shadow audit trail in deterministic reference order."""

        response = (
            self._client.table("shadow_predictions")
            .select("*")
            .eq("policy_id", str(policy_id))
            .order("reference_at", desc=False)
            .execute()
        )
        data = getattr(response, "data", None)
        if not isinstance(data, list) or not all(isinstance(item, Mapping) for item in data):
            raise RepositoryDataError("list shadow predictions retornou dados inválidos")
        records = tuple(ShadowPredictionRecord.from_payload(item) for item in data)
        return records

    def record_outcome(self, *, prediction_id: UUID, realized_at: datetime, realized_price: Decimal, gross_return: Decimal, net_return: Decimal, realized_positive: bool) -> ShadowPredictionRecord:
        response = self._client.table("shadow_predictions").update(_payload(realized_at=realized_at, realized_price=realized_price, gross_return=gross_return, net_return=net_return, realized_positive=realized_positive)).eq("id", str(prediction_id)).is_("realized_at", "null").execute()
        return create_one(response, operation="record shadow outcome", parser=ShadowPredictionRecord.from_payload)
