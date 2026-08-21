"""Scheduled orchestration from validated market data to Telegram alerts."""

from datetime import timedelta
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.ai import AIClassification, AIService, ValidatedAIContext
from app.analysis import AnalysisService
from app.jobs.models import JobContext, JobResult, ensure_job_name
from app.market_data.models import CandleInterval, DataQuality
from app.opportunity import OpportunityService


class ProviderSymbols(Protocol):
    def list_active_by_provider(self, provider: str):
        ...


class Quotes(Protocol):
    def get_latest(self, asset_id: UUID, provider: str):
        ...


class Candles(Protocol):
    def get_range(
        self,
        *,
        asset_id: UUID,
        provider: str,
        interval: CandleInterval,
        start,
        end,
    ):
        ...


class Assets(Protocol):
    def get_by_id(self, asset_id: UUID):
        ...


class Markets(Protocol):
    def get_by_id(self, market_id: UUID):
        ...


class Analyses(Protocol):
    def get_latest_for_asset(self, asset_id: UUID, interval: str):
        ...


class AIRuns(Protocol):
    def get_latest_for_asset(self, asset_id: UUID):
        ...


class Opportunities(Protocol):
    def get_latest_for_asset(self, asset_id: UUID):
        ...


class Alerts(Protocol):
    def send(self, **kwargs):
        ...


class AutomatedInvestmentPipelineJob:
    """Run the auditable analysis/AI/decision/alert chain for one provider.

    Market collection is deliberately separate and scheduled before this job.
    Missing or non-VALID inputs are skipped; provider/DB/AI/Telegram failures
    propagate so JobRunner records a FAILED run instead of fabricating success.
    """

    def __init__(
        self,
        *,
        provider_name: str,
        provider_symbols: ProviderSymbols,
        quotes: Quotes,
        candles: Candles,
        assets: Assets,
        markets: Markets,
        analysis_service: AnalysisService,
        analyses: Analyses,
        ai_service: AIService,
        ai_runs: AIRuns,
        opportunity_service: OpportunityService,
        opportunities: Opportunities,
        alert_service: Alerts,
        recipient_id: int,
        interval: CandleInterval,
        lookback: timedelta,
        analysis_period: int,
    ) -> None:
        if not isinstance(provider_name, str) or not provider_name.strip():
            raise ValueError("provider_name não pode ser vazio")
        if not isinstance(recipient_id, int) or isinstance(recipient_id, bool) or recipient_id <= 0:
            raise ValueError("recipient_id deve ser inteiro positivo")
        if not isinstance(interval, CandleInterval):
            raise ValueError("interval deve ser CandleInterval")
        if not isinstance(lookback, timedelta) or lookback <= timedelta():
            raise ValueError("lookback deve ser timedelta positivo")
        if isinstance(analysis_period, bool) or not isinstance(analysis_period, int) or analysis_period <= 0:
            raise ValueError("analysis_period deve ser inteiro positivo")

        self._provider_name = provider_name.strip()
        self._provider_symbols = provider_symbols
        self._quotes = quotes
        self._candles = candles
        self._assets = assets
        self._markets = markets
        self._analysis_service = analysis_service
        self._analyses = analyses
        self._ai_service = ai_service
        self._ai_runs = ai_runs
        self._opportunity_service = opportunity_service
        self._opportunities = opportunities
        self._alert_service = alert_service
        self._recipient_id = recipient_id
        self._interval = interval
        self._lookback = lookback
        self._analysis_period = analysis_period
        ensure_job_name(self.name)

    @property
    def name(self) -> str:
        return f"investment_pipeline:{self._provider_name}:{self._interval.value}"

    def execute(self, context: JobContext) -> JobResult:
        mappings = self._provider_symbols.list_active_by_provider(self._provider_name)
        processed = 0
        start = context.scheduled_for - self._lookback
        end = context.scheduled_for

        for mapping in mappings:
            quote = self._quotes.get_latest(mapping.asset_id, self._provider_name)
            if quote is None:
                continue
            try:
                quote_quality = DataQuality(quote.quality)
            except ValueError as exc:
                raise ValueError("quote persistida possui quality inválida") from exc
            if quote_quality is not DataQuality.VALID:
                continue

            rows = self._candles.get_range(
                asset_id=mapping.asset_id,
                provider=self._provider_name,
                interval=self._interval,
                start=start,
                end=end,
            )
            if not rows:
                continue
            try:
                row_qualities = tuple(DataQuality(row.quality) for row in rows)
            except ValueError as exc:
                raise ValueError("candle persistida possui quality inválida") from exc
            if any(quality is not DataQuality.VALID for quality in row_qualities):
                continue

            asset = self._assets.get_by_id(mapping.asset_id)
            if asset is None or not asset.is_active:
                continue
            market = self._markets.get_by_id(asset.market_id)
            if market is None or not market.is_active:
                continue

            analysis = self._analysis_service.analyze(
                asset_id=mapping.asset_id,
                provider=self._provider_name,
                interval=self._interval,
                start=start,
                end=end,
                period=self._analysis_period,
            )
            analysis_record = self._analyses.get_latest_for_asset(
                mapping.asset_id, self._interval.value
            )
            if analysis_record is None:
                raise RuntimeError("analysis persistida não encontrada após execução")
            if analysis_record.reference_at != rows[-1].observed_at:
                raise RuntimeError("latest analysis não corresponde ao histórico analisado")

            metrics = {metric.name: metric.value for metric in analysis.metrics}
            ai_response = self._ai_service.analyze_live(
                context=ValidatedAIContext(
                    asset_identity=asset.symbol,
                    market=market.code,
                    current_price=quote.price,
                    currency_code=quote.currency_code,
                    analysis_metrics=tuple(
                        (metric.name, metric.value) for metric in analysis.metrics
                    ),
                    data_timestamp=quote.observed_at,
                    algorithm_version=analysis.algorithm_version,
                ),
                asset_id=mapping.asset_id,
                analysis_id=analysis_record.id,
            )
            ai_run = self._ai_runs.get_latest_for_asset(mapping.asset_id)

            assessment = self._opportunity_service.assess(
                asset_id=mapping.asset_id,
                analysis_id=analysis_record.id,
                ai_run_id=getattr(ai_run, "id", None),
                metrics=metrics,
                quote_quality=quote_quality,
                reference_at=analysis_record.reference_at,
                evaluated_at=context.started_at,
                ai_positive=ai_response.classification is AIClassification.POSITIVE,
            )
            opportunity = self._opportunities.get_latest_for_asset(mapping.asset_id)
            if opportunity is None:
                raise RuntimeError("opportunity persistida não encontrada após avaliação")
            if opportunity.evaluated_at != context.started_at:
                raise RuntimeError("latest opportunity não corresponde à execução atual")

            self._alert_service.send(
                asset_id=mapping.asset_id,
                opportunity_id=opportunity.id,
                recipient_id=self._recipient_id,
                recipient_authorized=True,
                level=assessment.level,
                quality=quote_quality,
                decided_at=context.started_at,
                asset=asset.symbol,
                timestamp=quote.observed_at,
                price=quote.price,
                score=assessment.score,
                factors=ai_response.positive_factors,
                risks=ai_response.risks,
            )
            processed += 1

        return JobResult(processed_count=processed)
