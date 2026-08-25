from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import httpx
import pytest

from app.market_data.contracts import (
    AssetSearchRequest,
    HistoryRequest,
    MarketStatusRequest,
    QuoteRequest,
)
from app.market_data.errors import (
    ProviderCapabilityError,
    ProviderResponseError,
)
from app.market_data.http import ProviderHttpClient
from app.market_data.models import CandleInterval
from app.market_data.providers import BrapiProvider


ASSET_ID = UUID("11111111-1111-1111-1111-111111111111")
MARKET_ID = UUID("22222222-2222-2222-2222-222222222222")
CLOCK_TIME = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


def provider_for(payload, *, requests=None, token=None):
    def handler(request):
        if requests is not None:
            requests.append(request)
        return httpx.Response(200, json=payload)

    return BrapiProvider(
        ProviderHttpClient(
            base_url="https://brapi.dev",
            transport=httpx.MockTransport(handler),
            sleep=lambda _: None,
        ),
        token=token,
        clock=lambda: CLOCK_TIME,
    )


def quote_payload(**changes):
    data = {
        "regularMarketPrice": 30.25,
        "currency": "BRL",
        "regularMarketTime": 1781712000,
    }
    result = {
        "requestedSymbol": "PETR4",
        "symbol": "PETR4",
        "changed": False,
        "data": data,
    }
    result.update(changes)
    return {"results": [result]}


def history_payload(**changes):
    point = {
        "date": 1781625600,
        "open": 30,
        "high": 31,
        "low": 29,
        "close": 30.5,
        "volume": 100,
        "adjustedClose": 30.5,
    }
    data = {"historicalDataPrice": [point]}
    result = {
        "requestedSymbol": "PETR4",
        "symbol": "PETR4",
        "changed": False,
        "data": data,
    }
    result.update(changes)
    return {"results": [result]}


def history_request(interval=CandleInterval.ONE_DAY, *, start=True, end=True):
    return HistoryRequest(
        asset_id=ASSET_ID,
        provider_symbol="PETR4",
        interval=interval,
        start=datetime(2026, 6, 1, tzinfo=UTC) if start else None,
        end=datetime(2026, 6, 2, tzinfo=UTC) if end else None,
    )


def test_quote_is_normalized_with_decimal_timestamp_and_unassessed_quality():
    requests = []
    quote = provider_for(quote_payload(), requests=requests).get_quote(
        QuoteRequest(ASSET_ID, "PETR4")
    )

    assert quote.asset_id == ASSET_ID
    assert quote.provider_symbol == "PETR4"
    assert quote.price == Decimal("30.25")
    assert quote.timestamp == datetime(2026, 6, 17, 16, 0, tzinfo=UTC)
    assert quote.received_at == CLOCK_TIME
    assert quote.provider == "brapi"
    assert quote.quality is None
    assert requests[0].url.path == "/api/v2/stocks/quote"
    assert requests[0].url.params["symbols"] == "PETR4"


def test_quote_accepts_timezone_aware_iso_timestamp_from_current_api():
    payload = quote_payload(
        data={
            "regularMarketPrice": 30.25,
            "currency": "BRL",
            "regularMarketTime": "2026-06-17T16:00:00.000Z",
        }
    )

    quote = provider_for(payload).get_quote(QuoteRequest(ASSET_ID, "PETR4"))

    assert quote.timestamp == datetime(2026, 6, 17, 16, 0, tzinfo=UTC)


@pytest.mark.parametrize("results", [[], [{}, {}]])
def test_quote_rejects_empty_or_multiple_results(results):
    with pytest.raises(ProviderResponseError, match="exatamente um"):
        provider_for({"results": results}).get_quote(QuoteRequest(ASSET_ID, "PETR4"))


@pytest.mark.parametrize(
    "payload",
    [
        quote_payload(data={"currency": "BRL", "regularMarketTime": 1}),
        quote_payload(
            data={
                "regularMarketPrice": "30.25",
                "currency": "BRL",
                "regularMarketTime": 1,
            }
        ),
    ],
)
def test_quote_rejects_missing_or_invalid_fields(payload):
    with pytest.raises(ProviderResponseError):
        provider_for(payload).get_quote(QuoteRequest(ASSET_ID, "PETR4"))


def test_quote_rejects_changed_ticker_with_observable_identity_details():
    with pytest.raises(
        ProviderResponseError,
        match=(
            "requested_symbol=ELET3 returned_symbol=AXIA3 changed=true"
        ),
    ):
        provider_for(
            quote_payload(
                requestedSymbol="ELET3",
                symbol="AXIA3",
                changed=True,
            )
        ).get_quote(QuoteRequest(ASSET_ID, "ELET3"))


