from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True, slots=True)
class SummaryCandidate:
    symbol: str
    level: str
    score: str
    indicators: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class PipelineSummary:
    considered: int
    analyzed: int
    quality_blocked: int
    levels: tuple[tuple[str, int], ...]
    candidates: tuple[SummaryCandidate, ...]
    policy_version: str
    criteria: tuple[str, ...]
    gemini_calls_avoided: int = 0
    gemini_calls: int = 0
    dry_run: bool = False


@dataclass(frozen=True, slots=True)
class OpportunityAlertContent:
    symbol: str
    price: str
    score: str
    level: str
    timestamp: str
    indicators: tuple[tuple[str, str], ...] = ()
    criteria: tuple[str, ...] = ()
    ai_summary: str | None = None
    positive_factors: tuple[str, ...] = ()
    negative_factors: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DailySummaryCandidate:
    symbol: str
    price: Decimal
    currency_code: str
    return_value: Decimal
    rsi: Decimal
    volatility: Decimal
    level: str
    score: Decimal
    gemini_summary: str | None = None


@dataclass(frozen=True, slots=True)
class DailyInvestmentSummary:
    closing_date: date
    analyzed_assets: int
    candidates: tuple[DailySummaryCandidate, ...]
    new_symbols: tuple[str, ...]
    maintained_symbols: tuple[str, ...]
    no_longer_interesting_symbols: tuple[str, ...]
    risks: tuple[str, ...]


class TelegramMessageFormatter:
    @staticmethod
    def _decimal(value: Decimal) -> Decimal:
        if not isinstance(value, Decimal) or not value.is_finite():
            raise ValueError("valor de apresenta\u00e7\u00e3o deve ser Decimal finito")
        return value

    @staticmethod
    def _number(value: Decimal, *, signed: bool = False) -> str:
        rounded = TelegramMessageFormatter._decimal(value).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        text = f"{rounded:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"+{text}" if signed and rounded > 0 else text

    @staticmethod
    def _price(value: Decimal, currency_code: str) -> str:
        amount = TelegramMessageFormatter._number(value)
        prefixes = {"BRL": "R$", "USD": "US$", "EUR": "\u20ac"}
        prefix = prefixes.get(currency_code)
        return f"{prefix} {amount}" if prefix is not None else f"{currency_code} {amount}"

    @staticmethod
    def _symbols(symbols: tuple[str, ...]) -> str:
        return ", ".join(symbols) if symbols else "nenhuma"

    @staticmethod
    def _short_text(value: str, *, limit: int = 160) -> str:
        normalized = " ".join(value.split())
        return normalized if len(normalized) <= limit else normalized[: limit - 3].rstrip() + "..."

    @staticmethod
    def render_daily_summary(summary: DailyInvestmentSummary) -> str:
        if not isinstance(summary.closing_date, date):
            raise ValueError("closing_date deve ser date")
        if isinstance(summary.analyzed_assets, bool) or summary.analyzed_assets < 0:
            raise ValueError("analyzed_assets deve ser inteiro n\u00e3o negativo")
        lines = [
            f"FECHAMENTO DI\u00c1RIO \u2014 {summary.closing_date.strftime('%d/%m/%Y')}",
            "",
            f"Ativos analisados: {summary.analyzed_assets}",
            "",
        ]
        if summary.candidates:
            lines.append("Melhores oportunidades:")
            for candidate in summary.candidates:
                lines.extend(
                    [
                        f"\u2022 {candidate.symbol} \u2014 {candidate.level} | Score: {TelegramMessageFormatter._number(candidate.score)}",
                        "  " + " | ".join(
                            (
                                f"Pre\u00e7o: {TelegramMessageFormatter._price(candidate.price, candidate.currency_code)}",
                                f"Retorno: {TelegramMessageFormatter._number(candidate.return_value * Decimal('100'), signed=True)}%",
                                f"RSI: {TelegramMessageFormatter._number(candidate.rsi)}",
                                f"Volatilidade: {TelegramMessageFormatter._number(candidate.volatility * Decimal('100'))}%",
                            )
                        ),
                    ]
                )
                if candidate.gemini_summary is not None:
                    lines.append(
                        f"  Gemini: {TelegramMessageFormatter._short_text(candidate.gemini_summary)}"
                    )
                else:
                    lines.append("  Gemini: sem an\u00e1lise validada dispon\u00edvel.")
        else:
            lines.append("Nenhuma oportunidade relevante foi encontrada no fechamento de hoje.")
        lines.extend(
            [
                "",
                f"Novas: {TelegramMessageFormatter._symbols(summary.new_symbols)}",
                f"Mantidas: {TelegramMessageFormatter._symbols(summary.maintained_symbols)}",
                "Deixaram de ser interessantes: "
                f"{TelegramMessageFormatter._symbols(summary.no_longer_interesting_symbols)}",
                "",
                "Principais riscos: "
                + (
                    "; ".join(
                        TelegramMessageFormatter._short_text(risk, limit=80)
                        for risk in summary.risks[:5]
                    )
                    if summary.risks
                    else "nenhum risco registrado nas an\u00e1lises Gemini exibidas."
                ),
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def render_summary(summary: PipelineSummary) -> str:
        lines = [
            "ANÁLISE CONCLUÍDA",
            "",
            f"Ativos considerados: {summary.considered}",
            f"Analisados com sucesso: {summary.analyzed}",
            f"Ignorados/bloqueados: {summary.quality_blocked}",
        ]
        for level, count in summary.levels:
            lines.append(f"{level}: {count}")
        lines.extend(["", f"Melhores candidatos (até {len(summary.candidates)}):"])
        if summary.candidates:
            for candidate in summary.candidates:
                lines.append(f"• {candidate.symbol} — {candidate.level} (score {candidate.score})")
                for label, value in candidate.indicators:
                    lines.append(f"  {label}: {value}")
        else:
            lines.append("Nenhum ativo elegível para ranking nesta execução.")
        lines.extend(["", f"Critérios da policy {summary.policy_version}:"])
        lines.extend(f"• {criterion}" for criterion in summary.criteria)
        if not any(level in {"INTERESTING", "HIGH_INTEREST"} and count for level, count in summary.levels):
            lines.extend(["", "Nenhuma oportunidade atingiu os critérios completos nesta execução."])
        if summary.dry_run:
            lines.extend(["", "SIMULAÇÃO DRY-RUN — nenhuma mensagem foi enviada ao Telegram."])
        return "\n".join(lines)

    @staticmethod
    def render_opportunity_alert(content: OpportunityAlertContent) -> str:
        lines = [
            "OPORTUNIDADE DETECTADA",
            "",
            f"Ativo: {content.symbol}",
            f"Preço validado: {content.price}",
            f"Score: {content.score}",
            f"Nível: {content.level}",
            f"Dados referentes a: {content.timestamp}",
            "",
            "Indicadores:",
        ]
        lines.extend(f"- {label}: {value}" for label, value in content.indicators)
        if not content.indicators:
            lines.append("- indisponíveis")
        lines.extend(["", "Critérios atendidos:"])
        lines.extend(f"- {criterion}" for criterion in content.criteria)
        if content.ai_summary is not None:
            lines.extend(["", "Análise do Gemini:", f"- Resumo: {content.ai_summary}"])
            if content.positive_factors:
                lines.append("- Fatores positivos: " + ", ".join(content.positive_factors))
            if content.negative_factors:
                lines.append("- Fatores negativos: " + ", ".join(content.negative_factors))
            if content.risks:
                lines.append("- Riscos: " + ", ".join(content.risks))
        return "\n".join(lines)
