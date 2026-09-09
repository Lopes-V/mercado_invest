from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.database.repositories.stage_records import (
    AIRunRepository,
    AlertRepository,
    AnalysisRepository,
    OpportunityRepository,
)


ASSET_ID = UUID("11111111-1111-1111-1111-111111111111")
ANALYSIS_ID = UUID("22222222-2222-2222-2222-222222222222")
OPPORTUNITY_ID = UUID("33333333-3333-3333-3333-333333333333")
EARLIER = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
LATER = EARLIER + timedelta(minutes=1)


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeRequest:
    def __init__(self, rows):
        self._rows = rows
        self._filters = []
        self._order = None
        self._limit = None

    def select(self, *_columns):
        return self

    def eq(self, column, value):
        self._filters.append((column, value))
        return self

    def order(self, column, *, desc=False):
        self._order = (column, desc)
        return self

    def limit(self, size):
        self._limit = size
        return self

    def execute(self):
        rows = [
            row
            for row in self._rows
            if all(row[column] == value for column, value in self._filters)
        ]
        if self._order is not None:
            column, desc = self._order
            rows.sort(key=lambda row: row[column], reverse=desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        return FakeResponse(rows)


class FakeClient:
    def __init__(self, tables):
        self._tables = tables

    def table(self, name):
        return FakeRequest(self._tables[name])


def test_analysis_get_latest_returns_most_recent():
    earlier_id = UUID("44444444-4444-4444-4444-444444444444")
    latest_id = UUID("55555555-5555-5555-5555-555555555555")
    repository = AnalysisRepository(
        FakeClient(
            {
                "analyses": [
                    {
                        "id": str(earlier_id),
                        "asset_id": str(ASSET_ID),
                        "interval": "1d",
                        "reference_at": EARLIER.isoformat(),
                        "algorithm_version": "v1",
                        "created_at": EARLIER.isoformat(),
                    },
                    {
                        "id": str(latest_id),
                        "asset_id": str(ASSET_ID),
                        "interval": "1d",
                        "reference_at": LATER.isoformat(),
                        "algorithm_version": "v1",
                        "created_at": LATER.isoformat(),
                    },
                ]
            }
        )
    )

    assert repository.get_latest_for_asset(ASSET_ID, "1d").id == latest_id


def test_ai_run_get_latest_returns_most_recent():
    earlier_id = UUID("66666666-6666-6666-6666-666666666666")
    latest_id = UUID("77777777-7777-7777-7777-777777777777")
    repository = AIRunRepository(
        FakeClient(
            {
                "ai_runs": [
                    {
                        "id": str(earlier_id),
                        "asset_id": str(ASSET_ID),
                        "provider": "gemini",
                        "model": "model",
                        "classification": "POSITIVE",
                        "confidence": "0.7",
                        "summary": "earlier",
                        "started_at": EARLIER.isoformat(),
                        "finished_at": EARLIER.isoformat(),
                        "created_at": EARLIER.isoformat(),
                    },
                    {
                        "id": str(latest_id),
                        "asset_id": str(ASSET_ID),
                        "provider": "gemini",
                        "model": "model",
                        "classification": "POSITIVE",
                        "confidence": "0.7",
                        "summary": "latest",
                        "started_at": LATER.isoformat(),
                        "finished_at": LATER.isoformat(),
                        "created_at": LATER.isoformat(),
                    },
                ]
            }
        )
    )

    assert repository.get_latest_for_asset(ASSET_ID).id == latest_id


def test_opportunity_get_latest_returns_most_recent():
    earlier_id = UUID("88888888-8888-8888-8888-888888888888")
    latest_id = UUID("99999999-9999-9999-9999-999999999999")
    repository = OpportunityRepository(
        FakeClient(
            {
                "opportunities": [
                    {
                        "id": str(earlier_id),
                        "asset_id": str(ASSET_ID),
                        "analysis_id": str(ANALYSIS_ID),
                        "level": "WATCH",
                        "score": "50",
                        "evidence_count": 2,
                        "evaluated_at": EARLIER.isoformat(),
                        "policy_version": "candidate-v1",
                        "created_at": EARLIER.isoformat(),
                    },
                    {
                        "id": str(latest_id),
                        "asset_id": str(ASSET_ID),
                        "analysis_id": str(ANALYSIS_ID),
                        "level": "WATCH",
                        "score": "50",
                        "evidence_count": 2,
                        "evaluated_at": LATER.isoformat(),
                        "policy_version": "candidate-v1",
                        "created_at": LATER.isoformat(),
                    },
                ]
            }
        )
    )

    assert repository.get_latest_for_asset(ASSET_ID).id == latest_id


def test_alert_get_latest_sent_returns_most_recent():
    earlier_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    latest_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    repository = AlertRepository(
        FakeClient(
            {
                "alerts": [
                    {
                        "id": str(earlier_id),
                        "asset_id": str(ASSET_ID),
                        "opportunity_id": str(OPPORTUNITY_ID),
                        "channel": "telegram",
                        "status": "SENT",
                        "dedupe_key": "earlier",
                        "decided_at": EARLIER.isoformat(),
                        "sent_at": EARLIER.isoformat(),
                    },
                    {
                        "id": str(latest_id),
                        "asset_id": str(ASSET_ID),
                        "opportunity_id": str(OPPORTUNITY_ID),
                        "channel": "telegram",
                        "status": "SENT",
                        "dedupe_key": "latest",
                        "decided_at": LATER.isoformat(),
                        "sent_at": LATER.isoformat(),
                    },
                ]
            }
        )
    )

    assert repository.get_latest_sent_for_asset(ASSET_ID).id == latest_id
