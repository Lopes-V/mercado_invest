"""AI interpretation of immutable, validated facts. It cannot supply prices or scores."""
import json
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

class AIError(ValueError): pass
class AIClassification(StrEnum): POSITIVE="POSITIVE"; NEUTRAL="NEUTRAL"; NEGATIVE="NEGATIVE"; INSUFFICIENT_EVIDENCE="INSUFFICIENT_EVIDENCE"

def _text_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) or not item.strip() for item in value): raise AIError(f"{field} deve conter textos não vazios")
    return tuple(value)

@dataclass(frozen=True, slots=True)
class ValidatedAIContext:
    asset_identity: str; market: str; current_price: Decimal; currency_code: str; analysis_metrics: tuple[tuple[str, Decimal], ...]; data_timestamp: datetime; algorithm_version: str; portfolio_context: str | None = None; macro_context: str | None = None
    def __post_init__(self) -> None:
        if not isinstance(self.current_price, Decimal) or not self.current_price.is_finite() or self.current_price < 0: raise AIError("current_price deve ser Decimal finito")
        if self.data_timestamp.tzinfo is None or self.data_timestamp.utcoffset() is None: raise AIError("data_timestamp deve possuir timezone")
        object.__setattr__(self, "data_timestamp", self.data_timestamp.astimezone(UTC))

@dataclass(frozen=True, slots=True)
class AIAnalysisResponse:
    classification: AIClassification; confidence: Decimal; positive_factors: tuple[str,...]; negative_factors: tuple[str,...]; risks: tuple[str,...]; summary: str; input_tokens: int | None = None; output_tokens: int | None = None
    def __post_init__(self) -> None:
        if not isinstance(self.classification, AIClassification) or not isinstance(self.confidence, Decimal) or not self.confidence.is_finite() or not Decimal("0") <= self.confidence <= Decimal("1"): raise AIError("confidence/classification inválida")
        for field in ("positive_factors","negative_factors","risks"): object.__setattr__(self, field, _text_tuple(getattr(self,field),field))
        if not isinstance(self.summary,str) or not self.summary.strip(): raise AIError("summary não pode ser vazio")
        for field in ("input_tokens", "output_tokens"):
            value = getattr(self, field)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise AIError(f"{field} deve ser inteiro não negativo")

class AIProvider(Protocol):
    def analyze(self, context: ValidatedAIContext) -> AIAnalysisResponse: ...

class AIRunRepository(Protocol):
    def create(self, **payload): ...

class AIService:
    def __init__(self, *, provider: AIProvider, repository: AIRunRepository, provider_name: str, model: str, prompt_version: str) -> None:
        self._provider, self._repository, self._provider_name, self._model, self._prompt_version = provider, repository, provider_name, model, prompt_version

    @staticmethod
    def input_hash(context: ValidatedAIContext) -> str:
        payload = json.dumps({"asset": context.asset_identity, "market": context.market, "price": str(context.current_price), "currency": context.currency_code, "metrics": [(key, str(value)) for key, value in context.analysis_metrics], "timestamp": context.data_timestamp.isoformat(), "algorithm": context.algorithm_version}, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def analyze(self, *, context: ValidatedAIContext, asset_id: UUID, started_at: datetime, finished_at: datetime, analysis_id: UUID | None = None, input_tokens: int | None = None, output_tokens: int | None = None) -> AIAnalysisResponse:
        if started_at.tzinfo is None or finished_at.tzinfo is None or finished_at < started_at: raise AIError("timestamps de AI inválidos")
        response = self._provider.analyze(context)
        if not isinstance(response, AIAnalysisResponse): raise AIError("provider AI retornou tipo inválido")
        self._repository.create(analysis_id=analysis_id, asset_id=asset_id, provider=self._provider_name, model=self._model, prompt_version=self._prompt_version, started_at=started_at, finished_at=finished_at, duration_ms=int((finished_at-started_at).total_seconds()*1000), input_hash=self.input_hash(context), classification=response.classification.value, confidence=str(response.confidence), positive_factors=list(response.positive_factors), negative_factors=list(response.negative_factors), risks=list(response.risks), summary=response.summary, input_tokens=input_tokens if input_tokens is not None else response.input_tokens, output_tokens=output_tokens if output_tokens is not None else response.output_tokens)
        return response
