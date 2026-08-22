from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.database.repositories.policy_lifecycle import FrozenOpportunityPolicyRecord


NOW = datetime(2026, 8, 21, tzinfo=UTC)


def _record():
    return FrozenOpportunityPolicyRecord(
        id=uuid4(),
        policy_version="candidate-v1",
        created_at=NOW,
        calibration_release_ready=True,
        status="FROZEN",
        metric_rules=(
            {
                "metric_name": "RETURN",
                "operator": "GT",
                "threshold": "0",
                "weight": "40",
                "evidence_category": "TREND",
            },
        ),
    )


def test_readiness_cli_reports_no_future_evidence_without_enabling_execution(
    monkeypatch, capsys
):
    import app.evaluate_production_readiness as command

    record = _record()
    monkeypatch.setattr(command, "get_settings", lambda: object())
    monkeypatch.setattr(command, "create_supabase_client", lambda _settings: object())
    monkeypatch.setattr(
        command,
        "FrozenOpportunityPolicyRepository",
        lambda _client: SimpleNamespace(get_by_version=lambda _version: record),
    )
    monkeypatch.setattr(
        command,
        "ShadowPredictionRepository",
        lambda _client: SimpleNamespace(list_realized_by_policy=lambda _policy_id: ()),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["evaluate_production_readiness", "--policy-version", "candidate-v1"],
    )
    command.main()
    output = capsys.readouterr().out
    assert "CALIBRATION_RELEASE_READY=true" in output
    assert "FUTURE_SIGNALS=0" in output
    assert "PRODUCTION_READY=false" in output
    assert "PRODUCTION_READY_REASON=insufficient_future_signals" in output


def test_readiness_cli_accepts_sufficient_net_positive_evidence(monkeypatch, capsys):
    import app.evaluate_production_readiness as command

    record = _record()
    predictions = tuple(
        SimpleNamespace(
            asset_id=uuid4(),
            predicted_at=NOW,
            realized_at=NOW + timedelta(days=5),
            gross_return=Decimal("0.02"),
            net_return=Decimal("0.018"),
        )
        for _ in range(20)
    )
    monkeypatch.setattr(command, "get_settings", lambda: object())
    monkeypatch.setattr(command, "create_supabase_client", lambda _settings: object())
    monkeypatch.setattr(
        command,
        "FrozenOpportunityPolicyRepository",
        lambda _client: SimpleNamespace(get_by_version=lambda _version: record),
    )
    monkeypatch.setattr(
        command,
        "ShadowPredictionRepository",
        lambda _client: SimpleNamespace(list_realized_by_policy=lambda _policy_id: predictions),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["evaluate_production_readiness", "--policy-version", "candidate-v1"],
    )
    command.main()
    output = capsys.readouterr().out
    assert "PRODUCTION_READY=true" in output
    assert "PRODUCTION_READY_REASON=future_evidence_gate_passed" in output
