from datetime import datetime
from uuid import UUID

from supabase import Client

from app.database.models import (
    MarketCandleRecord,
    MarketQuoteRecord,
    ProviderSymbolRecord,
    RepositoryDataError,
)
from app.database.repositories._response import create_one, read_one_or_none
from app.market_data.models import Candle, CandleInterval, Quote


class ProviderSymbolRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def create(self, *, asset_id: UUID, provider: str, provider_symbol: str) -> ProviderSymbolRecord:
        response = self._client.table("asset_provider_symbols").insert({"asset_id": str(asset_id), "provider": provider, "provider_symbol": provider_symbol}).execute()
        return create_one(response, operation="create provider symbol", parser=ProviderSymbolRecord.from_payload)

    def get_by_id(self, record_id: UUID) -> ProviderSymbolRecord | None:
        return read_one_or_none(self._client.table("asset_provider_symbols").select("*").eq("id", str(record_id)), operation="get provider symbol by id", parser=ProviderSymbolRecord.from_payload)

    def get_by_asset_and_provider(self, asset_id: UUID, provider: str) -> ProviderSymbolRecord | None:
        query = self._client.table("asset_provider_symbols").select("*").eq("asset_id", str(asset_id)).eq("provider", provider)
        return read_one_or_none(query, operation="get provider symbol by asset and provider", parser=ProviderSymbolRecord.from_payload)

    def get_by_provider_and_symbol(self, provider: str, provider_symbol: str) -> ProviderSymbolRecord | None:
        query = self._client.table("asset_provider_symbols").select("*").eq("provider", provider).eq("provider_symbol", provider_symbol)
        return read_one_or_none(query, operation="get provider symbol by provider and symbol", parser=ProviderSymbolRecord.from_payload)

    def list_active_by_provider(self, provider: str) -> tuple[ProviderSymbolRecord, ...]:
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("provider não pode ser vazio")
        response = self._client.table("asset_provider_symbols").select("*").eq("provider", provider).eq("is_active", True).order("provider_symbol", desc=False).execute()
        rows = getattr(response, "data", None)
        if not isinstance(rows, list):
            raise RepositoryDataError("list active provider symbols retornou dados inválidos")
        return tuple(ProviderSymbolRecord.from_payload(row) for row in rows)


class MarketQuoteRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def create_from_quote(self, quote: Quote) -> MarketQuoteRecord:
        if quote.quality is None:
            raise ValueError("quote deve possuir quality avaliada antes de persistir")
        payload = {"asset_id": str(quote.asset_id), "provider": quote.provider, "provider_symbol": quote.provider_symbol, "price": str(quote.price), "currency_code": quote.currency_code, "observed_at": quote.timestamp.isoformat(), "received_at": quote.received_at.isoformat(), "quality": quote.quality.value}
        response = self._client.table("market_quotes").insert(payload).execute()
        return create_one(response, operation="create market quote", parser=MarketQuoteRecord.from_payload)

    def get_by_id(self, record_id: UUID) -> MarketQuoteRecord | None:
        return read_one_or_none(self._client.table("market_quotes").select("*").eq("id", str(record_id)), operation="get market quote by id", parser=MarketQuoteRecord.from_payload)

    def get_latest(self, asset_id: UUID, provider: str) -> MarketQuoteRecord | None:
        query = self._client.table("market_quotes").select("*").eq("asset_id", str(asset_id)).eq("provider", provider).order("observed_at", desc=True)
        return read_one_or_none(query, operation="get latest market quote", parser=MarketQuoteRecord.from_payload)


class MarketCandleRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def create_many(self, candles: list[Candle] | tuple[Candle, ...]) -> tuple[MarketCandleRecord, ...]:
        if any(candle.quality is None for candle in candles):
            raise ValueError("candles devem possuir quality avaliada antes de persistir")
        if not candles:
            return ()
        payload = [{"asset_id": str(c.asset_id), "provider": c.provider, "provider_symbol": c.provider_symbol, "interval": c.interval.value, "observed_at": c.timestamp.isoformat(), "open": str(c.open), "high": str(c.high), "low": str(c.low), "close": str(c.close), "volume": str(c.volume) if c.volume is not None else None, "adjusted_close": str(c.adjusted_close) if c.adjusted_close is not None else None, "received_at": c.received_at.isoformat(), "quality": c.quality.value} for c in candles]
        response = self._client.table("market_candles").insert(payload).execute()
        rows = getattr(response, "data", None)
        if not isinstance(rows, list) or len(rows) != len(candles):
            raise RepositoryDataError("create market candles deve retornar todos os registros")
        return tuple(MarketCandleRecord.from_payload(row) for row in rows)

    def get_by_id(self, record_id: UUID) -> MarketCandleRecord | None:
        return read_one_or_none(self._client.table("market_candles").select("*").eq("id", str(record_id)), operation="get market candle by id", parser=MarketCandleRecord.from_payload)

    def get_range(self, *, asset_id: UUID, provider: str, interval: CandleInterval, start: datetime, end: datetime) -> tuple[MarketCandleRecord, ...]:
        query = self._client.table("market_candles").select("*").eq("asset_id", str(asset_id)).eq("provider", provider).eq("interval", interval.value).gte("observed_at", start.isoformat()).lte("observed_at", end.isoformat()).order("observed_at", desc=False)
        response = query.execute()
        rows = getattr(response, "data", None)
        if not isinstance(rows, list):
            raise RepositoryDataError("get market candle range retornou dados inválidos")
        return tuple(MarketCandleRecord.from_payload(row) for row in rows)
