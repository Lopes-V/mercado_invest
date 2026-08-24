from collections.abc import Mapping
from dataclasses import dataclass
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
from app.market_data.models import Candle, CandleInterval, DataQuality, Quote, ensure_utc_datetime


@dataclass(frozen=True, slots=True)
class MarketQuoteSaveResult:
    """Outcome of an immutable market quote write."""

    record: MarketQuoteRecord
    created: bool


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

    def create_from_quote(self, quote: Quote) -> MarketQuoteSaveResult:
        """Atomically insert a quote or return its existing immutable observation.

        The unique database identity is the authority for duplicate detection.
        The follow-up identity lookup is only to recover the existing record after
        PostgreSQL has already decided ``ON CONFLICT DO NOTHING``.
        """
        if quote.quality is None:
            raise ValueError("quote deve possuir quality avaliada antes de persistir")
        payload = {"asset_id": str(quote.asset_id), "provider": quote.provider, "provider_symbol": quote.provider_symbol, "price": str(quote.price), "currency_code": quote.currency_code, "observed_at": quote.timestamp.isoformat(), "received_at": quote.received_at.isoformat(), "quality": quote.quality.value}
        response = (
            self._client.table("market_quotes")
            .upsert(
                payload,
                on_conflict="asset_id,provider,observed_at",
                ignore_duplicates=True,
            )
            .execute()
        )
        rows = getattr(response, "data", None)
        if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
            raise RepositoryDataError("create market quote retornou dados fora do formato esperado")
        if len(rows) == 1:
            return MarketQuoteSaveResult(
                record=MarketQuoteRecord.from_payload(rows[0]), created=True
            )
        if len(rows) != 0:
            raise RepositoryDataError("create market quote deve retornar no máximo um registro")
        existing = self.get_by_identity(
            asset_id=quote.asset_id,
            provider=quote.provider,
            observed_at=quote.timestamp,
        )
        if existing is None:
            raise RepositoryDataError(
                "duplicate market quote não retornou o registro existente"
            )
        return MarketQuoteSaveResult(record=existing, created=False)

    def get_by_id(self, record_id: UUID) -> MarketQuoteRecord | None:
        return read_one_or_none(self._client.table("market_quotes").select("*").eq("id", str(record_id)), operation="get market quote by id", parser=MarketQuoteRecord.from_payload)

    def get_latest(self, asset_id: UUID, provider: str) -> MarketQuoteRecord | None:
        query = self._client.table("market_quotes").select("*").eq("asset_id", str(asset_id)).eq("provider", provider).order("observed_at", desc=True)
        return read_one_or_none(query, operation="get latest market quote", parser=MarketQuoteRecord.from_payload)

    def get_by_identity(
        self, *, asset_id: UUID, provider: str, observed_at: datetime
    ) -> MarketQuoteRecord | None:
        query = (
            self._client.table("market_quotes")
            .select("*")
            .eq("asset_id", str(asset_id))
            .eq("provider", provider)
            .eq("observed_at", observed_at.isoformat())
        )
        return read_one_or_none(
            query,
            operation="get market quote by identity",
            parser=MarketQuoteRecord.from_payload,
        )


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

    def get_by_identity(
        self,
        *,
        asset_id: UUID,
        provider: str,
        interval: CandleInterval,
        observed_at: datetime,
    ) -> MarketCandleRecord | None:
        query = (
            self._client.table("market_candles")
            .select("*")
            .eq("asset_id", str(asset_id))
            .eq("provider", provider)
            .eq("interval", interval.value)
            .eq("observed_at", observed_at.isoformat())
        )
        return read_one_or_none(
            query,
            operation="get market candle by identity",
            parser=MarketCandleRecord.from_payload,
        )

    def create_many_idempotent(
        self, candles: list[Candle] | tuple[Candle, ...]
    ) -> tuple[MarketCandleRecord, ...]:
        """Persist only missing historical candles through explicit reads/inserts.

        Daily history requests intentionally overlap.  This method is not an
        upsert: an existing immutable identity is read and reused, missing
        identities are inserted, and a concurrent uniqueness race still
        propagates as a database error instead of being silently overwritten.
        """

        if not candles:
            return ()
        identities = [
            (candle.asset_id, candle.provider, candle.interval, candle.timestamp)
            for candle in candles
        ]
        if len(set(identities)) != len(identities):
            raise ValueError("candles de entrada não podem ter identidade duplicada")
        existing: dict[tuple[UUID, str, CandleInterval, datetime], MarketCandleRecord] = {}
        missing: list[Candle] = []
        for candle, identity in zip(candles, identities, strict=True):
            record = self.get_by_identity(
                asset_id=candle.asset_id,
                provider=candle.provider,
                interval=candle.interval,
                observed_at=candle.timestamp,
            )
            if record is None:
                missing.append(candle)
            else:
                existing[identity] = record
        created = self.create_many(missing) if missing else ()
        for record in created:
            existing[
                (
                    record.asset_id,
                    record.provider,
                    CandleInterval(record.interval),
                    record.observed_at,
                )
            ] = record
        return tuple(existing[identity] for identity in identities)

    def get_range(self, *, asset_id: UUID, provider: str, interval: CandleInterval, start: datetime, end: datetime) -> tuple[MarketCandleRecord, ...]:
        query = self._client.table("market_candles").select("*").eq("asset_id", str(asset_id)).eq("provider", provider).eq("interval", interval.value).gte("observed_at", start.isoformat()).lte("observed_at", end.isoformat()).order("observed_at", desc=False)
        response = query.execute()
        rows = getattr(response, "data", None)
        if not isinstance(rows, list):
            raise RepositoryDataError("get market candle range retornou dados inválidos")
        return tuple(MarketCandleRecord.from_payload(row) for row in rows)

    def first_price_at_or_after(
        self,
        *,
        asset_id: UUID,
        provider: str,
        interval: str,
        at_or_after: datetime,
    ) -> MarketCandleRecord | None:
        """Return the first VALID close no earlier than a shadow due instant."""

        due = ensure_utc_datetime(at_or_after, field="at_or_after")

        response = (
            self._client.table("market_candles")
            .select("*")
            .eq("asset_id", str(asset_id))
            .eq("provider", provider)
            .eq("interval", interval)
            .eq("quality", DataQuality.VALID.value)
            .gte("observed_at", due.isoformat())
            .order("observed_at", desc=False)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None)
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise RepositoryDataError("get first shadow outcome candle retornou dados inválidos")
        if not rows:
            return None
        return MarketCandleRecord.from_payload(rows[0])
