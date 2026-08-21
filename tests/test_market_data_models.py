from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from app.market_data.errors import MarketDataValidationError
from app.market_data.models import (
    Candle,
    CandleInterval,
    DataQuality,
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
UTC_TIME = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


def quote_kwargs(**changes):
    values = {
        "asset_id": ASSET_ID,
        "provider_symbol": "TEST.SYM",
        "price": Decimal("10.25"),
        "currency_code": "TST",
        "timestamp": OFFSET_TIME,
        "received_at": OFFSET_TIME,
        "provider": "test-provider",
        "quality": DataQuality.VALID,
    }
    values.update(changes)
    return values


def candle_kwargs(**changes):
    values = {
        "asset_id": ASSET_ID,
        "provider_symbol": "TEST.SYM",
        "timestamp": OFFSET_TIME,
        "open": Decimal("10"),
        "high": Decimal("12"),
        "low": Decimal("9"),
        "close": Decimal("11"),
        "volume": Decimal("100"),
        "interval": CandleInterval.ONE_DAY,
        "provider": "test-provider",
        "received_at": OFFSET_TIME,
        "quality": DataQuality.VALID,
    }
    values.update(changes)
    return values


def status_kwargs(**changes):
    values = {
        "market_id": MARKET_ID,
        "exchange_id": None,
        "status": MarketSessionStatus.OPEN,
        "timestamp": OFFSET_TIME,
        "received_at": OFFSET_TIME,
        "provider": "test-provider",
        "quality": DataQuality.VALID,
    }
    values.update(changes)
    return values


def test_quote_preserves_decimal_and_normalizes_timestamps_to_utc():
    quote = Quote(**quote_kwargs())

    assert quote.price == Decimal("10.25")
    assert isinstance(quote.price, Decimal)
    assert quote.timestamp == UTC_TIME
    assert quote.received_at == UTC_TIME


@pytest.mark.parametrize("field", ["timestamp", "received_at"])
def test_quote_rejects_naive_datetime(field):
    with pytest.raises(MarketDataValidationError, match="timezone"):
        Quote(**quote_kwargs(**{field: datetime(2026, 8, 18, 12, 0)}))


@pytest.mark.parametrize("field", ["provider", "provider_symbol"])
def test_quote_rejects_blank_provider_fields(field):
    with pytest.raises(MarketDataValidationError, match="não pode ser vazio"):
        Quote(**quote_kwargs(**{field: "  "}))


@pytest.mark.parametrize("currency_code", ["tst", "TOO_LONG_CODE", "12"])
def test_quote_rejects_invalid_currency_code(currency_code):
    with pytest.raises(MarketDataValidationError, match="currency_code"):
        Quote(**quote_kwargs(currency_code=currency_code))


@pytest.mark.parametrize(
    "price",
    [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"), Decimal("-1")],
)
def test_quote_rejects_non_finite_or_negative_price(price):
    with pytest.raises(MarketDataValidationError):
        Quote(**quote_kwargs(price=price))


def test_quote_rejects_float_and_requires_explicit_quality():
    with pytest.raises(MarketDataValidationError, match="Decimal"):
        Quote(**quote_kwargs(price=10.25))

    with pytest.raises(MarketDataValidationError, match="DataQuality"):
        Quote(**quote_kwargs(quality="VALID"))

    values = quote_kwargs()
    del values["quality"]
    with pytest.raises(TypeError):
        Quote(**values)


def test_quote_allows_unassessed_or_evaluated_quality():
    assert Quote(**quote_kwargs(quality=None)).quality is None
    assert (
        Quote(**quote_kwargs(quality=DataQuality.VALID)).quality
        is DataQuality.VALID
    )


def test_candle_normalizes_timestamps_and_allows_nullable_values():
    candle = Candle(
        **candle_kwargs(volume=None, adjusted_close=None)
    )

    assert candle.timestamp == UTC_TIME
    assert candle.received_at == UTC_TIME
    assert candle.volume is None
    assert candle.adjusted_close is None


def test_candle_allows_unassessed_quality():
    assert Candle(**candle_kwargs(quality=None)).quality is None


@pytest.mark.parametrize(
    ("field", "value", "changes", "message"),
    [
        ("high", Decimal("8"), {}, "menor que low"),
        ("high", Decimal("9.5"), {}, "menor que open"),
        ("high", Decimal("10.5"), {}, "menor que close"),
        ("low", Decimal("10.5"), {}, "maior que open"),
        ("low", Decimal("10"), {"close": Decimal("9")}, "maior que close"),
    ],
)
def test_candle_rejects_invalid_ohlc_relationships(
    field, value, changes, message
):
    with pytest.raises(MarketDataValidationError, match=message):
        Candle(**candle_kwargs(**changes, **{field: value}))


@pytest.mark.parametrize("field", ["open", "high", "low", "close"])
def test_candle_rejects_negative_and_non_finite_ohlc(field):
    with pytest.raises(MarketDataValidationError):
        Candle(**candle_kwargs(**{field: Decimal("-1")}))
    with pytest.raises(MarketDataValidationError, match="finito"):
        Candle(**candle_kwargs(**{field: Decimal("NaN")}))


def test_candle_rejects_invalid_volume_and_adjusted_close():
    with pytest.raises(MarketDataValidationError):
        Candle(**candle_kwargs(volume=Decimal("-1")))
    with pytest.raises(MarketDataValidationError, match="finito"):
        Candle(**candle_kwargs(adjusted_close=Decimal("Infinity")))


def test_candle_rejects_naive_timestamp():
    with pytest.raises(MarketDataValidationError, match="timezone"):
        Candle(**candle_kwargs(timestamp=datetime(2026, 8, 18, 12, 0)))


def test_market_status_supports_market_exchange_or_both():
    market_status = MarketStatus(**status_kwargs())
    exchange_status = MarketStatus(
        **status_kwargs(market_id=None, exchange_id=EXCHANGE_ID)
    )
    both_status = MarketStatus(
        **status_kwargs(exchange_id=EXCHANGE_ID)
    )

    assert market_status.timestamp == UTC_TIME
    assert exchange_status.exchange_id == EXCHANGE_ID
    assert both_status.market_id == MARKET_ID


def test_market_status_allows_unassessed_quality():
    assert MarketStatus(**status_kwargs(quality=None)).quality is None


def test_market_status_rejects_missing_scope_blank_provider_and_naive_time():
    with pytest.raises(MarketDataValidationError, match="deve ser informado"):
        MarketStatus(**status_kwargs(market_id=None, exchange_id=None))
    with pytest.raises(MarketDataValidationError, match="não pode ser vazio"):
        MarketStatus(**status_kwargs(provider=""))
    with pytest.raises(MarketDataValidationError, match="timezone"):
        MarketStatus(
            **status_kwargs(timestamp=datetime(2026, 8, 18, 12, 0))
        )


def test_provider_asset_is_provider_level_and_validates_required_fields():
    provider_asset = ProviderAsset(
        provider="test-provider",
        provider_symbol="TEST.SYM",
        name="Test asset",
        currency_code="TST",
    )

    assert provider_asset.currency_code == "TST"
    with pytest.raises(MarketDataValidationError, match="provider_symbol"):
        ProviderAsset(
            provider="test-provider",
            provider_symbol=" ",
            name="Test asset",
        )
