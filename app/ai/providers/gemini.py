"""Google Gemini adapter for the provider-independent AI domain contract."""

import json
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

import httpx

from app.ai.core import (
    AIAnalysisResponse,
    AIClassification,
    AIError,
    ValidatedAIContext,
)
from app.security.redaction import sanitize_sensitive_text


_SYSTEM_INSTRUCTION = (
    "Use only the supplied facts. Never invent prices, indicators, news, or "
    "macroeconomic data. Never recommend BUY or SELL directly and never "
    "change an opportunity score. Return INSUFFICIENT_EVIDENCE when the "
    "facts are insufficient."
)


def _response_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "classification",
            "confidence",
            "positive_factors",
            "negative_factors",
            "risks",
            "summary",
        ],
        "properties": {
            "classification": {
                "type": "string",
                "enum": [item.value for item in AIClassification],
            },
            "confidence": {"type": "number"},
            "positive_factors": {
                "type": "array",
                "items": {"type": "string"},
            },
            "negative_factors": {
                "type": "array",
                "items": {"type": "string"},
            },
            "risks": {"type": "array", "items": {"type": "string"}},
            "summary": {"type": "string"},
        },
    }


def _facts(context: ValidatedAIContext) -> dict[str, object]:
    facts: dict[str, object] = {
        "asset": context.asset_identity,
        "market": context.market,
        "current_price": str(context.current_price),
        "currency": context.currency_code,
        "analysis_metrics": [
            [name, str(value)] for name, value in context.analysis_metrics
        ],
        "timestamp": context.data_timestamp.isoformat(),
        "algorithm_version": context.algorithm_version,
    }
    if context.portfolio_context is not None:
        facts["portfolio_context"] = context.portfolio_context
    if context.macro_context is not None:
        facts["macro_context"] = context.macro_context
    return facts


class GeminiProvider:
    """Server-side Gemini GenerateContent adapter using JSON Schema output."""

    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        client: httpx.Client | None = None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise AIError("api_key é obrigatória para Gemini")
        if not isinstance(model, str) or not model.strip():
            raise AIError("model é obrigatório para Gemini")

        self._api_key = api_key
        self._model = model
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url="https://generativelanguage.googleapis.com",
            timeout=httpx.Timeout(20.0),
            follow_redirects=False,
        )

    def analyze(self, context: ValidatedAIContext) -> AIAnalysisResponse:
        payload = {
            "systemInstruction": {"parts": [{"text": _SYSTEM_INSTRUCTION}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": json.dumps(_facts(context))}],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": _response_schema(),
            },
        }
        try:
            response = self._client.post(
                f"/v1beta/models/{self._model}:generateContent",
                headers={"x-goog-api-key": self._api_key},
                json=payload,
            )
            response.raise_for_status()
            body = json.loads(response.text, parse_float=Decimal)
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise AIError(
                "Gemini não respondeu de forma válida: "
                f"{sanitize_sensitive_text(exc)}"
            ) from exc

        return self._parse_response(body)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    @staticmethod
    def _parse_response(body: object) -> AIAnalysisResponse:
        if not isinstance(body, Mapping):
            raise AIError("Gemini retornou resposta inválida")
        prompt_feedback = body.get("promptFeedback")
        if isinstance(prompt_feedback, Mapping) and prompt_feedback.get(
            "blockReason"
        ):
            raise AIError("Gemini bloqueou a solicitação por segurança")

        candidates = body.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise AIError("Gemini não retornou candidate")
        candidate = candidates[0]
        if not isinstance(candidate, Mapping):
            raise AIError("Gemini retornou candidate inválido")
        if candidate.get("finishReason") != "STOP":
            raise AIError("Gemini não concluiu a resposta estruturada")

        content = candidate.get("content")
        if not isinstance(content, Mapping):
            raise AIError("Gemini retornou resposta sem conteúdo")
        parts = content.get("parts")
        if not isinstance(parts, list):
            raise AIError("Gemini retornou partes inválidas")
        text = next(
            (
                part.get("text")
                for part in parts
                if isinstance(part, Mapping) and isinstance(part.get("text"), str)
            ),
            None,
        )
        if not isinstance(text, str) or not text.strip():
            raise AIError("Gemini retornou conteúdo vazio")

        try:
            raw = json.loads(text, parse_float=Decimal)
            if not isinstance(raw, Mapping):
                raise TypeError("objeto estruturado esperado")
            confidence = raw["confidence"]
            if isinstance(confidence, bool) or not isinstance(
                confidence, (str, int, Decimal)
            ):
                raise TypeError("confidence inválida")
            positive_factors = raw["positive_factors"]
            negative_factors = raw["negative_factors"]
            risks = raw["risks"]
            if not all(
                isinstance(items, list)
                for items in (positive_factors, negative_factors, risks)
            ):
                raise TypeError("arrays estruturados inválidos")
            input_tokens, output_tokens = GeminiProvider._usage(body)
            return AIAnalysisResponse(
                classification=AIClassification(raw["classification"]),
                confidence=Decimal(str(confidence)),
                positive_factors=tuple(positive_factors),
                negative_factors=tuple(negative_factors),
                risks=tuple(risks),
                summary=raw["summary"],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            InvalidOperation,
            json.JSONDecodeError,
        ) as exc:
            raise AIError("Gemini retornou resposta estruturada inválida") from exc

    @staticmethod
    def _usage(body: Mapping[str, object]) -> tuple[int | None, int | None]:
        usage = body.get("usageMetadata")
        if usage is None:
            return None, None
        if not isinstance(usage, Mapping):
            raise AIError("Gemini retornou usage metadata inválido")

        def token_count(field: str) -> int | None:
            value = usage.get(field)
            if value is None:
                return None
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise AIError("Gemini retornou usage metadata inválido")
            return value

        return token_count("promptTokenCount"), token_count("candidatesTokenCount")
