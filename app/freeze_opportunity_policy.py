"""Persist an immutable, calibration-approved opportunity policy from a report."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from app.config.settings import get_settings
from app.database.client import create_supabase_client
from app.database.repositories import FrozenOpportunityPolicyRepository


def _timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} ausente no relatório")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{field} deve possuir timezone")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Congela uma policy aprovada sem alterar GitHub Variables.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--policy-version", required=True)
    parser.add_argument("--analysis-algorithm-version", default="analysis-v1")
    args = parser.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    result = report.get("result")
    methodology = report.get("methodology")
    robustness = report.get("robustness_report")
    if not isinstance(result, dict) or not result.get("release_ready"):
        raise SystemExit("CALIBRATION_RELEASE_READY=false; policy não pode ser congelada")
    if not isinstance(methodology, dict) or not isinstance(robustness, dict):
        raise SystemExit("relatório de calibração/robustez inválido")
    rules = result.get("selected_rules")
    partitions = methodology.get("global_partitions")
    if not isinstance(rules, list) or not rules or not isinstance(partitions, dict):
        raise SystemExit("relatório não contém regras ou partições globais")
    if not isinstance(args.policy_version, str) or not args.policy_version.strip():
        raise SystemExit("--policy-version não pode ser vazio")

    train = partitions.get("train")
    validation = partitions.get("validation")
    test = partitions.get("test")
    if not all(isinstance(item, dict) for item in (train, validation, test)):
        raise SystemExit("partições globais inválidas")
    source = hashlib.sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    repository = FrozenOpportunityPolicyRepository(create_supabase_client(get_settings()))
    if repository.get_by_version(args.policy_version) is not None:
        raise SystemExit("policy_version já existe; versões congeladas nunca são sobrescritas")
    repository.create(
        policy_version=args.policy_version.strip(),
        source_calibration_run=source,
        created_at=datetime.now(UTC),
        analysis_algorithm_version=args.analysis_algorithm_version,
        train_started_at=_timestamp(train.get("first_signal_at"), field="train.first_signal_at"),
        train_ended_at=_timestamp(train.get("last_outcome_at"), field="train.last_outcome_at"),
        validation_started_at=_timestamp(validation.get("first_signal_at"), field="validation.first_signal_at"),
        validation_ended_at=_timestamp(validation.get("last_outcome_at"), field="validation.last_outcome_at"),
        holdout_started_at=_timestamp(test.get("first_signal_at"), field="test.first_signal_at"),
        holdout_ended_at=_timestamp(test.get("last_outcome_at"), field="test.last_outcome_at"),
        metric_rules=rules,
        gross_metrics=robustness.get("overall"),
        net_metrics=robustness.get("overall"),
        bootstrap_metadata=robustness.get("bootstrap"),
        calibration_release_ready=True,
        status="FROZEN",
    )
    print(f"OPPORTUNITY_POLICY_VERSION={args.policy_version.strip()}")
    print("OPPORTUNITY_RULES_JSON=" + json.dumps(rules, separators=(",", ":"), ensure_ascii=False))


if __name__ == "__main__":
    main()
