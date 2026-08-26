from datetime import UTC, datetime, timedelta
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.backtesting.calibration import CalibrationObservation
from app.alerts import AlertEngine, AlertPolicy, AlertService
from app.market_data.models import DataQuality
from app.opportunity import EvidenceCategory, MetricOperator, MetricRule, OpportunityAssessment, OpportunityLevel, OpportunityPolicy
from app.policy_lifecycle import ProductionGatePolicy, build_robustness_report, future_evidence_from_realized, production_ready
from app.shadow import ShadowPredictionInput, ShadowService


NOW = datetime(2026, 1, 1, tzinfo=UTC)
ASSET_A = uuid4()
ASSET_B = uuid4()
POLICY_ID = uuid4()


def policy() -> OpportunityPolicy:
    return OpportunityPolicy(
        version="frozen-v1",
        rules=(
            MetricRule("RETURN", MetricOperator.GT, Decimal("0"), Decimal("30"), EvidenceCategory.TREND.value),
            MetricRule("VOLATILITY", MetricOperator.LT, Decimal("1"), Decimal("30"), EvidenceCategory.RISK.value),
        ),
        minimum_categories=2,
        max_ai_weight=Decimal("0"),
        max_age=timedelta(minutes=1),
    )


def observations() -> tuple[CalibrationObservation, ...]:
    return tuple(
        CalibrationObservation(
            asset_id=ASSET_A if index < 3 else ASSET_B,
            signal_at=NOW + timedelta(days=index * 31),
            outcome_at=NOW + timedelta(days=index * 31 + 5),
            metrics=(("RETURN", Decimal("0.1")), ("VOLATILITY", Decimal("0.1"))),
            forward_return=Decimal("0.001") if index == 0 else Decimal("0.01"),
        )
        for index in range(5)
    )


def test_robustness_reports_cost_concentration_months_and_reproducible_bootstrap():
    first = build_robustness_report(observations(), policy=policy(), round_trip_cost_bps=Decimal("20"), bootstrap_seed=7, bootstrap_samples=50)
    second = build_robustness_report(observations(), policy=policy(), round_trip_cost_bps=Decimal("20"), bootstrap_seed=7, bootstrap_samples=50)

    assert first.overall.signals == 5
    assert first.overall.gross_average_forward_return > first.overall.net_average_forward_return
    assert first.overall.net_hit_rate < first.overall.gross_hit_rate
    assert first.signals_by_asset == {ASSET_A: 3, ASSET_B: 2}
    assert first.max_asset_signal_share == Decimal("0.6")
    assert len(first.signals_by_month) == 5
    assert first.bootstrap == second.bootstrap
    assert first.bootstrap.average_forward_return.low <= first.bootstrap.average_forward_return.high


def test_historical_calibration_alone_never_makes_production_ready():
    evidence = future_evidence_from_realized(())
    assert not production_ready(
        calibration_release_ready=True,
        policy_active=True,
        evidence=evidence,
    )


def test_future_evidence_requires_net_positive_but_not_operator_enablement():
    rows = tuple(
        SimpleNamespace(
            policy_id=POLICY_ID,
            asset_id=ASSET_A,
            provider="test",
            interval="1d",
            reference_at=NOW + timedelta(days=index),
            predicted_at=NOW + timedelta(days=index),
            realized_at=NOW + timedelta(days=index + 5),
            gross_return=Decimal("0.01"),
            net_return=Decimal("0.005"),
        )
        for index in range(20)
    )
    evidence = future_evidence_from_realized(rows)
    gate = ProductionGatePolicy(min_future_signals=20)
    assert production_ready(
        calibration_release_ready=True,
        policy_active=True,
        evidence=evidence,
        gate=gate,
    )


def test_net_negative_future_evidence_blocks_policy_readiness():
    rows = tuple(
        SimpleNamespace(
            policy_id=POLICY_ID,
            asset_id=ASSET_A,
            provider="test",
            interval="1d",
            reference_at=NOW + timedelta(days=index),
            predicted_at=NOW,
            realized_at=NOW + timedelta(days=index + 5),
            gross_return=Decimal("0.001"),
            net_return=Decimal("-0.001"),
        )
        for index in range(20)
    )
    assert not production_ready(
        calibration_release_ready=True,
        policy_active=True,
        evidence=future_evidence_from_realized(rows),
    )


