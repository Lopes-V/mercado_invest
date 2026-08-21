from datetime import UTC,datetime
from decimal import Decimal
import pytest
from app.ai import AIAnalysisResponse,AIClassification,AIError,ValidatedAIContext
from app.security import sanitize_sensitive_text
def test_ai_domain_validation_and_secret_redaction():
    response=AIAnalysisResponse(AIClassification.NEUTRAL,Decimal("0.5"),(),(),("volatility",),"facts only")
    assert response.confidence==Decimal("0.5")
    assert "secret" not in sanitize_sensitive_text("Bearer abcdefgh token=secret")
    with pytest.raises(AIError):AIAnalysisResponse(AIClassification.NEUTRAL,Decimal("1.1"),(),(),(),"x")
def test_context_requires_decimal_price():
    with pytest.raises(AIError):ValidatedAIContext("a","m",1,"USD",(),datetime.now(UTC),"v")
