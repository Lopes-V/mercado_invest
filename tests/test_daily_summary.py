from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.jobs.daily_summary import DailyInvestmentSummaryJob
from app.jobs.models import JobContext, JobTrigger
from app.telegram.messages import DailyInvestmentSummary, DailySummaryCandidate, TelegramMessageFormatter


LOCAL_CLOSE = datetime(2026, 9, 9, 1, 0, tzinfo=UTC)
DAY_START = datetime(2026, 9, 8, 3, 0, tzinfo=UTC)
ASSET_A, ASSET_B, ASSET_C = uuid4(), uuid4(), uuid4()
ANALYSIS_A, ANALYSIS_B, ANALYSIS_C = uuid4(), uuid4(), uuid4()
AI_A, AI_B = uuid4(), uuid4()


def opportunity(asset_id, analysis_id, level, score, evaluated_at):
    return SimpleNamespace(
        asset_id=asset_id,
        analysis_id=analysis_id,
        ai_run_id={ASSET_A: AI_A, ASSET_B: AI_B}.get(asset_id),
        level=level,
        score=Decimal(score),
        evaluated_at=evaluated_at,
    )


class Opportunities:
    def __init__(self, rows, before):
        self.rows, self.before = rows, before

    def list_between(self, start, end):
        assert start == DAY_START and end == LOCAL_CLOSE
        return self.rows

    def get_latest_before(self, asset_id, before):
        assert before == DAY_START
        return self.before.get(asset_id)


class Assets:
    symbols = {ASSET_A: "ALFA3", ASSET_B: "BETA4", ASSET_C: "GAMA5"}

    def get_by_id(self, asset_id):
        return SimpleNamespace(symbol=self.symbols[asset_id])


class Quotes:
    def get_latest_valid_at_or_before(self, asset_id, before):
        assert before == LOCAL_CLOSE
        return SimpleNamespace(
            price={ASSET_A: Decimal("42.1"), ASSET_B: Decimal("1050"), ASSET_C: Decimal("10")}[asset_id],
            currency_code="BRL",
            quality="VALID",
            observed_at=LOCAL_CLOSE - timedelta(minutes=5),
        )


class Metrics:
    values = {
        ANALYSIS_A: (("RETURN", "0.0512"), ("RSI", "58.678"), ("VOLATILITY", "0.01234")),
        ANALYSIS_B: (("RETURN", "-0.023"), ("RSI", "45"), ("VOLATILITY", "0.02")),
    }

    def list_by_analysis(self, analysis_id):
        return tuple(
            SimpleNamespace(metric_name=name, metric_value=Decimal(value))
            for name, value in self.values[analysis_id]
        )


class AIRuns:
    def get_by_id(self, record_id):
        return {
            AI_A: SimpleNamespace(summary="Tendência sustentada pelos dados validados.", risks=("Volatilidade elevada",)),
            AI_B: SimpleNamespace(summary="Retorno recente fraco exige cautela.", risks=("Volatilidade elevada", "Liquidez")),
        }[record_id]


class Sender:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))


def context():
    return JobContext(uuid4(), JobTrigger.SCHEDULED, LOCAL_CLOSE, LOCAL_CLOSE)


def test_daily_summary_consolidates_ranked_opportunities_and_transitions():
    rows = (
        opportunity(ASSET_A, ANALYSIS_A, "HIGH_INTEREST", "70", LOCAL_CLOSE - timedelta(minutes=10)),
        opportunity(ASSET_B, ANALYSIS_B, "INTERESTING", "80", LOCAL_CLOSE - timedelta(minutes=5)),
        opportunity(ASSET_C, ANALYSIS_C, "INTERESTING", "60", LOCAL_CLOSE - timedelta(hours=1)),
        opportunity(ASSET_C, ANALYSIS_C, "WATCH", "20", LOCAL_CLOSE - timedelta(minutes=2)),
    )
    previous = {
        ASSET_A: opportunity(ASSET_A, ANALYSIS_A, "INTERESTING", "60", DAY_START - timedelta(minutes=1)),
        ASSET_B: opportunity(ASSET_B, ANALYSIS_B, "WATCH", "20", DAY_START - timedelta(minutes=1)),
    }
    sender = Sender()
    job = DailyInvestmentSummaryJob(
        opportunities=Opportunities(rows, previous),
        assets=Assets(),
        quotes=Quotes(),
        metrics=Metrics(),
        ai_runs=AIRuns(),
        sender=sender,
        recipient_ids=(-1001, 42),
        top_n=5,
    )

    result = job.execute(context())

    assert result.processed_count == 3
    assert [chat_id for chat_id, _text in sender.messages] == [-1001, 42]
    text = sender.messages[0][1]
    assert text.index("BETA4") < text.index("ALFA3")
    assert "R$ 1.050,00" in text
    assert "Retorno: -2,30%" in text
    assert "RSI: 58,68" in text
    assert "Volatilidade: 1,23%" in text
    assert "Novas: BETA4" in text
    assert "Mantidas: ALFA3" in text
    assert "Deixaram de ser interessantes: GAMA5" in text
    assert "Tendência sustentada pelos dados validados." in text
    assert "Principais riscos: Liquidez; Volatilidade elevada" in text


def test_daily_summary_clearly_reports_when_no_relevant_opportunity_exists():
    sender = Sender()
    job = DailyInvestmentSummaryJob(
        opportunities=Opportunities(
            (opportunity(ASSET_C, ANALYSIS_C, "WATCH", "20", LOCAL_CLOSE - timedelta(minutes=2)),),
            {},
        ),
        assets=Assets(),
        quotes=Quotes(),
        metrics=Metrics(),
        ai_runs=AIRuns(),
        sender=sender,
        recipient_ids=(42,),
        top_n=5,
    )

    job.execute(context())

    assert len(sender.messages) == 1
    assert "Nenhuma oportunidade relevante foi encontrada no fechamento de hoje." in sender.messages[0][1]


def test_daily_summary_limits_gemini_free_text_to_keep_the_closing_readable():
    text = TelegramMessageFormatter.render_daily_summary(
        DailyInvestmentSummary(
            closing_date=LOCAL_CLOSE.date(),
            analyzed_assets=1,
            candidates=(
                DailySummaryCandidate(
                    symbol="ALFA3",
                    price=Decimal("1"),
                    currency_code="BRL",
                    return_value=Decimal("0"),
                    rsi=Decimal("50"),
                    volatility=Decimal("0"),
                    level="INTERESTING",
                    score=Decimal("40"),
                    gemini_summary="a" * 500,
                ),
            ),
            new_symbols=("ALFA3",),
            maintained_symbols=(),
            no_longer_interesting_symbols=(),
            risks=(),
        )
    )

    assert "a" * 500 not in text
    assert "..." in text


def test_daily_summary_rejects_relevant_opportunity_without_valid_quote():
    class MissingQuotes:
        def get_latest_valid_at_or_before(self, _asset_id, _before):
            return None

    job = DailyInvestmentSummaryJob(
        opportunities=Opportunities(
            (opportunity(ASSET_A, ANALYSIS_A, "INTERESTING", "70", LOCAL_CLOSE - timedelta(minutes=2)),),
            {},
        ),
        assets=Assets(),
        quotes=MissingQuotes(),
        metrics=Metrics(),
        ai_runs=AIRuns(),
        sender=Sender(),
        recipient_ids=(42,),
        top_n=5,
    )

    with pytest.raises(ValueError, match="quote VALID ausente"):
        job.execute(context())
