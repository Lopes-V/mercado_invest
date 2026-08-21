from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.ai import AIAnalysisResponse, AIClassification, AIService, ValidatedAIContext


NOW = datetime(2026, 8, 21, tzinfo=UTC)


class Provider:
    def analyze(self, _context):
        return AIAnalysisResponse(
            AIClassification.NEUTRAL,
            Decimal("0.5"),
            ("factor",),
            (),
            ("risk",),
            "summary",
            input_tokens=12,
            output_tokens=7,
        )


class Repository:
    def create(self, **payload):
        self.payload = payload
        return SimpleNamespace(id=uuid4(), **payload)


def test_analyze_live_measures_real_provider_window_and_persists_usage():
    times = iter((NOW, NOW + timedelta(milliseconds=2500)))
    repository = Repository()
    service = AIService(
        provider=Provider(),
        repository=repository,
        provider_name="gemini",
        model="gemini-test",
        prompt_version="v1",
        clock=lambda: next(times),
    )
    asset_id = uuid4()
    response = service.analyze_live(
        context=ValidatedAIContext(
            asset_identity="TEST",
            market="TEST",
            current_price=Decimal("10"),
            currency_code="USD",
            analysis_metrics=(("RETURN", Decimal("0.01")),),
            data_timestamp=NOW,
            algorithm_version="analysis-v1",
        ),
        asset_id=asset_id,
    )
    assert response.classification is AIClassification.NEUTRAL
    assert repository.payload["duration_ms"] == 2500
    assert repository.payload["input_tokens"] == 12
    assert repository.payload["output_tokens"] == 7
