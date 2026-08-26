"""Production and explicit simulation orchestration after market collection."""

from datetime import timedelta
from typing import Protocol
from uuid import UUID

from app.ai import AIService, ValidatedAIContext
from app.analysis import AnalysisService
from app.jobs.models import JobContext, JobResult, ensure_job_name
from app.market_data.models import CandleInterval, DataQuality
from app.monitoring.logger import get_logger
from app.opportunity import OpportunityLevel, OpportunityPreFilter, OpportunityService
from app.telegram.messages import OpportunityAlertContent, PipelineSummary, SummaryCandidate, TelegramMessageFormatter


class ProviderSymbols(Protocol):
    def list_active_by_provider(self, provider: str): ...


class Quotes(Protocol):
    def get_latest(self, asset_id: UUID, provider: str): ...


class Candles(Protocol):
    def get_range(self, *, asset_id: UUID, provider: str, interval: CandleInterval, start, end): ...


class Assets(Protocol):
    def get_by_id(self, asset_id: UUID): ...


class Markets(Protocol):
    def get_by_id(self, market_id: UUID): ...


class Analyses(Protocol):
    def get_latest_for_asset(self, asset_id: UUID, interval: str): ...


class AIRuns(Protocol):
    def get_latest_for_asset(self, asset_id: UUID): ...


class Opportunities(Protocol):
    def get_latest_for_asset(self, asset_id: UUID): ...


class Alerts(Protocol):
    def send(self, **kwargs): ...


class MessageSender(Protocol):
    def send_message(self, chat_id: int, text: str): ...


