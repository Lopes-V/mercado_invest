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

import httpx

from app.security.redaction import sanitize_sensitive_text

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
    classification: AIClassification; confidence: Decimal; positive_factors: tuple[str,...]; negative_factors: tuple[str,...]; risks: tuple[str,...]; summary: str
    def __post_init__(self) -> None:
        if not isinstance(self.classification, AIClassification) or not isinstance(self.confidence, Decimal) or not self.confidence.is_finite() or not Decimal("0") <= self.confidence <= Decimal("1"): raise AIError("confidence/classification inválida")
        for field in ("positive_factors","negative_factors","risks"): object.__setattr__(self, field, _text_tuple(getattr(self,field),field))
        if not isinstance(self.summary,str) or not self.summary.strip(): raise AIError("summary não pode ser vazio")

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
        self._repository.create(analysis_id=analysis_id, asset_id=asset_id, provider=self._provider_name, model=self._model, prompt_version=self._prompt_version, started_at=started_at, finished_at=finished_at, duration_ms=int((finished_at-started_at).total_seconds()*1000), input_hash=self.input_hash(context), classification=response.classification.value, confidence=str(response.confidence), positive_factors=list(response.positive_factors), negative_factors=list(response.negative_factors), risks=list(response.risks), summary=response.summary, input_tokens=input_tokens, output_tokens=output_tokens)
        return response

class OpenAIResponsesProvider:
    """Minimal server-side Responses API adapter using strict structured output."""
    name="openai"
    def __init__(self, *, api_key: str, model: str, client: httpx.Client | None=None) -> None:
        if not isinstance(api_key,str) or not api_key.strip() or not isinstance(model,str) or not model.strip(): raise AIError("api_key e model são obrigatórios para OpenAI")
        self._key=api_key; self._model=model; self._client=client or httpx.Client(base_url="https://api.openai.com", timeout=httpx.Timeout(20), follow_redirects=False)
    def analyze(self, context: ValidatedAIContext) -> AIAnalysisResponse:
        schema={"type":"object","additionalProperties":False,"required":["classification","confidence","positive_factors","negative_factors","risks","summary"],"properties":{"classification":{"type":"string","enum":[item.value for item in AIClassification]},"confidence":{"type":"string"},"positive_factors":{"type":"array","items":{"type":"string"}},"negative_factors":{"type":"array","items":{"type":"string"}},"risks":{"type":"array","items":{"type":"string"}},"summary":{"type":"string"}}}
        facts={"asset":context.asset_identity,"market":context.market,"price":str(context.current_price),"currency":context.currency_code,"metrics":[[key,str(value)] for key,value in context.analysis_metrics],"timestamp":context.data_timestamp.isoformat(),"algorithm_version":context.algorithm_version}
        payload={"model":self._model,"store":False,"input":[{"role":"developer","content":"Use only supplied facts. Never invent prices, metrics, news or macro data. Never recommend buy or sell, and never change an opportunity score. Use INSUFFICIENT_EVIDENCE when facts are insufficient."},{"role":"user","content":json.dumps(facts)}],"text":{"format":{"type":"json_schema","name":"validated_ai_analysis","strict":True,"schema":schema}}}
        try: response=self._client.post("/v1/responses",headers={"Authorization":f"Bearer {self._key}"},json=payload); response.raise_for_status(); body=response.json()
        except (httpx.HTTPError, ValueError) as exc: raise AIError(f"OpenAI não respondeu de forma válida: {sanitize_sensitive_text(exc)}") from exc
        try:
            text=body["output"][0]["content"][0]["text"]; raw=json.loads(text)
            return AIAnalysisResponse(AIClassification(raw["classification"]),Decimal(raw["confidence"]),tuple(raw["positive_factors"]),tuple(raw["negative_factors"]),tuple(raw["risks"]),raw["summary"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc: raise AIError("OpenAI retornou resposta estruturada inválida") from exc
    def close(self)->None: self._client.close()
