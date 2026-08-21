from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
import re
from uuid import UUID

from app.market_data.errors import MarketDataValidationError


_CURRENCY_CODE_RE = re.compile(r"^[A-Z0-9]{3,10}$")


class DataQuality(StrEnum):
    VALID = "VALID"
    STALE = "STALE"
    INCOMPLETE = "INCOMPLETE"
    OUTLIER = "OUTLIER"
    INVALID = "INVALID"


class CandleInterval(StrEnum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    ONE_DAY = "1d"
    ONE_WEEK = "1wk"
    ONE_MONTH = "1mo"


class MarketSessionStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PRE_MARKET = "PRE_MARKET"
    POST_MARKET = "POST_MARKET"
    AUCTION = "AUCTION"
    HALTED = "HALTED"


def ensure_utc_datetime(value: datetime, *, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise MarketDataValidationError(f"{field} deve ser datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise MarketDataValidationError(
            f"{field} deve possuir timezone"
        )

    return value.astimezone(UTC)


def ensure_non_blank(value: str, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MarketDataValidationError(f"{field} não pode ser vazio")

    return value


def ensure_uuid(value: UUID, *, field: str) -> UUID:
    if not isinstance(value, UUID):
        raise MarketDataValidationError(f"{field} deve ser UUID")

    return value


def ensure_currency_code(value: str) -> str:
    ensure_non_blank(value, field="currency_code")

    if not _CURRENCY_CODE_RE.fullmatch(value):
        raise MarketDataValidationError(
            "currency_code possui formato inválido"
        )

    return value


def ensure_non_negative_decimal(value: Decimal, *, field: str) -> Decimal:
    if not isinstance(value, Decimal):
        raise MarketDataValidationError(f"{field} deve ser Decimal")
    if not value.is_finite():
        raise MarketDataValidationError(f"{field} deve ser finito")
    if value < 0:
        raise MarketDataValidationError(
            f"{field} não pode ser negativo"
        )

    return value


def ensure_optional_text(value: str | None, *, field: str) -> str | None:
    if value is None:
        return None

    return ensure_non_blank(value, field=field)


@dataclass(frozen=True, slots=True)
class Quote:
    asset_id: UUID
    provider_symbol: str
    price: Decimal
    currency_code: str
    timestamp: datetime
    received_at: datetime
    provider: str
    quality: DataQuality | None

    def __post_init__(self) -> None:
        ensure_uuid(self.asset_id, field="asset_id")
        ensure_non_blank(self.provider_symbol, field="provider_symbol")
        ensure_non_negative_decimal(self.price, field="price")
        ensure_currency_code(self.currency_code)
        ensure_non_blank(self.provider, field="provider")
        if self.quality is not None and not isinstance(
            self.quality, DataQuality
        ):
            raise MarketDataValidationError(
                "quality deve ser DataQuality"
            )

        object.__setattr__(
            self,
            "timestamp",
            ensure_utc_datetime(self.timestamp, field="timestamp"),
        )
        object.__setattr__(
            self,
            "received_at",
            ensure_utc_datetime(self.received_at, field="received_at"),
        )


@dataclass(frozen=True, slots=True)
class Candle:
    asset_id: UUID
    provider_symbol: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None
    interval: CandleInterval
    provider: str
    received_at: datetime
    quality: DataQuality | None
    adjusted_close: Decimal | None = None

    def __post_init__(self) -> None:
        ensure_uuid(self.asset_id, field="asset_id")
        ensure_non_blank(self.provider_symbol, field="provider_symbol")
        ensure_non_blank(self.provider, field="provider")
        if not isinstance(self.interval, CandleInterval):
            raise MarketDataValidationError(
                "interval deve ser CandleInterval"
            )
        if self.quality is not None and not isinstance(
            self.quality, DataQuality
        ):
            raise MarketDataValidationError(
                "quality deve ser DataQuality"
            )

        open_price = ensure_non_negative_decimal(self.open, field="open")
        high_price = ensure_non_negative_decimal(self.high, field="high")
        low_price = ensure_non_negative_decimal(self.low, field="low")
        close_price = ensure_non_negative_decimal(self.close, field="close")

        if high_price < low_price:
            raise MarketDataValidationError("high não pode ser menor que low")
        if high_price < open_price:
            raise MarketDataValidationError("high não pode ser menor que open")
        if high_price < close_price:
            raise MarketDataValidationError("high não pode ser menor que close")
        if low_price > open_price:
            raise MarketDataValidationError("low não pode ser maior que open")
        if low_price > close_price:
            raise MarketDataValidationError("low não pode ser maior que close")

        if self.volume is not None:
            ensure_non_negative_decimal(self.volume, field="volume")
        if self.adjusted_close is not None:
            ensure_non_negative_decimal(
                self.adjusted_close, field="adjusted_close"
            )

        object.__setattr__(
            self,
            "timestamp",
            ensure_utc_datetime(self.timestamp, field="timestamp"),
        )
        object.__setattr__(
            self,
            "received_at",
            ensure_utc_datetime(self.received_at, field="received_at"),
        )


@dataclass(frozen=True, slots=True)
class MarketStatus:
    market_id: UUID | None
    exchange_id: UUID | None
    status: MarketSessionStatus
    timestamp: datetime
    received_at: datetime
    provider: str
    quality: DataQuality | None

    def __post_init__(self) -> None:
        if self.market_id is None and self.exchange_id is None:
            raise MarketDataValidationError(
                "market_id ou exchange_id deve ser informado"
            )
        if self.market_id is not None:
            ensure_uuid(self.market_id, field="market_id")
        if self.exchange_id is not None:
            ensure_uuid(self.exchange_id, field="exchange_id")
        if not isinstance(self.status, MarketSessionStatus):
            raise MarketDataValidationError(
                "status deve ser MarketSessionStatus"
            )
        if self.quality is not None and not isinstance(
            self.quality, DataQuality
        ):
            raise MarketDataValidationError(
                "quality deve ser DataQuality"
            )
        ensure_non_blank(self.provider, field="provider")

        object.__setattr__(
            self,
            "timestamp",
            ensure_utc_datetime(self.timestamp, field="timestamp"),
        )
        object.__setattr__(
            self,
            "received_at",
            ensure_utc_datetime(self.received_at, field="received_at"),
        )


@dataclass(frozen=True, slots=True)
class ProviderAsset:
    provider: str
    provider_symbol: str
    name: str
    asset_type: str | None = None
    currency_code: str | None = None
    exchange_code: str | None = None
    market_code: str | None = None
    isin: str | None = None

    def __post_init__(self) -> None:
        ensure_non_blank(self.provider, field="provider")
        ensure_non_blank(self.provider_symbol, field="provider_symbol")
        ensure_non_blank(self.name, field="name")
        ensure_optional_text(self.asset_type, field="asset_type")
        ensure_optional_text(self.exchange_code, field="exchange_code")
        ensure_optional_text(self.market_code, field="market_code")
        ensure_optional_text(self.isin, field="isin")
        if self.currency_code is not None:
            ensure_currency_code(self.currency_code)
