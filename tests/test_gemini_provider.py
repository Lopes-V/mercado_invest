import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

from app.ai import (
    AIAnalysisResponse,
    AIClassification,
    AIError,
    AIService,
    GeminiProvider,
    ValidatedAIContext,
)


_API_KEY = "test-gemini-key-not-a-secret"
_MODEL = "gemini-test-model"
_CONTEXT = ValidatedAIContext(
    asset_identity="TEST-ASSET",
    market="TEST-MARKET",
    current_price=Decimal("123.450000000000000001"),
    currency_code="TST",
    analysis_metrics=(("RETURN", Decimal("0.010000000000000001")),),
    data_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    algorithm_version="analysis-test-v1",
    portfolio_context="validated test portfolio",
)


def _body(
    *,
    classification: str = "NEUTRAL",
    confidence: str = "0.5",
    positive_factors: object = (),
    negative_factors: object = (),
    risks: object = ("test risk",),
    summary: object = "test summary",
    finish_reason: str = "STOP",
) -> dict[str, object]:
    text = json.dumps(
        {
            "classification": classification,
            "confidence": confidence,
            "positive_factors": positive_factors,
            "negative_factors": negative_factors,
            "risks": risks,
            "summary": summary,
        }
    )
    return {
        "candidates": [
            {
                "finishReason": finish_reason,
                "content": {"parts": [{"text": text}]},
            }
        ],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
    }


def _provider(transport: httpx.MockTransport) -> GeminiProvider:
    return GeminiProvider(
        api_key=_API_KEY,
        model=_MODEL,
        client=httpx.Client(
            base_url="https://generativelanguage.googleapis.com",
            transport=transport,
            timeout=httpx.Timeout(5.0),
            follow_redirects=False,
        ),
    )


def _response(body: object, status_code: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=body, request=request)

    return httpx.MockTransport(handler)


@pytest.mark.parametrize(
    ("classification", "confidence"),
    [
        ("POSITIVE", "0"),
        ("NEUTRAL", "0.25"),
        ("NEGATIVE", "0.75"),
        ("INSUFFICIENT_EVIDENCE", "1"),
    ],
)
def test_gemini_accepts_each_valid_classification(
    classification: str, confidence: str
) -> None:
    provider = _provider(_response(_body(classification=classification, confidence=confidence)))
    try:
        response = provider.analyze(_CONTEXT)
    finally:
        provider.close()

    assert response.classification.value == classification
    assert response.confidence == Decimal(confidence)
    assert response.input_tokens == 10
    assert response.output_tokens == 5


def test_gemini_preserves_decimal_json_number_without_float_round_trip() -> None:
    body = _body()
    body["candidates"][0]["content"]["parts"][0]["text"] = (
        '{"classification":"NEUTRAL","confidence":0.123456789012345678,'
        '"positive_factors":[],"negative_factors":[],"risks":["risk"],'
        '"summary":"summary"}'
    )
    provider = _provider(_response(body))
    try:
        response = provider.analyze(_CONTEXT)
    finally:
        provider.close()

    assert response.confidence == Decimal("0.123456789012345678")


@pytest.mark.parametrize(
    "body",
    [
        _body(confidence="-0.01"),
        _body(confidence="1.01"),
        _body(classification="UNKNOWN"),
        _body(summary=""),
        _body(positive_factors=[""]),
        _body(risks="not-an-array"),
        _body(finish_reason="SAFETY"),
        {"promptFeedback": {"blockReason": "SAFETY"}},
        {"candidates": []},
        {"candidates": [{"finishReason": "STOP", "content": {"parts": []}}]},
    ],
)
def test_gemini_rejects_invalid_or_refused_structured_responses(body: object) -> None:
    provider = _provider(_response(body))
    try:
        with pytest.raises(AIError):
            provider.analyze(_CONTEXT)
    finally:
        provider.close()


def test_gemini_rejects_invalid_generated_json() -> None:
    body = _body()
    body["candidates"][0]["content"]["parts"][0]["text"] = "not-json"
    provider = _provider(_response(body))
    try:
        with pytest.raises(AIError, match="estruturada inválida"):
            provider.analyze(_CONTEXT)
    finally:
        provider.close()


@pytest.mark.parametrize("status_code", [400, 401, 429, 500])
def test_gemini_sanitizes_http_errors(status_code: int) -> None:
    provider = _provider(_response({"error": "failed"}, status_code))
    try:
        with pytest.raises(AIError) as exc_info:
            provider.analyze(_CONTEXT)
    finally:
        provider.close()

    assert _API_KEY not in str(exc_info.value)


def test_gemini_sanitizes_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    provider = _provider(httpx.MockTransport(handler))
    try:
        with pytest.raises(AIError) as exc_info:
            provider.analyze(_CONTEXT)
    finally:
        provider.close()

    assert _API_KEY not in str(exc_info.value)


def test_gemini_uses_header_generate_content_model_and_structured_schema() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json=_body(), request=request)

    provider = _provider(httpx.MockTransport(handler))
    try:
        provider.analyze(_CONTEXT)
    finally:
        provider.close()

    headers = captured["headers"]
    payload = captured["payload"]
    assert captured["url"].endswith(f"/v1beta/models/{_MODEL}:generateContent")
    assert "api_key" not in captured["url"]
    assert headers["x-goog-api-key"] == _API_KEY
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
    assert payload["generationConfig"]["responseJsonSchema"]["properties"]["classification"]["enum"] == [
        item.value for item in AIClassification
    ]
    facts = json.loads(payload["contents"][0]["parts"][0]["text"])
    assert facts["current_price"] == str(_CONTEXT.current_price)
    assert facts["analysis_metrics"] == [["RETURN", "0.010000000000000001"]]
    assert "opportunity_score" not in facts
    assert "quality" not in facts


def test_gemini_own_client_closes() -> None:
    provider = GeminiProvider(api_key=_API_KEY, model=_MODEL)
    provider.close()
    assert provider._client.is_closed


def test_ai_service_persists_gemini_provider_and_validated_response() -> None:
    payload: dict[str, object] = {}

    class Repository:
        def create(self, **kwargs: object) -> None:
            payload.update(kwargs)

    class Provider:
        def analyze(self, context: ValidatedAIContext) -> AIAnalysisResponse:
            assert context is _CONTEXT
            return AIAnalysisResponse(
                AIClassification.NEUTRAL,
                Decimal("0.5"),
                (),
                (),
                ("test risk",),
                "test summary",
                12,
                4,
            )

    service = AIService(
        provider=Provider(),
        repository=Repository(),
        provider_name="gemini",
        model=_MODEL,
        prompt_version="gemini-v1",
    )
    response = service.analyze(
        context=_CONTEXT,
        asset_id=uuid4(),
        started_at=_CONTEXT.data_timestamp,
        finished_at=_CONTEXT.data_timestamp,
    )

    assert response.confidence == Decimal("0.5")
    assert payload["provider"] == "gemini"
    assert payload["model"] == _MODEL
    assert payload["confidence"] == "0.5"
    assert payload["input_hash"] == AIService.input_hash(_CONTEXT)
    assert payload["input_tokens"] == 12
    assert payload["output_tokens"] == 4
