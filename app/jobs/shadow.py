"""Deterministic, non-notifying shadow evaluation jobs."""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol

from app.analysis import AnalysisService
from app.jobs.models import JobContext, JobResult, ensure_job_name
from app.market_data.models import CandleInterval, DataQuality
from app.opportunity import OpportunityEngine, OpportunityLevel
from app.shadow import ShadowPredictionInput, ShadowService
from app.shadow_policy import load_frozen_opportunity_policy


class FrozenPolicySource(Protocol):
    def get_by_version(self, policy_version: str): ...


class ProviderSymbolsSource(Protocol):
    def list_active_by_provider(self, provider: str): ...


class CandlesSource(Protocol):
    def get_range(self, *, asset_id, provider: str, interval: CandleInterval, start, end): ...


class ShadowOpportunityPipelineJob:
    """Persist deterministic future predictions from one immutable policy.

    This job intentionally has no Gemini, AlertService, Telegram or paper
    trading dependency.  It records only qualified deterministic opportunity
    signals, so a shadow row is semantically a future-evidence signal.
    """

    def __init__(
        self,
        *,
        provider_name: str,
        policy_version: str,
        frozen_policies: FrozenPolicySource,
        provider_symbols: ProviderSymbolsSource,
        candles: CandlesSource,
        analysis_service: AnalysisService,
        shadow_service: ShadowService,
        interval: CandleInterval,
        lookback: timedelta,
        analysis_period: int,
        forward_horizon_days: int,
        round_trip_cost_bps,
    ) -> None:
        if not isinstance(provider_name, str) or not provider_name.strip():
            raise ValueError("provider_name não pode ser vazio")
        if not isinstance(policy_version, str) or not policy_version.strip():
            raise ValueError("policy_version não pode ser vazio")
        if not isinstance(interval, CandleInterval):
            raise ValueError("interval deve ser CandleInterval")
        if not isinstance(lookback, timedelta) or lookback <= timedelta():
            raise ValueError("lookback deve ser timedelta positivo")
        if not isinstance(analysis_period, int) or isinstance(analysis_period, bool) or analysis_period <= 0:
            raise ValueError("analysis_period deve ser inteiro positivo")
        if not isinstance(forward_horizon_days, int) or isinstance(forward_horizon_days, bool) or forward_horizon_days <= 0:
            raise ValueError("forward_horizon_days deve ser inteiro positivo")
        self._provider_name = provider_name
        self._policy_version = policy_version
        self._frozen_policies = frozen_policies
        self._provider_symbols = provider_symbols
        self._candles = candles
        self._analysis_service = analysis_service
        self._shadow_service = shadow_service
        self._interval = interval
        self._lookback = lookback
        self._analysis_period = analysis_period
        self._forward_horizon = timedelta(days=forward_horizon_days)
        self._round_trip_cost_bps = round_trip_cost_bps
        ensure_job_name(self.name)

    @property
    def name(self) -> str:
        return f"shadow_opportunity:{self._provider_name}:{self._interval.value}"

    def execute(self, context: JobContext) -> JobResult:
        record = self._frozen_policies.get_by_version(self._policy_version)
        if record is None:
            raise ValueError("SHADOW_POLICY_VERSION não foi encontrada")
        policy = load_frozen_opportunity_policy(
            record,
            max_age=self._lookback + timedelta(days=2),
        )
        engine = OpportunityEngine(policy)
        start = context.scheduled_for - self._lookback
        processed = 0
        for mapping in self._provider_symbols.list_active_by_provider(self._provider_name):
            rows = self._candles.get_range(
                asset_id=mapping.asset_id,
                provider=self._provider_name,
                interval=self._interval,
                start=start,
                end=context.scheduled_for,
            )
            # A quality failure blocks this asset rather than introducing a
            # partial analysis with selected data.  Other assets still retain
            # their own deterministic evaluations.
            if not rows:
                continue
            try:
                qualities = tuple(DataQuality(row.quality) for row in rows)
            except ValueError as exc:
                raise ValueError("candle persistida possui quality inválida") from exc
            if any(quality is not DataQuality.VALID for quality in qualities):
                continue
            analysis = self._analysis_service.analyze(
                asset_id=mapping.asset_id,
                provider=self._provider_name,
                interval=self._interval,
                start=start,
                end=context.scheduled_for,
                period=self._analysis_period,
            )
            reference = rows[-1]
            assessment = engine.assess(
                metrics={metric.name: metric.value for metric in analysis.metrics},
                price_quality=DataQuality.VALID,
                reference_at=reference.observed_at,
                evaluated_at=context.scheduled_for,
                ai_positive=False,
            )
            if assessment.level not in (
                OpportunityLevel.INTERESTING,
                OpportunityLevel.HIGH_INTEREST,
            ):
                continue
            self._shadow_service.record_prediction(
                ShadowPredictionInput(
                    policy_id=record.id,
                    policy_version=record.policy_version,
                    asset_id=mapping.asset_id,
                    provider=self._provider_name,
                    interval=self._interval.value,
                    predicted_at=context.scheduled_for,
                    # This is a calendar-day horizon, explicitly configured
                    # as SHADOW_FORWARD_HORIZON_DAYS; it is not a candle count.
                    outcome_due_at=context.scheduled_for + self._forward_horizon,
                    reference_price=reference.close,
                    quality=DataQuality.VALID,
                    assessment=assessment,
                    metrics={metric.name: metric.value for metric in analysis.metrics},
                    round_trip_cost_bps=self._round_trip_cost_bps,
                )
            )
            processed += 1
        return JobResult(processed)


class ShadowSettlementJob:
    """Settle only due shadow predictions with a later VALID candle."""

    def __init__(self, *, shadow_service: ShadowService, candles: CandlesSource) -> None:
        self._shadow_service = shadow_service
        self._candles = candles
        ensure_job_name(self.name)

    @property
    def name(self) -> str:
        return "shadow_settlement"

    def execute(self, context: JobContext) -> JobResult:
        records = self._shadow_service.settle_due(now=context.scheduled_for, prices=self._candles)
        return JobResult(len(records))
