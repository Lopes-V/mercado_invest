from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from app.market_data.contracts import (
    AssetSearchRequest,
    HistoryRequest,
    MarketDataProvider,
    MarketStatusRequest,
    QuoteRequest,
)
from app.market_data.errors import MarketDataValidationError
from app.market_data.models import (
    Candle,
    CandleInterval,
    MarketSessionStatus,
    MarketStatus,
    ProviderAsset,
    Quote,
)


ASSET_ID = UUID("11111111-1111-1111-1111-111111111111")
MARKET_ID = UUID("22222222-2222-2222-2222-222222222222")
EXCHANGE_ID = UUID("33333333-3333-3333-3333-333333333333")
OFFSET_TIME = datetime(
    2026, 8, 18, 9, 0, tzinfo=timezone(timedelta(hours=-3))
)


def test_quote_request_requires_canonical_asset_id_and_provider_symbol():
    request = QuoteRequest(ASSET_ID, "TEST.SYM")

    assert request.asset_id == ASSET_ID
    assert request.provider_symbol == "TEST.SYM"
    with pytest.raises(MarketDataValidationError, match="provider_symbol"):
        QuoteRequest(ASSET_ID, " ")


def test_history_request_normalizes_explicit_range_to_utc():
    request = HistoryRequest(
        asset_id=ASSET_ID,
        provider_symbol="TEST.SYM",
        interval=CandleInterval.ONE_DAY,
        start=OFFSET_TIME,
        end=OFFSET_TIME,
    )

    assert request.start == datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
    assert request.end == datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


def test_history_request_allows_open_range_and_rejects_invalid_ranges():
    assert HistoryRequest(
        ASSET_ID, "TEST.SYM", CandleInterval.ONE_DAY
    ).start is None

    with pytest.raises(MarketDataValidationError, match="timezone"):
        HistoryRequest(
            ASSET_ID,
            "TEST.SYM",
            CandleInterval.ONE_DAY,
            start=datetime(2026, 8, 18, 12, 0),
        )
    with pytest.raises(MarketDataValidationError, match="timezone"):
        HistoryRequest(
            ASSET_ID,
            "TEST.SYM",
            CandleInterval.ONE_DAY,
            end=datetime(2026, 8, 18, 12, 0),
        )
    with pytest.raises(MarketDataValidationError, match="posterior"):
        HistoryRequest(
            ASSET_ID,
            "TEST.SYM",
            CandleInterval.ONE_DAY,
            start=datetime(2026, 8, 19, tzinfo=UTC),
            end=datetime(2026, 8, 18, tzinfo=UTC),
        )
    with pytest.raises(MarketDataValidationError, match="CandleInterval"):
        HistoryRequest(ASSET_ID, "TEST.SYM", "1d")


def test_asset_search_request_has_only_provider_independent_filters():
    request = AssetSearchRequest(
        query="test",
        market_code="TEST",
        exchange_code="TESTEX",
    )

    assert request.market_code == "TEST"
    assert AssetSearchRequest() == AssetSearchRequest()
    with pytest.raises(MarketDataValidationError, match="query"):
        AssetSearchRequest(query=" ")


def test_market_status_request_accepts_internal_and_external_identifiers():
    market_request = MarketStatusRequest(
        market_id=MARKET_ID, provider_market_code="market-code"
    )
    exchange_request = MarketStatusRequest(
        exchange_id=EXCHANGE_ID, provider_exchange_code="exchange-code"
    )
    mixed_request = MarketStatusRequest(
        market_id=MARKET_ID, provider_exchange_code="exchange-code"
    )
    both_ids_request = MarketStatusRequest(
        market_id=MARKET_ID,
        exchange_id=EXCHANGE_ID,
        provider_market_code="market-code",
    )

    assert market_request.provider_market_code == "market-code"
    assert exchange_request.provider_exchange_code == "exchange-code"
    assert mixed_request.market_id == MARKET_ID
    assert both_ids_request.exchange_id == EXCHANGE_ID


@pytest.mark.parametrize(
    "kwargs",
    [
        {"provider_market_code": "market-code"},
        {"market_id": MARKET_ID},
        {},
    ],
)
def test_market_status_request_requires_internal_and_external_identifier(kwargs):
    with pytest.raises(MarketDataValidationError, match="deve ser informado"):
        MarketStatusRequest(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"market_id": MARKET_ID, "provider_market_code": ""},
        {"exchange_id": EXCHANGE_ID, "provider_exchange_code": "   "},
        {"market_id": "invalid", "provider_market_code": "market-code"},
    ],
)
def test_market_status_request_rejects_invalid_identifiers(kwargs):
    with pytest.raises(MarketDataValidationError):
        MarketStatusRequest(**kwargs)


class FakeProvider:
    def __init__(self) -> None:
        self.last_provider_market_code: str | None = None
        self.last_provider_exchange_code: str | None = None

    @property
    def name(self) -> str:
        return "fake-provider"

    def get_quote(self, request: QuoteRequest) -> Quote:
        return Quote(
            asset_id=request.asset_id,
            provider_symbol=request.provider_symbol,
            price=Decimal("1"),
            currency_code="TST",
            timestamp=OFFSET_TIME,
            received_at=OFFSET_TIME,
            provider=self.name,
            quality=None,
        )

    def get_history(self, request: HistoryRequest) -> list[Candle]:
        return []

    def get_assets(
        self, request: AssetSearchRequest
    ) -> list[ProviderAsset]:
        return []

    def get_market_status(
        self, request: MarketStatusRequest
    ) -> MarketStatus:
        self.last_provider_market_code = request.provider_market_code
        self.last_provider_exchange_code = request.provider_exchange_code
        return MarketStatus(
            market_id=request.market_id,
            exchange_id=request.exchange_id,
            status=MarketSessionStatus.UNKNOWN,
            timestamp=OFFSET_TIME,
            received_at=OFFSET_TIME,
            provider=self.name,
            quality=None,
        )


def test_fake_provider_satisfies_protocol_without_external_dependency():
    provider = FakeProvider()

    assert isinstance(provider, MarketDataProvider)
    assert provider.get_quote(QuoteRequest(ASSET_ID, "TEST.SYM")).price == Decimal(
        "1"
    )
    assert provider.get_history(
        HistoryRequest(ASSET_ID, "TEST.SYM", CandleInterval.ONE_DAY)
    ) == []
    assert provider.get_assets(AssetSearchRequest()) == []
    assert provider.get_market_status(
        MarketStatusRequest(
            market_id=MARKET_ID, provider_market_code="market-code"
        )
    ).status is MarketSessionStatus.UNKNOWN
    assert provider.last_provider_market_code == "market-code"
