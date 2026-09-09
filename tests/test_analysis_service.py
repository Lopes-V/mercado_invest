from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

from app.analysis import AnalysisEngine, AnalysisService
from app.market_data.models import CandleInterval


ASSET_ID = UUID("11111111-1111-1111-1111-111111111111")
NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)


class Candles:
    def get_range(self, **_kwargs):
        return tuple(
            SimpleNamespace(
                asset_id=ASSET_ID,
                provider_symbol="TEST3",
                observed_at=NOW + timedelta(days=offset),
                open=Decimal("10"),
                high=Decimal("11"),
                low=Decimal("9"),
                close=Decimal(str(10 + offset)),
                volume=Decimal("100"),
                provider="brapi",
                received_at=NOW + timedelta(days=offset),
                quality="VALID",
                adjusted_close=None,
            )
            for offset in range(2)
        )


class Analyses:
    def __init__(self):
        self.record = SimpleNamespace(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            reference_at=NOW + timedelta(days=1),
        )

    def create(self, **_kwargs):
        return self.record


class Metrics:
    def create_many(self, **_kwargs):
        return ()


def test_analyze_persisted_returns_the_exact_analysis_record_created():
    analyses = Analyses()
    service = AnalysisService(
        candles=Candles(),
        engine=AnalysisEngine(),
        analyses=analyses,
        metrics=Metrics(),
    )

    persisted = service.analyze_persisted(
        asset_id=ASSET_ID,
        provider="brapi",
        interval=CandleInterval.ONE_DAY,
        start=NOW,
        end=NOW + timedelta(days=1),
        period=1,
    )

    assert persisted.record is analyses.record
    assert persisted.result.asset_id == ASSET_ID
