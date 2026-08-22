"""Fail-closed conversion of a persisted frozen policy into domain rules."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from app.database.repositories.policy_lifecycle import FrozenOpportunityPolicyRecord
from app.opportunity import EvidenceCategory, MetricOperator, MetricRule, OpportunityPolicy


class FrozenPolicyError(ValueError):
    """A persisted policy is not safe to execute in shadow mode."""


def load_frozen_opportunity_policy(
    record: FrozenOpportunityPolicyRecord,
    *,
    minimum_categories: int = 2,
    max_age: timedelta,
    max_ai_weight: Decimal = Decimal("0"),
) -> OpportunityPolicy:
    """Build an ``OpportunityPolicy`` only from an approved frozen record.

    Thresholds, weights, operators and evidence categories are always read
    from the immutable ``metric_rules`` JSON persisted with the calibration.
    The runtime supplies only operational freshness, never replacement rules.
    """

    if record.status != "FROZEN":
        raise FrozenPolicyError("shadow requer policy com status FROZEN")
    if not record.calibration_release_ready:
        raise FrozenPolicyError("shadow requer calibration_release_ready=true")
    if not isinstance(minimum_categories, int) or isinstance(minimum_categories, bool) or minimum_categories <= 0:
        raise FrozenPolicyError("minimum_categories deve ser inteiro positivo")
    if not isinstance(max_age, timedelta) or max_age <= timedelta():
        raise FrozenPolicyError("max_age deve ser timedelta positivo")
    if not isinstance(max_ai_weight, Decimal) or not max_ai_weight.is_finite() or not Decimal("0") <= max_ai_weight <= Decimal("100"):
        raise FrozenPolicyError("max_ai_weight deve ser Decimal entre 0 e 100")

    rules = tuple(_metric_rule(item, index=index) for index, item in enumerate(record.metric_rules))
    if not rules:
        raise FrozenPolicyError("policy congelada não possui metric_rules")
    return OpportunityPolicy(
        version=record.policy_version,
        rules=rules,
        minimum_categories=minimum_categories,
        # Shadow passes zero; the production composition may pass its explicit,
        # bounded setting while still using the same frozen metric rules.
        max_ai_weight=max_ai_weight,
        max_age=max_age,
    )


def _metric_rule(value: Mapping[str, object], *, index: int) -> MetricRule:
    def required(name: str) -> object:
        try:
            return value[name]
        except KeyError as exc:
            raise FrozenPolicyError(f"metric_rules[{index}].{name} ausente") from exc

    metric_name = required("metric_name")
    if not isinstance(metric_name, str) or not metric_name.strip():
        raise FrozenPolicyError(f"metric_rules[{index}].metric_name inválido")
    try:
        operator = MetricOperator(required("operator"))
    except (TypeError, ValueError) as exc:
        raise FrozenPolicyError(f"metric_rules[{index}].operator inválido") from exc
    try:
        category = EvidenceCategory(required("evidence_category"))
    except (TypeError, ValueError) as exc:
        raise FrozenPolicyError(
            f"metric_rules[{index}].evidence_category inválido"
        ) from exc
    threshold = _decimal(required("threshold"), field=f"metric_rules[{index}].threshold")
    weight = _decimal(required("weight"), field=f"metric_rules[{index}].weight")
    if weight <= Decimal("0") or weight > Decimal("100"):
        raise FrozenPolicyError(f"metric_rules[{index}].weight deve estar entre 0 e 100")
    return MetricRule(
        metric_name=metric_name.strip(),
        operator=operator,
        threshold=threshold,
        weight=weight,
        evidence_category=category.value,
    )


def _decimal(value: object, *, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise FrozenPolicyError(f"{field} deve ser decimal em texto ou inteiro")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise FrozenPolicyError(f"{field} inválido") from exc
    if not parsed.is_finite():
        raise FrozenPolicyError(f"{field} deve ser finito")
    return parsed
