from uuid import UUID

import pytest

from app.database.models import RepositoryDataError
from app.database.repositories import (
    AssetRepository,
    CurrencyRepository,
    ExchangeRepository,
    MarketRepository,
)


CURRENCY_ID = UUID("11111111-1111-1111-1111-111111111111")
MARKET_ID = UUID("22222222-2222-2222-2222-222222222222")
EXCHANGE_ID = UUID("33333333-3333-3333-3333-333333333333")
ASSET_ID = UUID("44444444-4444-4444-4444-444444444444")
TIMESTAMP = "2026-08-17T12:00:00+00:00"


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeRequest:
    def __init__(self, response, error=None):
        self.response = response
        self.error = error
        self.operations = []

    def insert(self, payload):
        self.operations.append(("insert", payload))
        return self

    def select(self, *columns):
        self.operations.append(("select", columns))
        return self

    def eq(self, column, value):
        self.operations.append(("eq", column, value))
        return self

    def is_(self, column, value):
        self.operations.append(("is_", column, value))
        return self

    def limit(self, size):
        self.operations.append(("limit", size))
        return self

    def execute(self):
        self.operations.append(("execute",))
        if self.error is not None:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, response, error=None):
        self.response = response
        self.error = error
        self.requests = []

    def table(self, table_name):
        request = FakeRequest(self.response, self.error)
        self.requests.append((table_name, request))
        return request


def currency_row(**changes):
    row = {
        "id": str(CURRENCY_ID),
        "code": "TST001",
        "name": "Test currency",
        "symbol": None,
        "decimal_places": 2,
        "is_active": True,
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
    }
    row.update(changes)
    return row


def market_row(**changes):
    row = {
        "id": str(MARKET_ID),
        "code": "TEST",
        "name": "Test market",
        "country_code": None,
        "default_currency_id": str(CURRENCY_ID),
        "is_active": True,
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
    }
    row.update(changes)
    return row


def exchange_row(**changes):
    row = {
        "id": str(EXCHANGE_ID),
        "market_id": str(MARKET_ID),
        "code": "TESTEX",
        "name": "Test exchange",
        "mic": None,
        "timezone": "UTC",
        "is_active": True,
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
    }
    row.update(changes)
    return row


def asset_row(**changes):
    row = {
        "id": str(ASSET_ID),
        "market_id": str(MARKET_ID),
        "exchange_id": str(EXCHANGE_ID),
        "currency_id": str(CURRENCY_ID),
        "symbol": "TEST.A",
        "name": "Test asset",
        "asset_type": "STOCK",
        "isin": None,
        "is_active": True,
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
    }
    row.update(changes)
    return row


def last_request(client):
    return client.requests[-1]


def test_currency_create_sends_database_payload_and_parses_row():
    client = FakeClient(FakeResponse([currency_row(symbol="¤")]))

    record = CurrencyRepository(client).create(
        code="TST001",
        name="Test currency",
        symbol="¤",
        decimal_places=3,
        is_active=False,
    )

    table, request = last_request(client)
    assert table == "currencies"
    assert request.operations[0] == (
        "insert",
        {
            "code": "TST001",
            "name": "Test currency",
            "symbol": "¤",
            "decimal_places": 3,
            "is_active": False,
        },
    )
    assert record.id == CURRENCY_ID
    assert record.symbol == "¤"
    assert record.created_at.tzinfo is not None


def test_currency_lookup_handles_found_and_empty_responses():
    found_client = FakeClient(FakeResponse([currency_row()]))
    found = CurrencyRepository(found_client).get_by_id(CURRENCY_ID)

    assert found is not None
    assert found.id == CURRENCY_ID
    assert ("eq", "id", str(CURRENCY_ID)) in last_request(found_client)[1].operations

    empty_client = FakeClient(FakeResponse([]))
    assert CurrencyRepository(empty_client).get_by_code("TST001") is None
    assert ("eq", "code", "TST001") in last_request(empty_client)[1].operations


def test_market_create_and_lookup_by_code_preserve_nullable_fields():
    client = FakeClient(FakeResponse([market_row()]))

    created = MarketRepository(client).create(
        code="TEST",
        name="Test market",
        default_currency_id=CURRENCY_ID,
    )
    assert created.country_code is None
    assert last_request(client)[1].operations[0] == (
        "insert",
        {
            "code": "TEST",
            "name": "Test market",
            "is_active": True,
            "default_currency_id": str(CURRENCY_ID),
        },
    )

    lookup_client = FakeClient(FakeResponse([market_row(country_code="ZZ")]))
    found = MarketRepository(lookup_client).get_by_code("TEST")
    assert found is not None
    assert found.country_code == "ZZ"
    assert ("eq", "code", "TEST") in last_request(lookup_client)[1].operations


def test_market_lookup_by_id_uses_primary_key():
    client = FakeClient(FakeResponse([market_row()]))

    record = MarketRepository(client).get_by_id(MARKET_ID)

    assert record is not None
    assert record.id == MARKET_ID
    assert ("eq", "id", str(MARKET_ID)) in last_request(client)[1].operations


