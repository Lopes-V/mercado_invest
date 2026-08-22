"""Evaluate future shadow evidence without changing any runtime variable."""

from __future__ import annotations

import argparse
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from app.config.settings import get_settings
from app.database.client import create_supabase_client
from app.database.repositories import (
    FrozenOpportunityPolicyRepository,
    ShadowPredictionRepository,
)
from app.policy_lifecycle import (
    ProductionGatePolicy,
    future_evidence_from_realized,
    production_ready,
)
from app.shadow_policy import FrozenPolicyError, load_frozen_opportunity_policy


def _decimal(raw: str, *, field: str) -> Decimal:
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(f"{field} deve ser decimal") from exc
    if not value.is_finite() or not Decimal("0") <= value <= Decimal("1"):
        raise argparse.ArgumentTypeError(f"{field} deve estar entre 0 e 1")
    return value


def _reason(*, record, evidence, gate: ProductionGatePolicy, ready: bool) -> str:
    if ready:
        return "future_evidence_gate_passed"
    if record.status != "FROZEN":
        return "policy_not_frozen"
    if not record.calibration_release_ready:
        return "calibration_release_not_ready"
    if evidence.signals < gate.min_future_signals:
        return "insufficient_future_signals"
    if evidence.gross_hit_rate < gate.minimum_hit_rate:
        return "future_hit_rate_below_minimum"
    if evidence.net_average_return <= Decimal("0"):
        return "future_net_average_return_not_positive"
    return "policy_validation_failed"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Avalia readiness de produção a partir de evidência shadow realizada."
    )
    parser.add_argument("--policy-version", required=True)
    parser.add_argument("--min-future-signals", type=int, default=20)
    parser.add_argument(
        "--minimum-hit-rate",
        default=Decimal("0.5"),
        type=lambda raw: _decimal(raw, field="--minimum-hit-rate"),
    )
    args = parser.parse_args()
    gate = ProductionGatePolicy(
        min_future_signals=args.min_future_signals,
        minimum_hit_rate=args.minimum_hit_rate,
    )

    client = create_supabase_client(get_settings())
    policies = FrozenOpportunityPolicyRepository(client)
    predictions = ShadowPredictionRepository(client)
    record = policies.get_by_version(args.policy_version)
    if record is None:
        raise SystemExit("policy_version não encontrada")
    try:
        # Validate immutable rule data before it can be treated as an active policy.
        load_frozen_opportunity_policy(record, max_age=timedelta(days=1))
    except FrozenPolicyError as exc:
        raise SystemExit(f"policy congelada inválida: {exc}") from exc

    evidence = future_evidence_from_realized(
        predictions.list_realized_by_policy(record.id)
    )
    ready = production_ready(
        calibration_release_ready=record.calibration_release_ready,
        policy_active=record.status == "FROZEN",
        evidence=evidence,
        gate=gate,
    )
    print(f"CALIBRATION_RELEASE_READY={str(record.calibration_release_ready).lower()}")
    print(f"FUTURE_SIGNALS={evidence.signals}")
    print(f"FUTURE_HIT_RATE={evidence.gross_hit_rate}")
    print(f"FUTURE_GROSS_AVERAGE_RETURN={evidence.gross_average_return}")
    print(f"FUTURE_NET_AVERAGE_RETURN={evidence.net_average_return}")
    print(f"PRODUCTION_READY={str(ready).lower()}")
    print(f"PRODUCTION_READY_REASON={_reason(record=record, evidence=evidence, gate=gate, ready=ready)}")


if __name__ == "__main__":
    main()
