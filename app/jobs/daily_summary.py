"""Daily consolidated Telegram closing built from persisted opportunity facts."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from zoneinfo import ZoneInfo

from app.jobs.models import JobContext, JobResult, ensure_job_name
from app.telegram.messages import (
    DailyInvestmentSummary,
    DailySummaryCandidate,
    TelegramMessageFormatter,
)


_RELEVANT_LEVELS = frozenset({"INTERESTING", "HIGH_INTEREST"})
_BRAZIL_TIME = ZoneInfo("America/Sao_Paulo")


class Opportunities(Protocol):
    def list_between(self, start: datetime, end: datetime): ...

    def get_latest_before(self, asset_id, before: datetime): ...


class Assets(Protocol):
    def get_by_id(self, asset_id): ...


class Quotes(Protocol):
    def get_latest_valid_at_or_before(self, asset_id, before: datetime): ...


class Metrics(Protocol):
    def list_by_analysis(self, analysis_id): ...


class AIRuns(Protocol):
    def get_by_id(self, record_id): ...


class MessageSender(Protocol):
    def send_message(self, chat_id: int, text: str): ...


class DailyInvestmentSummaryJob:
    """Send a single BRT closing without creating or repeating individual alerts."""

    def __init__(
        self,
        *,
        opportunities: Opportunities,
        assets: Assets,
        quotes: Quotes,
        metrics: Metrics,
        ai_runs: AIRuns,
        sender: MessageSender,
        recipient_ids: tuple[int, ...],
        top_n: int,
        hour_brt: int = 22,
    ) -> None:
        if not recipient_ids or any(
            isinstance(item, bool) or not isinstance(item, int) or item == 0
            for item in recipient_ids
        ):
            raise ValueError("ao menos um recipient inteiro n\u00e3o-zero deve ser informado")
        if isinstance(top_n, bool) or not isinstance(top_n, int) or not 1 <= top_n <= 10:
            raise ValueError("top_n deve estar entre 1 e 10")
        if isinstance(hour_brt, bool) or not isinstance(hour_brt, int) or not 0 <= hour_brt <= 23:
            raise ValueError("hour_brt deve estar entre 0 e 23")
        self._opportunities = opportunities
        self._assets = assets
        self._quotes = quotes
        self._metrics = metrics
        self._ai_runs = ai_runs
        self._sender = sender
        self._recipient_ids = recipient_ids
        self._top_n = top_n
        self._hour_brt = hour_brt
        ensure_job_name(self.name)

    @property
    def name(self) -> str:
        return "daily_investment_summary"

    def _day_bounds(self, closed_at: datetime) -> tuple[datetime, datetime]:
        local_close = closed_at.astimezone(_BRAZIL_TIME)
        if local_close.hour != self._hour_brt:
            raise ValueError("fechamento diario deve respeitar o horario BRT configurado")
        local_start = local_close.replace(hour=0, minute=0, second=0, microsecond=0)
        return local_start.astimezone(UTC), closed_at.astimezone(UTC)

    @staticmethod
    def _latest_by_asset(rows) -> dict:
        latest = {}
        for row in rows:
            if row.evaluated_at.tzinfo is None:
                raise ValueError("opportunity persistida sem timezone")
            current = latest.get(row.asset_id)
            if current is None or row.evaluated_at > current.evaluated_at:
                latest[row.asset_id] = row
        return latest

    @staticmethod
    def _metric_values(rows) -> dict[str, Decimal]:
        result: dict[str, Decimal] = {}
        for row in rows:
            if not isinstance(row.metric_value, Decimal) or not row.metric_value.is_finite():
                raise ValueError("m\u00e9trica persistida inv\u00e1lida para fechamento")
            result[row.metric_name] = row.metric_value
        missing = {"RETURN", "RSI", "VOLATILITY"}.difference(result)
        if missing:
            raise ValueError("m\u00e9tricas obrigat\u00f3rias ausentes no fechamento")
        return result

    def _candidate(self, opportunity, closed_at: datetime) -> tuple[DailySummaryCandidate, tuple[str, ...]]:
        asset = self._assets.get_by_id(opportunity.asset_id)
        if asset is None:
            raise ValueError("asset da opportunity n\u00e3o encontrado")
        quote = self._quotes.get_latest_valid_at_or_before(opportunity.asset_id, closed_at)
        if quote is None or quote.quality != "VALID" or quote.observed_at > closed_at:
            raise ValueError("quote VALID ausente para opportunity relevante")
        metric_values = self._metric_values(self._metrics.list_by_analysis(opportunity.analysis_id))
        ai_run = self._ai_runs.get_by_id(opportunity.ai_run_id) if opportunity.ai_run_id else None
        risks = tuple(ai_run.risks) if ai_run is not None else ()
        return (
            DailySummaryCandidate(
                symbol=asset.symbol,
                price=quote.price,
                currency_code=quote.currency_code,
                return_value=metric_values["RETURN"],
                rsi=metric_values["RSI"],
                volatility=metric_values["VOLATILITY"],
                level=opportunity.level,
                score=opportunity.score,
                gemini_summary=ai_run.summary if ai_run is not None else None,
            ),
            risks,
        )

    def execute(self, context: JobContext) -> JobResult:
        day_start, closed_at = self._day_bounds(context.scheduled_for)
        rows = tuple(self._opportunities.list_between(day_start, closed_at))
        latest = self._latest_by_asset(rows)
        relevant = [row for row in latest.values() if row.level in _RELEVANT_LEVELS]
        candidates: list[DailySummaryCandidate] = []
        all_risks: set[str] = set()
        for row in relevant:
            candidate, risks = self._candidate(row, closed_at)
            candidates.append(candidate)
            all_risks.update(risks)
        candidates.sort(key=lambda item: (-item.score, item.symbol))
        new_symbols: list[str] = []
        maintained_symbols: list[str] = []
        no_longer_interesting_symbols: list[str] = []
        for asset_id, latest_row in latest.items():
            asset = self._assets.get_by_id(asset_id)
            if asset is None:
                raise ValueError("asset da opportunity n\u00e3o encontrado")
            day_rows = [row for row in rows if row.asset_id == asset_id]
            was_relevant = any(row.level in _RELEVANT_LEVELS for row in day_rows)
            if latest_row.level in _RELEVANT_LEVELS:
                previous = self._opportunities.get_latest_before(asset_id, day_start)
                if previous is not None and previous.level in _RELEVANT_LEVELS:
                    maintained_symbols.append(asset.symbol)
                else:
                    new_symbols.append(asset.symbol)
            elif was_relevant:
                no_longer_interesting_symbols.append(asset.symbol)
        summary = DailyInvestmentSummary(
            closing_date=closed_at.astimezone(_BRAZIL_TIME).date(),
            analyzed_assets=len(latest),
            candidates=tuple(candidates[: self._top_n]),
            new_symbols=tuple(sorted(new_symbols)),
            maintained_symbols=tuple(sorted(maintained_symbols)),
            no_longer_interesting_symbols=tuple(sorted(no_longer_interesting_symbols)),
            risks=tuple(sorted(all_risks)[:5]),
        )
        text = TelegramMessageFormatter.render_daily_summary(summary)
        for recipient_id in self._recipient_ids:
            self._sender.send_message(recipient_id, text)
        return JobResult(processed_count=len(latest))
