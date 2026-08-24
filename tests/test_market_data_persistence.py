from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.database.repositories.market_data import MarketQuoteRepository
from app.market_data.models import DataQuality, Quote


MIGRATIONS_DIR = Path("supabase/migrations")
ASSET_ID = UUID("11111111-1111-1111-1111-111111111111")
OBSERVED_AT = datetime(2026, 8, 21, 21, 31, 30, tzinfo=UTC)


class FakeResponse:
    def __init__(self, data):
        self.data = data


class PersistenceError(RuntimeError):
    code = "23505"
    constraint = "another_unique_constraint"


class FakeMarketQuotesRequest:
    def __init__(self, client):
        self._client = client
        self._filters = []

    def upsert(self, payload, **kwargs):
        self._upsert_payload = payload
        self._upsert_options = kwargs
        return self

    def select(self, *_columns):
        self._selecting = True
        return self

    def eq(self, column, value):
        self._filters.append((column, value))
        return self

    def limit(self, _size):
        return self

    def execute(self):
        if hasattr(self, "_upsert_payload"):
            if self._client.error is not None:
                raise self._client.error
            payload = self._upsert_payload
            self._client.upsert_calls.append((payload, self._upsert_options))
            identity = tuple(
                payload[column] for column in ("asset_id", "provider", "observed_at")
            )
            if any(
                tuple(row[column] for column in ("asset_id", "provider", "observed_at"))
                == identity
                for row in self._client.rows
            ):
                return FakeResponse([])
            row = {
                "id": str(uuid4()),
                **payload,
                "created_at": OBSERVED_AT.isoformat(),
            }
            self._client.rows.append(row)
            return FakeResponse([row])
        rows = [
            row
            for row in self._client.rows
            if all(row[column] == value for column, value in self._filters)
        ]
        return FakeResponse(rows)


class FakeMarketQuotesClient:
    def __init__(self, *, error=None):
        self.rows = []
        self.upsert_calls = []
        self.error = error

    def table(self, name):
        assert name == "market_quotes"
        return FakeMarketQuotesRequest(self)


def quote(*, observed_at=OBSERVED_AT, provider="brapi"):
    return Quote(
        ASSET_ID,
        "TEST3",
        Decimal("10.25"),
        "BRL",
        observed_at,
        observed_at,
        provider,
        DataQuality.VALID,
    )


def market_data_migration() -> Path:
    matches = sorted(MIGRATIONS_DIR.glob("*_create_market_data_tables.sql"))
    assert len(matches) == 1, "deve existir exatamente uma migration create_market_data_tables"
    return matches[0]


def migration() -> str:
    return " ".join(market_data_migration().read_text(encoding="utf-8").lower().split())


def test_market_data_migration_creates_precise_auditable_tables():
    sql = migration()
    for table in ("asset_provider_symbols", "market_quotes", "market_candles"):
        assert f"create table public.{table}" in sql
        assert f"alter table public.{table} enable row level security;" in sql
        assert f"revoke all privileges on table public.{table} from anon, authenticated, public;" in sql
        assert f"revoke all privileges on table public.{table} from service_role;" in sql
        assert f"grant select, insert, update, delete on table public.{table} to service_role;" in sql
    assert "price numeric(38,18) not null" in sql
    assert "open numeric(38,18) not null" in sql
    assert "market_quotes_identity_unique unique (asset_id, provider, observed_at)" in sql
    assert "market_candles_identity_unique unique (asset_id, provider, interval, observed_at)" in sql


def test_market_data_migration_has_constraints_without_policies_or_extra_grants():
    sql = migration()
    assert "on delete restrict" in sql
    assert "quality in ('valid', 'stale', 'incomplete', 'outlier', 'invalid')" in sql
    assert "interval in ('1m', '5m', '15m', '30m', '1h', '1d', '1wk', '1mo')" in sql
    assert "create policy" not in sql
    for privilege in ("truncate", "trigger", "references", "maintain"):
        assert f"grant {privilege}" not in sql


def test_market_quote_insert_is_atomic_idempotent_for_its_identity():
    client = FakeMarketQuotesClient()
    repository = MarketQuoteRepository(client)

    first = repository.create_from_quote(quote())
    duplicate = repository.create_from_quote(quote())

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.record.id == first.record.id
    assert len(client.rows) == 1
    assert all(
        options == {
            "on_conflict": "asset_id,provider,observed_at",
            "ignore_duplicates": True,
        }
        for _payload, options in client.upsert_calls
    )


def test_market_quote_identity_allows_different_timestamp_and_provider():
    client = FakeMarketQuotesClient()
    repository = MarketQuoteRepository(client)

    first = repository.create_from_quote(quote())
    different_timestamp = repository.create_from_quote(
        quote(observed_at=OBSERVED_AT + timedelta(seconds=1))
    )
    different_provider = repository.create_from_quote(quote(provider="twelve_data"))

    assert all(result.created for result in (first, different_timestamp, different_provider))
    assert len(client.rows) == 3


def test_market_quote_propagates_real_persistence_errors():
    error = PersistenceError("unexpected unique violation")
    with pytest.raises(PersistenceError, match="unexpected unique violation"):
        MarketQuoteRepository(FakeMarketQuotesClient(error=error)).create_from_quote(
            quote()
        )