def test_exchange_create_and_market_code_lookup_use_canonical_key():
    client = FakeClient(FakeResponse([exchange_row(mic="TST1")]))

    created = ExchangeRepository(client).create(
        market_id=MARKET_ID,
        code="TESTEX",
        name="Test exchange",
        timezone="UTC",
        mic="TST1",
    )
    assert created.mic == "TST1"
    assert last_request(client)[1].operations[0] == (
        "insert",
        {
            "market_id": str(MARKET_ID),
            "code": "TESTEX",
            "name": "Test exchange",
            "timezone": "UTC",
            "is_active": True,
            "mic": "TST1",
        },
    )

    lookup_client = FakeClient(FakeResponse([exchange_row()]))
    found = ExchangeRepository(lookup_client).get_by_market_and_code(
        MARKET_ID, "TESTEX"
    )
    assert found is not None
    assert ("eq", "market_id", str(MARKET_ID)) in last_request(lookup_client)[1].operations
    assert ("eq", "code", "TESTEX") in last_request(lookup_client)[1].operations


def test_exchange_lookup_by_id_uses_primary_key():
    client = FakeClient(FakeResponse([exchange_row()]))

    record = ExchangeRepository(client).get_by_id(EXCHANGE_ID)

    assert record is not None
    assert record.id == EXCHANGE_ID
    assert ("eq", "id", str(EXCHANGE_ID)) in last_request(client)[1].operations


def test_asset_create_and_identity_lookup_with_exchange():
    client = FakeClient(FakeResponse([asset_row(isin="ZZ0000000001")]))

    created = AssetRepository(client).create(
        market_id=MARKET_ID,
        exchange_id=EXCHANGE_ID,
        currency_id=CURRENCY_ID,
        symbol="TEST.A",
        name="Test asset",
        asset_type="STOCK",
        isin="ZZ0000000001",
    )
    assert created.exchange_id == EXCHANGE_ID
    assert last_request(client)[1].operations[0] == (
        "insert",
        {
            "market_id": str(MARKET_ID),
            "exchange_id": str(EXCHANGE_ID),
            "currency_id": str(CURRENCY_ID),
            "symbol": "TEST.A",
            "name": "Test asset",
            "asset_type": "STOCK",
            "is_active": True,
            "isin": "ZZ0000000001",
        },
    )

    lookup_client = FakeClient(FakeResponse([asset_row()]))
    found = AssetRepository(lookup_client).get_by_identity(
        market_id=MARKET_ID,
        exchange_id=EXCHANGE_ID,
        currency_id=CURRENCY_ID,
        symbol="TEST.A",
    )
    assert found is not None
    assert ("eq", "exchange_id", str(EXCHANGE_ID)) in last_request(lookup_client)[1].operations


def test_asset_identity_lookup_without_exchange_uses_is_null_filter():
    client = FakeClient(FakeResponse([asset_row(exchange_id=None)]))

    found = AssetRepository(client).get_by_identity(
        market_id=MARKET_ID,
        exchange_id=None,
        currency_id=CURRENCY_ID,
        symbol="TEST_NOEX",
    )

    assert found is not None
    assert found.exchange_id is None
    operations = last_request(client)[1].operations
    assert ("is_", "exchange_id", "null") in operations
    assert not any(
        operation[:2] == ("eq", "exchange_id")
        for operation in operations
    )


def test_asset_lookup_by_id_and_isin_use_their_canonical_filters():
    id_client = FakeClient(FakeResponse([asset_row()]))
    by_id = AssetRepository(id_client).get_by_id(ASSET_ID)
    assert by_id is not None
    assert ("eq", "id", str(ASSET_ID)) in last_request(id_client)[1].operations

    isin_client = FakeClient(FakeResponse([asset_row(isin="ZZ0000000001")]))
    by_isin = AssetRepository(isin_client).get_by_isin("ZZ0000000001")
    assert by_isin is not None
    assert ("eq", "isin", "ZZ0000000001") in last_request(isin_client)[1].operations


def test_duplicate_response_for_unique_lookup_is_rejected():
    client = FakeClient(FakeResponse([currency_row(), currency_row()]))

    with pytest.raises(RepositoryDataError, match="mais de um"):
        CurrencyRepository(client).get_by_code("TST001")


def test_malformed_response_is_rejected():
    client = FakeClient(FakeResponse([currency_row(id="not-a-uuid")]))

    with pytest.raises(RepositoryDataError, match="UUID inválido"):
        CurrencyRepository(client).get_by_code("TST001")


def test_create_requires_exactly_one_returned_row():
    client = FakeClient(FakeResponse([]))

    with pytest.raises(RepositoryDataError, match="exatamente um"):
        CurrencyRepository(client).create(
            code="TST001", name="Test currency"
        )


def test_client_errors_propagate_without_conversion_to_not_found():
    client = FakeClient(FakeResponse([]), error=RuntimeError("network failure"))

    with pytest.raises(RuntimeError, match="network failure"):
        AssetRepository(client).get_by_id(ASSET_ID)
