from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Sequence, runtime_checkable
from uuid import UUID

from app.market_data.errors import MarketDataValidationError
from app.market_data.models import (
    Candle,
    CandleInterval,
    MarketStatus,
    ProviderAsset,
    Quote,
    ensure_non_blank,
    ensure_utc_datetime,
    ensure_uuid,
)


@dataclass(frozen=True, slots=True)
class QuoteRequest:
    asset_id: UUID
    provider_symbol: str

    def __post_init__(self) -> None:
        ensure_uuid(self.asset_id, field="asset_id")
        ensure_non_blank(self.provider_symbol, field="provider_symbol")


@dataclass(frozen=True, slots=True)
class HistoryRequest:
    asset_id: UUID
    provider_symbol: str
    interval: CandleInterval
    start: datetime | None = None
    end: datetime | None = None

    def __post_init__(self) -> None:
        ensure_uuid(self.asset_id, field="asset_id")
        ensure_non_blank(self.provider_symbol, field="provider_symbol")
        if not isinstance(self.interval, CandleInterval):
            raise MarketDataValidationError(
                "interval deve ser CandleInterval"
            )

        start = (
            ensure_utc_datetime(self.start, field="start")
            if self.start is not None
            else None
        )
        end = (
            ensure_utc_datetime(self.end, field="end")
            if self.end is not None
            else None
        )
        if start is not None and end is not None and start > end:
            raise MarketDataValidationError("start não pode ser posterior a end")

        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)


@dataclass(frozen=True, slots=True)
class AssetSearchRequest:
    query: str | None = None
    market_code: str | None = None
    exchange_code: str | None = None

    def __post_init__(self) -> None:
        for field in ("query", "market_code", "exchange_code"):
            value = getattr(self, field)
            if value is not None:
                ensure_non_blank(value, field=field)


@dataclass(frozen=True, slots=True)
class MarketStatusRequest:
    market_id: UUID | None = None
    exchange_id: UUID | None = None
    provider_market_code: str | None = None
    provider_exchange_code: str | None = None

    def __post_init__(self) -> None:
        if self.market_id is None and self.exchange_id is None:
            raise MarketDataValidationError(
                "market_id ou exchange_id deve ser informado"
            )
        if self.market_id is not None:
            ensure_uuid(self.market_id, field="market_id")
        if self.exchange_id is not None:
            ensure_uuid(self.exchange_id, field="exchange_id")
        if (
            self.provider_market_code is None
            and self.provider_exchange_code is None
        ):
            raise MarketDataValidationError(
                "provider_market_code ou provider_exchange_code deve ser "
                "informado"
            )
        if self.provider_market_code is not None:
            ensure_non_blank(
                self.provider_market_code, field="provider_market_code"
            )
        if self.provider_exchange_code is not None:
            ensure_non_blank(
                self.provider_exchange_code, field="provider_exchange_code"
            )


@runtime_checkable
class MarketDataProvider(Protocol):
    @property
    def name(self) -> str:
        """Provider identifier, without a closed central enum."""

    def get_quote(self, request: QuoteRequest) -> Quote:
        """Return one normalized quote or raise a provider-domain error."""

    def get_history(self, request: HistoryRequest) -> Sequence[Candle]:
        """Return normalized candles for the requested explicit range."""

    def get_assets(
        self, request: AssetSearchRequest
    ) -> Sequence[ProviderAsset]:
        """Return provider-level assets for later mapping."""

    def get_market_status(
        self, request: MarketStatusRequest
    ) -> MarketStatus:
        """Return normalized market or exchange status."""
