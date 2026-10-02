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
    AIResponseError,
    AIService,
    AIUnavailableError,
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


def _provider(
    transport: httpx.MockTransport,
    *,
    retry_delays: tuple[float, float] = (0, 0),
    sleeper=lambda _delay: None,
) -> GeminiProvider:
    return GeminiProvider(
        api_key=_API_KEY,
        model=_MODEL,
        retry_delays=retry_delays,
        sleeper=sleeper,
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


def _sequence(*outcomes: int | Exception) -> tuple[httpx.MockTransport, list[int]]:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        outcome = outcomes[len(calls) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return httpx.Response(
            outcome,
            json=_body() if outcome == 200 else {"error": "failed"},
            request=request,
        )

    return httpx.MockTransport(handler), calls


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
        with pytest.raises(AIResponseError):
            provider.analyze(_CONTEXT)
    finally:
        provider.close()


def test_gemini_rejects_invalid_generated_json() -> None:
    body = _body()
    body["candidates"][0]["content"]["parts"][0]["text"] = "not-json"
    provider = _provider(_response(body))
    try:
        with pytest.raises(AIResponseError, match="estruturada inválida"):
            provider.analyze(_CONTEXT)
    finally:
        provider.close()


def test_gemini_retries_503_until_valid_response() -> None:
    transport, calls = _sequence(503, 503, 200)
    delays: list[float] = []
    provider = _provider(
        transport,
        retry_delays=(1, 2),
        sleeper=delays.append,
    )
    try:
        response = provider.analyze(_CONTEXT)
    finally:
        provider.close()

    assert response.classification is AIClassification.NEUTRAL
    assert len(calls) == 3
    assert delays == [1, 2]


def test_gemini_reports_unavailable_after_three_503_responses() -> None:
    transport, calls = _sequence(503, 503, 503)
    provider = _provider(transport)
    try:
        with pytest.raises(AIUnavailableError):
            provider.analyze(_CONTEXT)
    finally:
        provider.close()

    assert len(calls) == 3


def test_gemini_retries_429_until_valid_response() -> None:
    transport, calls = _sequence(429, 200)
    provider = _provider(transport)
    try:
        response = provider.analyze(_CONTEXT)
    finally:
        provider.close()

    assert response.classification is AIClassification.NEUTRAL
    assert len(calls) == 2


def test_gemini_retries_timeout_until_valid_response() -> None:
    timeout = httpx.ReadTimeout(
        "timeout",
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
    )
    transport, calls = _sequence(timeout, 200)
    provider = _provider(transport)
    try:
        response = provider.analyze(_CONTEXT)
    finally:
        provider.close()

    assert response.classification is AIClassification.NEUTRAL
    assert len(calls) == 2


def test_gemini_retries_connection_error_until_valid_response() -> None:
    connection_error = httpx.ConnectError(
        "network unavailable",
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
    )
    transport, calls = _sequence(connection_error, 200)
    provider = _provider(transport)
    try:
        response = provider.analyze(_CONTEXT)
    finally:
        provider.close()

    assert response.classification is AIClassification.NEUTRAL
    assert len(calls) == 2


def test_gemini_does_not_retry_401() -> None:
    transport, calls = _sequence(401, 200)
    provider = _provider(transport)
    try:
        with pytest.raises(AIResponseError):
            provider.analyze(_CONTEXT)
    finally:
        provider.close()

    assert len(calls) == 1


@pytest.mark.parametrize(
    "retry_delays",
    [
        (float("nan"), 1),
        (1, float("inf")),
    ],
)
def test_gemini_rejects_non_finite_retry_delays(
    retry_delays: tuple[float, float],
) -> None:
    with pytest.raises(AIError, match="retry_delays"):
        GeminiProvider(
            api_key=_API_KEY,
            model=_MODEL,
            retry_delays=retry_delays,
        )


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (400, AIResponseError),
        (401, AIResponseError),
        (429, AIUnavailableError),
        (500, AIUnavailableError),
    ],
)
def test_gemini_sanitizes_http_errors(status_code: int, error_type: type[AIError]) -> None:
    provider = _provider(_response({"error": "failed"}, status_code))
    try:
        with pytest.raises(error_type) as exc_info:
            provider.analyze(_CONTEXT)
    finally:
        provider.close()

    assert _API_KEY not in str(exc_info.value)


def test_gemini_sanitizes_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    provider = _provider(httpx.MockTransport(handler))
    try:
        with pytest.raises(AIUnavailableError) as exc_info:
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
    instruction = payload["systemInstruction"]["parts"][0]["text"]
    assert "Portugu\u00eas do Brasil" in instruction


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
