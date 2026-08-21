"""Composition root for market collection and the automated analysis pipeline."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.ai import AIService, GeminiProvider
from app.alerts import AlertEngine, AlertPolicy, AlertService
from app.analysis import AnalysisEngine, AnalysisService
from app.automation_config import (
    build_opportunity_policy,
    build_quality_policy,
    validate_automation_settings,
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
)
from app.jobs.investment_pipeline import AutomatedInvestmentPipelineJob
from app.jobs.market_data import MarketHistoryCollectionJob, MarketQuoteCollectionJob
from app.jobs.runner import JobRunner
from app.jobs.schedule import IntervalSchedule, ScheduledJob, SchedulerService
from app.market_data.http import ProviderHttpClient
from app.market_data.ingestion import MarketDataIngestionService
from app.market_data.models import CandleInterval
from app.market_data.providers.brapi import BrapiProvider
from app.market_data.providers.twelve_data import TwelveDataProvider
from app.market_data.quality import QualityEngine, QualityPolicy
from app.opportunity import OpportunityEngine, OpportunityPolicy, OpportunityService
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

    if settings.automated_pipeline_enabled:
        if settings.gemini_api_key is None or settings.gemini_model is None:
            raise ValueError("Gemini precisa estar configurado para automação")
        opportunity_policy = opportunity_policy or build_opportunity_policy(settings)
        try:
            pipeline_interval = CandleInterval(
                settings.automated_pipeline_candle_interval
            )
        except ValueError as exc:
            raise ValueError("AUTOMATED_PIPELINE_CANDLE_INTERVAL inválido") from exc

        gemini = GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )
        telegram = TelegramClient(settings.telegram_bot_token)
        closers.extend((gemini.close, telegram.close))

        analysis_service = AnalysisService(
            candles=candles,
            engine=AnalysisEngine(),
            analyses=analyses,
            metrics=metrics,
        )
        ai_service = AIService(
            provider=gemini,
            repository=ai_runs,
            provider_name=gemini.name,
            model=settings.gemini_model,
            prompt_version=settings.automated_pipeline_prompt_version,
        )
        opportunity_service = OpportunityService(
            engine=OpportunityEngine(opportunity_policy),
            repository=opportunities,
        )
        alert_service = AlertService(
            engine=AlertEngine(
                AlertPolicy(cooldown=timedelta(seconds=settings.alert_cooldown_seconds))
            ),
            repository=alerts,
            sender=telegram,
        )
        recipient_id = next(iter(settings.telegram_allowed_user_ids))
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
                        recipient_id=recipient_id,
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
