"""Opt-in real discovery and validation of a non-Brazilian, non-US equity."""

import os
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from dotenv import load_dotenv

from app.market_data.contracts import HistoryRequest, QuoteRequest
from app.market_data.errors import ProviderHttpError
from app.market_data.http import ProviderHttpClient
from app.market_data.models import CandleInterval
from app.market_data.providers.twelve_data import TwelveDataProvider


pytestmark = pytest.mark.integration

_EXCLUDED_COUNTRIES = frozenset({"Brazil", "United States"})
_EXCLUDED_EXCHANGES = frozenset({"B3", "NASDAQ", "NYSE"})
_DISCOVERY_QUERIES = ("NESN", "7203")


@dataclass(frozen=True, slots=True)
class _GlobalCandidate:
    symbol: str
    exchange: str
    country: str
    currency: str


def _provider() -> tuple[TwelveDataProvider, ProviderHttpClient]:
    if os.getenv("RUN_GLOBAL_MARKET_INTEGRATION") != "1":
        pytest.skip("RUN_GLOBAL_MARKET_INTEGRATION=1 required")
    load_dotenv(".env")
    api_key = os.getenv("TWELVE_DATA_API_KEY")
    if not api_key:
        pytest.fail("TWELVE_DATA_API_KEY is required when integration is enabled")
    client = ProviderHttpClient(
        base_url="https://api.twelvedata.com",
        timeout_seconds=15,
    )
    return TwelveDataProvider(client, api_key=api_key), client


def _text(row: Mapping[str, object], field: str) -> str | None:
    value = row.get(field)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _discover_candidates(
    client: ProviderHttpClient,
    requested_symbol: str | None,
) -> tuple[_GlobalCandidate, ...]:
    queries = (requested_symbol,) if requested_symbol else _DISCOVERY_QUERIES
    candidates: list[_GlobalCandidate] = []
    for query in queries:
        payload = client.get_json("/symbol_search", params={"symbol": query})
        if not isinstance(payload, Mapping) or not isinstance(payload.get("data"), list):
            pytest.fail("Twelve Data symbol_search returned an invalid response")
        rows_by_symbol: dict[str, list[Mapping[str, object]]] = defaultdict(list)
        for row in payload["data"]:
            if isinstance(row, Mapping):
                symbol = _text(row, "symbol")
                if symbol:
                    rows_by_symbol[symbol].append(row)
        for symbol, rows in rows_by_symbol.items():
            countries = {_text(row, "country") for row in rows}
            exchanges = {_text(row, "exchange") for row in rows}
            if (
                not countries
                or None in countries
                or countries & _EXCLUDED_COUNTRIES
                or any(
                    exchange is None or exchange.upper() in _EXCLUDED_EXCHANGES
                    for exchange in exchanges
                )
            ):
                continue
            row = rows[0]
            exchange = _text(row, "exchange")
            country = _text(row, "country")
            currency = _text(row, "currency")
            if exchange and country and currency and currency != "BRL":
                candidates.append(
                    _GlobalCandidate(symbol, exchange, country, currency)
                )
    return tuple(candidates)


def test_global_market_live_quote_and_history() -> None:
    provider, client = _provider()
    requested_symbol = os.getenv("GLOBAL_TEST_SYMBOL")
    unavailable_statuses: list[int] = []
    try:
        candidates = _discover_candidates(client, requested_symbol)
        if not candidates:
            pytest.skip("no eligible non-Brazilian/non-US equity was discoverable")
        for candidate in candidates:
            try:
                quote = provider.get_quote(QuoteRequest(uuid4(), candidate.symbol))
                end = datetime.now(UTC)
                candles = provider.get_history(
                    HistoryRequest(
                        asset_id=quote.asset_id,
                        provider_symbol=candidate.symbol,
                        interval=CandleInterval.ONE_DAY,
                        start=end - timedelta(days=10),
                        end=end,
                    )
                )
            except ProviderHttpError as exc:
                if exc.status_code in {400, 403, 404}:
                    unavailable_statuses.append(exc.status_code)
                    continue
                raise

            assert candidate.country not in _EXCLUDED_COUNTRIES
            assert candidate.exchange.upper() not in _EXCLUDED_EXCHANGES
            assert candidate.currency != "BRL"
            assert quote.provider == "twelve_data"
            assert quote.provider_symbol == candidate.symbol
            assert isinstance(quote.price, Decimal)
            assert quote.price > 0
            assert quote.currency_code
            assert quote.timestamp.tzinfo is not None
            assert quote.received_at.tzinfo is not None
            assert quote.quality is None
            assert candles
            assert tuple(candle.timestamp for candle in candles) == tuple(
                sorted(candle.timestamp for candle in candles)
            )
            assert all(
                candle.provider == "twelve_data"
                and candle.interval is CandleInterval.ONE_DAY
                and candle.quality is None
                and candle.timestamp.tzinfo is not None
                and isinstance(candle.close, Decimal)
                for candle in candles
            )
            return
    finally:
        client.close()

    pytest.skip(
        "Twelve Data plan or symbol access did not allow a discovered global "
        f"equity (HTTP statuses: {sorted(set(unavailable_statuses))})"
    )
