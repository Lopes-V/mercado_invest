import os
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.ai import GeminiProvider, ValidatedAIContext


pytestmark = pytest.mark.integration


def test_gemini_live_structured_response() -> None:
    if os.getenv("RUN_GEMINI_INTEGRATION") != "1":
        pytest.skip("RUN_GEMINI_INTEGRATION=1 required")
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL")
    if not api_key:
        pytest.fail("GEMINI_API_KEY is required when RUN_GEMINI_INTEGRATION=1")
    if not model:
        pytest.fail("GEMINI_MODEL is required when RUN_GEMINI_INTEGRATION=1")

    provider = GeminiProvider(api_key=api_key, model=model)
    try:
        response = provider.analyze(
            ValidatedAIContext(
                asset_identity="TEST-ASSET",
                market="TEST-MARKET",
                current_price=Decimal("100.00"),
                currency_code="TST",
                analysis_metrics=(("RETURN", Decimal("0.01")),),
                data_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                algorithm_version="test-v1",
            )
        )
    finally:
        provider.close()

    assert Decimal("0") <= response.confidence <= Decimal("1")
    assert response.summary.strip()