class AutomatedInvestmentPipelineJob:
    """Run quality, deterministic pre-filter, optional AI context and delivery."""

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
        ai_service: AIService | None,
        ai_runs: AIRuns,
        opportunity_service: OpportunityService,
        opportunities: Opportunities,
        alert_service: Alerts,
        recipient_id: int | None = None,
        recipient_ids: tuple[int, ...] = (),
        opportunity_pre_filter: OpportunityPreFilter | None = None,
        summary_sender: MessageSender | None = None,
        summary_enabled: bool = True,
        summary_top_n: int = 5,
        watch_ai_enabled: bool = False,
        dry_run: bool = False,
        interval: CandleInterval,
        lookback: timedelta,
        analysis_period: int,
        production_ready: bool = False,
        automation_enabled: bool = False,
    ) -> None:
        if not isinstance(provider_name, str) or not provider_name.strip():
            raise ValueError("provider_name não pode ser vazio")
        resolved = recipient_ids or ((recipient_id,) if recipient_id is not None else ())
        if not resolved or any(isinstance(item, bool) or not isinstance(item, int) or item == 0 for item in resolved):
            raise ValueError("ao menos um recipient inteiro não-zero deve ser informado")
        if not isinstance(interval, CandleInterval):
            raise ValueError("interval deve ser CandleInterval")
        if not isinstance(lookback, timedelta) or lookback <= timedelta():
            raise ValueError("lookback deve ser timedelta positivo")
        if isinstance(analysis_period, bool) or not isinstance(analysis_period, int) or analysis_period <= 0:
            raise ValueError("analysis_period deve ser inteiro positivo")
        if isinstance(summary_top_n, bool) or not isinstance(summary_top_n, int) or not 1 <= summary_top_n <= 10:
            raise ValueError("summary_top_n deve estar entre 1 e 10")
        self._provider_name = provider_name.strip()
        self._provider_symbols, self._quotes, self._candles = provider_symbols, quotes, candles
        self._assets, self._markets = assets, markets
        self._analysis_service, self._analyses = analysis_service, analyses
        self._ai_service, self._ai_runs = ai_service, ai_runs
        self._opportunity_service, self._opportunities = opportunity_service, opportunities
        self._alert_service = alert_service
        self._recipient_ids = tuple(resolved)
        self._opportunity_pre_filter = opportunity_pre_filter
        self._summary_sender, self._summary_enabled = summary_sender, summary_enabled
        self._summary_top_n, self._watch_ai_enabled, self._dry_run = summary_top_n, watch_ai_enabled, dry_run
        self._interval, self._lookback, self._analysis_period = interval, lookback, analysis_period
        self._production_ready, self._automation_enabled = production_ready, automation_enabled
        ensure_job_name(self.name)

    @property
    def name(self) -> str:
        return f"investment_pipeline:{self._provider_name}:{self._interval.value}"

    @staticmethod
    def _criteria(policy, names=None) -> tuple[str, ...]:
        symbols = {"GT": ">", "GTE": ">=", "LT": "<", "LTE": "<="}
        return tuple(
            f"{rule.metric_name} {symbols[rule.operator.value]} {rule.threshold}"
            for rule in policy.rules
            if names is None or rule.metric_name in names
        )

    def execute(self, context: JobContext) -> JobResult:
        mappings = tuple(self._provider_symbols.list_active_by_provider(self._provider_name))
        start, end = context.scheduled_for - self._lookback, context.scheduled_for
        processed = quality_blocked = gemini_calls = gemini_avoided = 0
        alerts_rendered = alerts_sent = alerts_suppressed = 0
        summaries_rendered = summaries_simulated = summaries_sent = 0
        counts = {level.value: 0 for level in OpportunityLevel}
        ranked: list[tuple[tuple, SummaryCandidate]] = []
        logger = get_logger()

        for mapping in mappings:
            quote = self._quotes.get_latest(mapping.asset_id, self._provider_name)
            if quote is None:
                quality_blocked += 1
                continue
            try:
                quote_quality = DataQuality(quote.quality)
            except ValueError as exc:
                raise ValueError("quote persistida possui quality inválida") from exc
            if quote_quality is not DataQuality.VALID:
                quality_blocked += 1
                continue
            rows = self._candles.get_range(asset_id=mapping.asset_id, provider=self._provider_name, interval=self._interval, start=start, end=end)
            if not rows:
                quality_blocked += 1
                continue
            try:
                qualities = tuple(DataQuality(row.quality) for row in rows)
            except ValueError as exc:
                raise ValueError("candle persistida possui quality inválida") from exc
            if any(quality is not DataQuality.VALID for quality in qualities):
                quality_blocked += 1
                continue
            asset = self._assets.get_by_id(mapping.asset_id)
            market = self._markets.get_by_id(asset.market_id) if asset is not None else None
            if asset is None or not asset.is_active or market is None or not market.is_active:
                quality_blocked += 1
                continue
            analysis = self._analysis_service.analyze(asset_id=mapping.asset_id, provider=self._provider_name, interval=self._interval, start=start, end=end, period=self._analysis_period)
            analysis_record = self._analyses.get_latest_for_asset(mapping.asset_id, self._interval.value)
            if analysis_record is None or analysis_record.reference_at != rows[-1].observed_at:
                raise RuntimeError("analysis persistida não corresponde ao histórico analisado")
            processed += 1
            metrics = {metric.name: metric.value for metric in analysis.metrics}
            prefiltered = self._opportunity_pre_filter.assess(metrics=metrics, quote_quality=quote_quality, reference_at=analysis_record.reference_at, evaluated_at=context.started_at, symbol=asset.symbol) if self._opportunity_pre_filter else None
            if prefiltered is None:
                assessment = self._opportunity_service.assess(asset_id=mapping.asset_id, analysis_id=analysis_record.id, metrics=metrics, quote_quality=quote_quality, reference_at=analysis_record.reference_at, evaluated_at=context.started_at)
            else:
                assessment = prefiltered.assessment
            counts[assessment.level.value] += 1
            candidate_level = assessment.level in (OpportunityLevel.INTERESTING, OpportunityLevel.HIGH_INTEREST)
            should_call_ai = self._ai_service is not None and (candidate_level or (assessment.level is OpportunityLevel.WATCH and self._watch_ai_enabled))
            ai_response = None
            if should_call_ai:
                ai_response = self._ai_service.analyze_live(context=ValidatedAIContext(asset_identity=asset.symbol, market=market.code, current_price=quote.price, currency_code=quote.currency_code, analysis_metrics=tuple(metrics.items()), data_timestamp=quote.observed_at, algorithm_version=analysis.algorithm_version), asset_id=mapping.asset_id, analysis_id=analysis_record.id)
                gemini_calls += 1
            else:
                gemini_avoided += 1
            ai_run = self._ai_runs.get_latest_for_asset(mapping.asset_id) if ai_response else None
            if prefiltered is not None:
                self._opportunity_service.record(asset_id=mapping.asset_id, analysis_id=analysis_record.id, assessment=assessment, evaluated_at=context.started_at, ai_run_id=getattr(ai_run, "id", None))
            opportunity = self._opportunities.get_latest_for_asset(mapping.asset_id)
            if opportunity is None or opportunity.evaluated_at != context.started_at:
                raise RuntimeError("opportunity persistida não corresponde à execução atual")
            if prefiltered is not None:
                policy = self._opportunity_pre_filter.policy
                indicators = tuple((name, str(value)) for name, value in metrics.items())
                ranked.append((prefiltered.presentation_rank, SummaryCandidate(asset.symbol, assessment.level.value, str(assessment.score), indicators)))
            if candidate_level:
                policy = self._opportunity_pre_filter.policy if self._opportunity_pre_filter else None
                indicators = tuple((name, str(value)) for name, value in metrics.items())
                alert_text = TelegramMessageFormatter.render_opportunity_alert(OpportunityAlertContent(asset.symbol, str(quote.price), str(assessment.score), assessment.level.value, quote.observed_at.isoformat(), indicators, self._criteria(policy, set(assessment.reasons)) if policy else (), getattr(ai_response, "summary", None), getattr(ai_response, "positive_factors", ()), getattr(ai_response, "negative_factors", ()), getattr(ai_response, "risks", ())))
                alerts_rendered += len(self._recipient_ids)
                cooldown_snapshot = self._alert_service.cooldown_snapshot(mapping.asset_id) if hasattr(self._alert_service, "cooldown_snapshot") else None
                for recipient_id in self._recipient_ids:
                    alert_result = self._alert_service.send(asset_id=mapping.asset_id, opportunity_id=opportunity.id, recipient_id=recipient_id, recipient_authorized=True, level=assessment.level, quality=quote_quality, decided_at=context.started_at, asset=asset.symbol, timestamp=quote.observed_at, price=quote.price, score=assessment.score, factors=getattr(ai_response, "positive_factors", ()), risks=getattr(ai_response, "risks", ()), production_ready=self._production_ready, automation_enabled=self._automation_enabled, dry_run=self._dry_run, message_text=alert_text, cooldown_reference=cooldown_snapshot)
                    if getattr(alert_result, "status", "") == "SENT":
                        alerts_sent += 1
                    else:
                        alerts_suppressed += 1

        if self._summary_enabled and self._summary_sender is not None:
            ranked.sort(key=lambda item: (-item[0][0], -item[0][1], -item[0][2], item[0][3]))
            policy = self._opportunity_pre_filter.policy if self._opportunity_pre_filter else None
            summary = PipelineSummary(len(mappings), processed, quality_blocked, tuple(counts.items()), tuple(item[1] for item in ranked[:self._summary_top_n]), policy.version if policy else "unknown", self._criteria(policy) if policy else (), gemini_calls_avoided=gemini_avoided, gemini_calls=gemini_calls, dry_run=self._dry_run)
            summary_text = TelegramMessageFormatter.render_summary(summary)
            summaries_rendered += 1
            for recipient_id in self._recipient_ids:
                self._summary_sender.send_message(recipient_id, summary_text)
            if self._dry_run:
                summaries_simulated += len(self._recipient_ids)
            else:
                summaries_sent += len(self._recipient_ids)
            logger.info("pipeline_summary_rendered analyzed=%s skipped=%s rendered=%s simulated=%s sent=%s dry_run=%s", processed, quality_blocked, summaries_rendered, summaries_simulated, summaries_sent, self._dry_run)
        logger.info("pipeline_completed considered=%s analyzed=%s skipped=%s levels=%s gemini_calls=%s gemini_calls_avoided=%s alerts_rendered=%s alerts_sent=%s alerts_suppressed=%s summaries_rendered=%s summaries_simulated=%s summaries_sent=%s dry_run=%s", len(mappings), processed, quality_blocked, counts, gemini_calls, gemini_avoided, alerts_rendered, alerts_sent, alerts_suppressed, summaries_rendered, summaries_simulated, summaries_sent, self._dry_run)
        return JobResult(processed_count=processed)
