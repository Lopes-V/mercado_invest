"""Composition root for market collection and the automated analysis pipeline."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.ai import AIService, GeminiProvider
from app.alerts import AlertEngine, AlertPolicy, AlertService
from app.analysis import AnalysisEngine, AnalysisService
from app.automation_config import (
    build_quality_policy,
    validate_automation_settings,
    validate_shadow_settings,
)
from app.config.settings import Settings
from app.database.client import create_supabase_client
from app.database.repositories import (
    AIRunRepository,
    AlertRepository,
    AnalysisMetricRepository,
    AnalysisRepository,
    AssetRepository,
    JobRunRepository,
    MarketCandleRepository,
    MarketQuoteRepository,
    MarketRepository,
    OpportunityRepository,
    ProviderSymbolRepository,
    FrozenOpportunityPolicyRepository,
    ShadowPredictionRepository,
)
from app.jobs.investment_pipeline import AutomatedInvestmentPipelineJob
from app.jobs.market_data import MarketHistoryCollectionJob, MarketQuoteCollectionJob
from app.jobs.shadow import ShadowOpportunityPipelineJob, ShadowSettlementJob
from app.jobs.runner import JobRunner
from app.jobs.schedule import IntervalSchedule, ScheduledJob, SchedulerService
from app.market_data.http import ProviderHttpClient
from app.market_data.ingestion import MarketDataIngestionService
from app.market_data.models import CandleInterval
from app.market_data.providers.brapi import BrapiProvider
from app.market_data.providers.twelve_data import TwelveDataProvider
from app.market_data.quality import QualityEngine, QualityPolicy
from app.opportunity import OpportunityEngine, OpportunityPolicy, OpportunityPreFilter, OpportunityService
from app.shadow import ShadowService
from app.shadow_policy import FrozenPolicyError, load_frozen_opportunity_policy, validate_production_frozen_policy
from app.telegram.client import TelegramClient


@dataclass(slots=True)
class Application:
    job_runs: JobRunRepository
    scheduler: SchedulerService
    _closers: tuple[Callable[[], None], ...]

    def close(self) -> None:
        first_error: Exception | None = None
        for closer in reversed(self._closers):
            try:
                closer()
            except Exception as exc:  # cleanup must continue for remaining clients
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error


def build_application(
    settings: Settings,
    *,
    quality_policy: QualityPolicy | None = None,
    opportunity_policy: OpportunityPolicy | None = None,
) -> Application:
    validate_shadow_settings(settings)
    production_pipeline_enabled = (
        settings.automated_pipeline_enabled
        and settings.automation_enabled
        and settings.production_ready
    )
    simulation_pipeline_enabled = (
        settings.automated_pipeline_enabled and settings.pipeline_simulation_enabled
    )
    if production_pipeline_enabled:
        validate_automation_settings(settings)
    if simulation_pipeline_enabled:
        validate_automation_settings(settings)
    quality_policy = quality_policy or build_quality_policy(settings)

    client = create_supabase_client(settings)
    symbols = ProviderSymbolRepository(client)
    quotes = MarketQuoteRepository(client)
    candles = MarketCandleRepository(client)
    assets = AssetRepository(client)
    markets = MarketRepository(client)
    analyses = AnalysisRepository(client)
    metrics = AnalysisMetricRepository(client)
    ai_runs = AIRunRepository(client)
    opportunities = OpportunityRepository(client)
    alerts = AlertRepository(client)
    frozen_policies = FrozenOpportunityPolicyRepository(client)
    shadow_predictions = ShadowPredictionRepository(client)
    job_runs = JobRunRepository(client)
    runner = JobRunner(job_runs)
    jobs: list[ScheduledJob] = []
    closers: list[Callable[[], None]] = []
    anchor = datetime(1970, 1, 1, tzinfo=UTC)
    quality_engine = QualityEngine(quality_policy)

    providers: dict[str, tuple[object, MarketDataIngestionService]] = {}

    brapi_http = ProviderHttpClient(base_url="https://brapi.dev")
    brapi = BrapiProvider(brapi_http, token=settings.brapi_token)
    brapi_ingestion = MarketDataIngestionService(
        provider=brapi,
        quality_engine=quality_engine,
        provider_symbols=symbols,
        quotes=quotes,
        candles=candles,
    )
    providers[brapi.name] = (brapi, brapi_ingestion)
    closers.append(brapi_http.close)

    if settings.twelve_data_api_key:
        twelve_http = ProviderHttpClient(base_url="https://api.twelvedata.com")
        twelve = TwelveDataProvider(
            twelve_http,
            api_key=settings.twelve_data_api_key,
        )
        twelve_ingestion = MarketDataIngestionService(
            provider=twelve,
            quality_engine=quality_engine,
            provider_symbols=symbols,
            quotes=quotes,
            candles=candles,
        )
        providers[twelve.name] = (twelve, twelve_ingestion)
        closers.append(twelve_http.close)

    if settings.market_quotes_enabled:
        schedule = IntervalSchedule(
            timedelta(seconds=settings.market_quotes_interval_seconds), anchor
        )
        for provider, ingestion in providers.values():
            jobs.append(
                ScheduledJob(
                    MarketQuoteCollectionJob(
                        provider=provider,
                        ingestion=ingestion,
                        provider_symbols=symbols,
                    ),
                    schedule,
                )
            )

    try:
        history_interval = CandleInterval(settings.market_history_candle_interval)
    except ValueError as exc:
        raise ValueError("MARKET_HISTORY_CANDLE_INTERVAL inválido") from exc

    if settings.market_history_enabled:
        schedule = IntervalSchedule(
            timedelta(seconds=settings.market_history_interval_seconds), anchor
        )
        for provider, ingestion in providers.values():
            jobs.append(
                ScheduledJob(
                    MarketHistoryCollectionJob(
                        provider=provider,
                        ingestion=ingestion,
                        provider_symbols=symbols,
                        interval=history_interval,
                        lookback=timedelta(days=settings.market_history_lookback_days),
                    ),
                    schedule,
                )
            )

    if settings.shadow_mode_enabled:
        try:
            shadow_interval = CandleInterval(settings.shadow_candle_interval)
        except ValueError as exc:
            raise ValueError("SHADOW_CANDLE_INTERVAL inválido") from exc
        analysis_service = AnalysisService(
            candles=candles,
            engine=AnalysisEngine(),
            analyses=analyses,
            metrics=metrics,
        )
        shadow_service = ShadowService(repository=shadow_predictions)
        shadow_schedule = IntervalSchedule(
            timedelta(seconds=settings.shadow_interval_seconds), anchor
        )
        for provider_name in providers:
            jobs.append(
                ScheduledJob(
                    ShadowOpportunityPipelineJob(
                        provider_name=provider_name,
                        policy_version=settings.shadow_policy_version or "",
                        frozen_policies=frozen_policies,
                        provider_symbols=symbols,
                        candles=candles,
                        analysis_service=analysis_service,
                        shadow_service=shadow_service,
                        interval=shadow_interval,
                        lookback=timedelta(days=settings.shadow_lookback_days),
                        analysis_period=settings.shadow_analysis_period,
                        forward_horizon_days=settings.shadow_forward_horizon_days,
                        round_trip_cost_bps=settings.shadow_round_trip_cost_bps,
                    ),
                    shadow_schedule,
                )
            )
        jobs.append(
            ScheduledJob(
                ShadowSettlementJob(shadow_service=shadow_service, candles=candles),
                shadow_schedule,
            )
        )

    if production_pipeline_enabled or simulation_pipeline_enabled:
        if production_pipeline_enabled and (settings.gemini_api_key is None or settings.gemini_model is None):
            raise ValueError("Gemini precisa estar configurado para automação")
        if not settings.opportunity_policy_version:
            raise ValueError("OPPORTUNITY_POLICY_VERSION é obrigatória para a pipeline")
        frozen_record = frozen_policies.get_by_version(settings.opportunity_policy_version)
        if frozen_record is None:
            raise ValueError("pipeline de produção requer policy congelada")
        try:
            frozen_policy = load_frozen_opportunity_policy(
                frozen_record,
                minimum_categories=2,
                max_ai_weight=Decimal("0"),
                max_age=timedelta(
                    seconds=settings.automated_pipeline_reference_max_age_seconds
                ),
            )
        except FrozenPolicyError as exc:
            raise ValueError("pipeline de produção requer policy congelada aprovada") from exc
        try:
            validate_production_frozen_policy(frozen_policy)
        except FrozenPolicyError as exc:
            raise ValueError("pipeline requer policy determinística sem AI_CONTEXT legado") from exc
        opportunity_policy = frozen_policy
        try:
            pipeline_interval = CandleInterval(
                settings.automated_pipeline_candle_interval
            )
        except ValueError as exc:
            raise ValueError("AUTOMATED_PIPELINE_CANDLE_INTERVAL inválido") from exc

        gemini = None
        if production_pipeline_enabled or settings.dry_run_allow_ai:
            if settings.gemini_api_key is None or settings.gemini_model is None:
                raise ValueError("Gemini precisa estar configurado quando a IA está habilitada")
            gemini = GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
            closers.append(gemini.close)
        telegram = TelegramClient(settings.telegram_bot_token, dry_run=simulation_pipeline_enabled)
        closers.append(telegram.close)

        analysis_service = AnalysisService(
            candles=candles,
            engine=AnalysisEngine(),
            analyses=analyses,
            metrics=metrics,
        )
        ai_service = (
            AIService(
                provider=gemini,
                repository=ai_runs,
                provider_name=gemini.name,
                model=settings.gemini_model or "dry-run-disabled",
                prompt_version=settings.automated_pipeline_prompt_version,
            )
            if gemini is not None
            else None
        )
        opportunity_service = OpportunityService(
            engine=OpportunityEngine(opportunity_policy),
            repository=opportunities,
        )
        opportunity_pre_filter = OpportunityPreFilter(opportunity_service.engine)
        alert_service = AlertService(
            engine=AlertEngine(
                AlertPolicy(cooldown=timedelta(seconds=settings.alert_cooldown_seconds))
            ),
            repository=alerts,
            sender=telegram,
        )
        pipeline_schedule = IntervalSchedule(
            timedelta(seconds=settings.automated_pipeline_interval_seconds), anchor
        )

        for provider_name in settings.automated_pipeline_providers:
            if provider_name not in providers:
                raise ValueError(
                    f"provider {provider_name} não está configurado para automação"
                )
            jobs.append(
                ScheduledJob(
                    AutomatedInvestmentPipelineJob(
                        provider_name=provider_name,
                        provider_symbols=symbols,
                        quotes=quotes,
                        candles=candles,
                        assets=assets,
                        markets=markets,
                        analysis_service=analysis_service,
                        analyses=analyses,
                        ai_service=ai_service,
                        ai_runs=ai_runs,
                        opportunity_service=opportunity_service,
                        opportunities=opportunities,
                        alert_service=alert_service,
                        recipient_ids=settings.telegram_alert_chat_ids,
                        opportunity_pre_filter=opportunity_pre_filter,
                        summary_sender=telegram,
                        summary_enabled=settings.telegram_summary_enabled,
                        summary_top_n=settings.telegram_summary_top_n,
                        dry_run=simulation_pipeline_enabled,
                        interval=pipeline_interval,
                        lookback=timedelta(
                            days=settings.automated_pipeline_lookback_days
                        ),
                        analysis_period=settings.automated_pipeline_analysis_period,
                        production_ready=settings.production_ready,
                        automation_enabled=settings.automation_enabled,
                    ),
                    pipeline_schedule,
                )
            )

    return Application(
        job_runs=job_runs,
        scheduler=SchedulerService(runner, jobs),
        _closers=tuple(closers),
    )