def test_quote_rejects_divergent_symbol_even_when_provider_reports_unchanged():
    with pytest.raises(
        ProviderResponseError,
        match=(
            "requested_symbol=ELET3 returned_symbol=AXIA3 changed=false"
        ),
    ):
        provider_for(
            quote_payload(
                requestedSymbol="ELET3",
                symbol="AXIA3",
                changed=False,
            )
        ).get_quote(QuoteRequest(ASSET_ID, "ELET3"))


def test_quote_accepts_axia3_when_mapping_and_provider_identity_match():
    quote = provider_for(
        quote_payload(
            requestedSymbol="AXIA3",
            symbol="AXIA3",
            changed=False,
        )
    ).get_quote(QuoteRequest(ASSET_ID, "AXIA3"))

    assert quote.provider_symbol == "AXIA3"


def test_history_normalizes_ohlcv_and_nullable_optional_fields():
    payload = history_payload()
    point = payload["results"][0]["data"]["historicalDataPrice"][0]
    point["volume"] = None
    point["adjustedClose"] = None
    requests = []
    candles = provider_for(payload, requests=requests).get_history(history_request())

    assert len(candles) == 1
    assert candles[0].close == Decimal("30.5")
    assert candles[0].volume is None
    assert candles[0].adjusted_close is None
    assert candles[0].timestamp.tzinfo is UTC
    assert candles[0].quality is None
    assert requests[0].url.path == "/api/v2/stocks/historical"
    assert requests[0].url.params["startDate"] == "2026-06-01"
    assert requests[0].url.params["endDate"] == "2026-06-02"
    assert requests[0].url.params["sortOrder"] == "asc"


@pytest.mark.parametrize(
    ("interval", "provider_interval"),
    [
        (CandleInterval.ONE_MINUTE, "1m"),
        (CandleInterval.FIVE_MINUTES, "5m"),
        (CandleInterval.FIFTEEN_MINUTES, "15m"),
        (CandleInterval.THIRTY_MINUTES, "30m"),
        (CandleInterval.ONE_HOUR, "1h"),
        (CandleInterval.ONE_DAY, "1d"),
        (CandleInterval.ONE_WEEK, "1wk"),
        (CandleInterval.ONE_MONTH, "1mo"),
    ],
)
def test_history_uses_explicit_interval_mapping(interval, provider_interval):
    requests = []
    provider_for(history_payload(), requests=requests).get_history(
        history_request(interval)
    )

    assert requests[0].url.params["interval"] == provider_interval


@pytest.mark.parametrize(
    "history_request_value",
    [history_request(start=False), history_request(end=False), history_request(start=False, end=False)],
)
def test_history_requires_explicit_complete_range(history_request_value):
    with pytest.raises(ProviderCapabilityError, match="start e end"):
        provider_for(history_payload()).get_history(history_request_value)


def test_assets_map_query_and_do_not_invent_market_data():
    requests = []
    payload = {
        "results": [
            {
                "symbol": "PETR4",
                "name": "Petrobras",
                "assetType": "stock",
                "subType": "stock",
                "currency": "BRL",
                "exchange": "B3",
            }
        ]
    }
    assets = provider_for(payload, requests=requests).get_assets(
        AssetSearchRequest(query="PETR")
    )

    assert assets[0].provider_symbol == "PETR4"
    assert assets[0].asset_type == "stock"
    assert assets[0].market_code is None
    assert assets[0].isin is None
    assert requests[0].url.path == "/api/v2/tickers"
    assert requests[0].url.params["search"] == "PETR"


def test_assets_reject_unsupported_domain_filters():
    with pytest.raises(ProviderCapabilityError, match="market/exchange"):
        provider_for({"results": []}).get_assets(
            AssetSearchRequest(market_code="BR")
        )


def test_market_status_reports_unsupported_capability():
    request = MarketStatusRequest(
        market_id=MARKET_ID, provider_market_code="BR"
    )
    with pytest.raises(ProviderCapabilityError, match="market status"):
        provider_for({}).get_market_status(request)


def test_authorization_header_is_optional_and_never_a_query_parameter():
    authenticated_requests = []
    provider_for(
        quote_payload(),
        requests=authenticated_requests,
        token="test-token",
    ).get_quote(QuoteRequest(ASSET_ID, "PETR4"))
    assert authenticated_requests[0].headers["authorization"] == "Bearer test-token"
    assert "token" not in authenticated_requests[0].url.params

    public_requests = []
    provider_for(quote_payload(), requests=public_requests).get_quote(
        QuoteRequest(ASSET_ID, "PETR4")
    )
    assert "authorization" not in public_requests[0].headers
