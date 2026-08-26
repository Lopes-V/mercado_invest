from app.telegram.messages import (
    OpportunityAlertContent,
    PipelineSummary,
    SummaryCandidate,
    TelegramMessageFormatter,
)


def test_summary_includes_watch_and_honors_candidate_limit():
    summary = PipelineSummary(
        considered=15,
        analyzed=15,
        quality_blocked=0,
        levels=(("NONE", 10), ("WATCH", 5), ("INTERESTING", 0), ("HIGH_INTEREST", 0)),
        candidates=(SummaryCandidate("AAA3", "WATCH", "20", (("Retorno", "+2%"),)),),
        policy_version="candidate-v1",
        criteria=("RETURN > 2%", "VOLATILITY < 1%"),
    )
    text = TelegramMessageFormatter.render_summary(summary)
    assert "WATCH: 5" in text
    assert "AAA3" in text
    assert "Nenhuma oportunidade" in text


def test_alert_omits_unavailable_indicators_and_uses_real_values():
    text = TelegramMessageFormatter.render_opportunity_alert(
        OpportunityAlertContent(
            symbol="WEGE3",
            price="R$ 42,10",
            score="80",
            level="HIGH_INTEREST",
            timestamp="2026-08-21T18:00:00+00:00",
            indicators=(("Retorno", "+6,17%"),),
            criteria=("RETURN > 2,87%",),
            ai_summary="Contexto limitado aos fatos fornecidos.",
            risks=("volatilidade",),
        )
    )
    assert "WEGE3" in text and "R$ 42,10" in text
    assert "RSI" not in text
    assert "Contexto limitado" in text