class ShadowRepo:
    def __init__(self): self.items = []
    def get_by_prediction_key(self, key): return next((item for item in self.items if item.prediction_key == key), None)
    def create(self, **payload):
        row = SimpleNamespace(id=uuid4(), realized_at=None, realized_price=None, gross_return=None, net_return=None, realized_positive=None, **payload)
        self.items.append(row)
        return row
    def list_pending_due(self, *, before): return tuple(item for item in self.items if item.realized_at is None and item.outcome_due_at <= before)
    def record_outcome(self, *, prediction_id, **payload):
        row = next(item for item in self.items if item.id == prediction_id)
        for key, value in payload.items(): setattr(row, key, value)
        return row


def test_shadow_prediction_is_idempotent_and_settlement_cannot_look_ahead():
    repo = ShadowRepo()
    service = ShadowService(repository=repo)
    item = ShadowPredictionInput(
        policy_id=uuid4(), policy_version="frozen-v1", asset_id=ASSET_A, provider="test", interval="1d",
        reference_at=NOW,
        predicted_at=NOW, outcome_due_at=NOW + timedelta(days=5), reference_price=Decimal("100"), quality=DataQuality.VALID,
        assessment=OpportunityAssessment(OpportunityLevel.INTERESTING, Decimal("60"), 2, ("RETURN",)), metrics={"RETURN": Decimal("0.1")}, round_trip_cost_bps=Decimal("20"),
    )
    first = service.record_prediction(item)
    assert service.record_prediction(item) is first

    assert ShadowService.prediction_key(replace(item, reference_at=NOW + timedelta(days=1))) != ShadowService.prediction_key(item)
    assert ShadowService.prediction_key(replace(item, predicted_at=NOW + timedelta(minutes=30))) == ShadowService.prediction_key(item)
    assert service.record_prediction(replace(item, predicted_at=NOW + timedelta(minutes=30))) is first

    class Prices:
        def first_price_at_or_after(self, **kwargs):
            return SimpleNamespace(observed_at=NOW + timedelta(days=4), close=Decimal("110"), quality="VALID")
    try:
        service.settle_due(now=NOW + timedelta(days=5), prices=Prices())
    except ValueError as exc:
        assert "não pode usar preço anterior" in str(exc)
    else:
        raise AssertionError("settlement com candle anterior ao horizonte deve falhar")

    class DuePrices:
        def first_price_at_or_after(self, **kwargs):
            return SimpleNamespace(observed_at=NOW + timedelta(days=5), close=Decimal("110"), quality="VALID")
    settled = service.settle_due(now=NOW + timedelta(days=5), prices=DuePrices())
    assert len(settled) == 1
    assert settled[0].gross_return == Decimal("0.1")
    assert settled[0].net_return == Decimal("0.098")
    assert service.settle_due(now=NOW + timedelta(days=6), prices=DuePrices()) == ()


def test_shadow_settlement_ignores_non_valid_outcome_candles():
    repo = ShadowRepo()
    service = ShadowService(repository=repo)
    service.record_prediction(
        ShadowPredictionInput(
            policy_id=uuid4(), policy_version="frozen-v1", asset_id=ASSET_A,
            provider="test", interval="1d", predicted_at=NOW,
            reference_at=NOW,
            outcome_due_at=NOW + timedelta(days=5), reference_price=Decimal("100"),
            quality=DataQuality.VALID,
            assessment=OpportunityAssessment(OpportunityLevel.INTERESTING, Decimal("60"), 2, ("RETURN",)),
            metrics={"RETURN": Decimal("0.1")}, round_trip_cost_bps=Decimal("20"),
        )
    )

    class InvalidPrices:
        def first_price_at_or_after(self, **_kwargs):
            return SimpleNamespace(
                observed_at=NOW + timedelta(days=5),
                close=Decimal("110"),
                quality="STALE",
            )

    assert service.settle_due(now=NOW + timedelta(days=5), prices=InvalidPrices()) == ()
    assert repo.items[0].realized_at is None


