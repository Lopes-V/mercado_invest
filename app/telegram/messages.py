from dataclasses import dataclass


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


class TelegramMessageFormatter:
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