def test_future_evidence_counts_only_realized_shadow_predictions():
    pending = SimpleNamespace(
        policy_id=POLICY_ID,
        asset_id=ASSET_A,
        provider="test",
        interval="1d",
        reference_at=NOW,
        predicted_at=NOW,
        realized_at=None,
        gross_return=None,
        net_return=None,
    )
    settled = SimpleNamespace(
        policy_id=POLICY_ID,
        asset_id=ASSET_A,
        provider="test",
        interval="1d",
        reference_at=NOW,
        predicted_at=NOW,
        realized_at=NOW + timedelta(days=5),
        gross_return=Decimal("0.02"),
        net_return=Decimal("0.018"),
    )
    evidence = future_evidence_from_realized((pending, settled))
    assert evidence.signals == 1
    assert evidence.net_average_return == Decimal("0.018")


def test_repeated_scheduler_slots_for_one_reference_candle_do_not_inflate_future_signals():
    rows = tuple(
        SimpleNamespace(
            policy_id=POLICY_ID,
            asset_id=ASSET_A,
            provider="test",
            interval="1d",
            reference_at=NOW,
            predicted_at=NOW + timedelta(minutes=30 * index),
            realized_at=NOW + timedelta(days=5),
            gross_return=Decimal("0.02"),
            net_return=Decimal("0.018"),
        )
        for index in range(20)
    )
    evidence = future_evidence_from_realized(rows)

    assert evidence.signals == 1
    assert not production_ready(
        calibration_release_ready=True,
        policy_active=True,
        evidence=evidence,
        gate=ProductionGatePolicy(min_future_signals=20),
    )


def test_alert_is_suppressed_until_production_and_automation_gates_are_true():
    class Alerts:
        def get_by_dedupe_key(self, _key): return None
        def get_latest_sent_for_asset(self, _asset): return None
        def create_pending(self, **_payload): return SimpleNamespace(id=uuid4())
        def mark_suppressed(self, *, alert_id, reason): return SimpleNamespace(id=alert_id, status="SUPPRESSED", reason=reason)
        def mark_sent(self, **_payload): raise AssertionError("não deve enviar")
        def mark_failed(self, **_payload): raise AssertionError("não deve falhar")
    class Sender:
        def send_message(self, *_args): raise AssertionError("shadow/produção bloqueada não envia Telegram")
    result = AlertService(engine=AlertEngine(AlertPolicy()), repository=Alerts(), sender=Sender()).send(
        asset_id=ASSET_A, opportunity_id=uuid4(), recipient_id=1, recipient_authorized=True,
        level=OpportunityLevel.INTERESTING, quality=DataQuality.VALID, decided_at=NOW,
        asset="TEST", timestamp=NOW, price=Decimal("100"), score=Decimal("60"),
    )
    assert result.status == "SUPPRESSED"
    assert result.reason == "production_gate"


def test_alert_dry_run_renders_without_external_send_and_uses_recipient_dedupe():
    class Alerts:
        def __init__(self): self.rows = []
        def get_by_dedupe_key(self, key): return next((row for row in self.rows if row.key == key), None)
        def get_latest_sent_for_asset(self, _asset): return None
        def create_pending(self, **payload):
            row = SimpleNamespace(id=uuid4(), key=payload["dedupe_key"])
            self.rows.append(row)
            return row
        def mark_suppressed(self, *, alert_id, reason): return SimpleNamespace(id=alert_id, status="SUPPRESSED", reason=reason)
        def mark_sent(self, **_payload): raise AssertionError("dry-run não deve marcar SENT")
        def mark_failed(self, **_payload): raise AssertionError("não deve falhar")
    class Sender:
        def __init__(self): self.messages = []
        def send_message(self, chat_id, text): self.messages.append((chat_id, text))
    repository, sender = Alerts(), Sender()
    service = AlertService(engine=AlertEngine(AlertPolicy()), repository=repository, sender=sender)
    kwargs = dict(
        asset_id=ASSET_A, opportunity_id=uuid4(), recipient_authorized=True,
        level=OpportunityLevel.INTERESTING, quality=DataQuality.VALID,
        decided_at=NOW, asset="TEST", timestamp=NOW, price=Decimal("100"),
        score=Decimal("60"), production_ready=False, automation_enabled=False,
        dry_run=True,
    )
    first = service.send(recipient_id=1, **kwargs)
    second = service.send(recipient_id=2, **kwargs)
    assert first.status == second.status == "SUPPRESSED"
    assert [item[0] for item in sender.messages] == [1, 2]
    assert len(repository.rows) == 2
