from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from math import isfinite
from uuid import UUID


class RepositoryDataError(ValueError):
    """Raised when a Supabase response does not match the persistence contract."""


def _required(payload: Mapping[str, object], field: str) -> object:
    try:
        return payload[field]
    except KeyError as exc:
        raise RepositoryDataError(
            f"Campo ausente na resposta do repository: {field}"
        ) from exc


def _uuid(payload: Mapping[str, object], field: str) -> UUID:
    value = _required(payload, field)

    if not isinstance(value, str):
        raise RepositoryDataError(f"{field} deve ser UUID em texto")

    try:
        return UUID(value)
    except ValueError as exc:
        raise RepositoryDataError(f"{field} contém UUID inválido") from exc


def _nullable_uuid(
    payload: Mapping[str, object], field: str
) -> UUID | None:
    value = _required(payload, field)

    if value is None:
        return None
    if not isinstance(value, str):
        raise RepositoryDataError(f"{field} deve ser UUID em texto ou nulo")

    try:
        return UUID(value)
    except ValueError as exc:
        raise RepositoryDataError(f"{field} contém UUID inválido") from exc


def _text(payload: Mapping[str, object], field: str) -> str:
    value = _required(payload, field)

    if not isinstance(value, str):
        raise RepositoryDataError(f"{field} deve ser texto")

    return value


def _nullable_text(
    payload: Mapping[str, object], field: str
) -> str | None:
    value = _required(payload, field)

    if value is None:
        return None
    if not isinstance(value, str):
        raise RepositoryDataError(f"{field} deve ser texto ou nulo")

    return value


def _integer(payload: Mapping[str, object], field: str) -> int:
    value = _required(payload, field)

    if isinstance(value, bool) or not isinstance(value, int):
        raise RepositoryDataError(f"{field} deve ser inteiro")

    return value


def _boolean(payload: Mapping[str, object], field: str) -> bool:
    value = _required(payload, field)

    if not isinstance(value, bool):
        raise RepositoryDataError(f"{field} deve ser booleano")

    return value


def _datetime(payload: Mapping[str, object], field: str) -> datetime:
    value = _required(payload, field)

    if not isinstance(value, str):
        raise RepositoryDataError(
            f"{field} deve ser timestamp ISO 8601 em texto"
        )

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RepositoryDataError(
            f"{field} contém timestamp inválido"
        ) from exc

    if parsed.tzinfo is None:
        raise RepositoryDataError(
            f"{field} deve conter timezone"
        )

    return parsed


def _decimal(payload: Mapping[str, object], field: str) -> Decimal:
    value = _required(payload, field)
    if isinstance(value, bool):
        raise RepositoryDataError(f"{field} deve preservar precisão decimal")
    if isinstance(value, float):
        # PostgREST decodifica colunas numeric como float no cliente Python.
        # Converter sua representação textual evita Decimal(float), que
        # incorporaria artefatos binários à representação decimal do record.
        if not isfinite(value):
            raise RepositoryDataError(f"{field} deve ser finito")
        return Decimal(str(value))
    if not isinstance(value, (str, int, Decimal)):
        raise RepositoryDataError(f"{field} deve ser decimal")
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise RepositoryDataError(f"{field} contém decimal inválido") from exc
    if not parsed.is_finite():
        raise RepositoryDataError(f"{field} deve ser finito")
    return parsed


def _nullable_decimal(payload: Mapping[str, object], field: str) -> Decimal | None:
    if _required(payload, field) is None:
        return None
    return _decimal(payload, field)


@dataclass(frozen=True, slots=True)
class CurrencyRecord:
    id: UUID
    code: str
    name: str
    symbol: str | None
    decimal_places: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_payload(
        cls, payload: Mapping[str, object]
    ) -> "CurrencyRecord":
        return cls(
            id=_uuid(payload, "id"),
            code=_text(payload, "code"),
            name=_text(payload, "name"),
            symbol=_nullable_text(payload, "symbol"),
            decimal_places=_integer(payload, "decimal_places"),
            is_active=_boolean(payload, "is_active"),
            created_at=_datetime(payload, "created_at"),
            updated_at=_datetime(payload, "updated_at"),
        )


@dataclass(frozen=True, slots=True)
class MarketRecord:
    id: UUID
    code: str
    name: str
    country_code: str | None
    default_currency_id: UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_payload(
        cls, payload: Mapping[str, object]
    ) -> "MarketRecord":
        return cls(
            id=_uuid(payload, "id"),
            code=_text(payload, "code"),
            name=_text(payload, "name"),
            country_code=_nullable_text(payload, "country_code"),
            default_currency_id=_nullable_uuid(
                payload, "default_currency_id"
            ),
            is_active=_boolean(payload, "is_active"),
            created_at=_datetime(payload, "created_at"),
            updated_at=_datetime(payload, "updated_at"),
        )


@dataclass(frozen=True, slots=True)
class ExchangeRecord:
    id: UUID
    market_id: UUID
    code: str
    name: str
    mic: str | None
    timezone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_payload(
        cls, payload: Mapping[str, object]
    ) -> "ExchangeRecord":
        return cls(
            id=_uuid(payload, "id"),
            market_id=_uuid(payload, "market_id"),
            code=_text(payload, "code"),
            name=_text(payload, "name"),
            mic=_nullable_text(payload, "mic"),
            timezone=_text(payload, "timezone"),
            is_active=_boolean(payload, "is_active"),
            created_at=_datetime(payload, "created_at"),
            updated_at=_datetime(payload, "updated_at"),
        )


@dataclass(frozen=True, slots=True)
class AssetRecord:
    id: UUID
    market_id: UUID
    exchange_id: UUID | None
    currency_id: UUID
    symbol: str
    name: str
    asset_type: str
    isin: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_payload(
        cls, payload: Mapping[str, object]
    ) -> "AssetRecord":
        return cls(
            id=_uuid(payload, "id"),
            market_id=_uuid(payload, "market_id"),
            exchange_id=_nullable_uuid(payload, "exchange_id"),
            currency_id=_uuid(payload, "currency_id"),
            symbol=_text(payload, "symbol"),
            name=_text(payload, "name"),
            asset_type=_text(payload, "asset_type"),
            isin=_nullable_text(payload, "isin"),
            is_active=_boolean(payload, "is_active"),
            created_at=_datetime(payload, "created_at"),
            updated_at=_datetime(payload, "updated_at"),
        )


@dataclass(frozen=True, slots=True)
class ProviderSymbolRecord:
    id: UUID
    asset_id: UUID
    provider: str
    provider_symbol: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "ProviderSymbolRecord":
        return cls(_uuid(payload, "id"), _uuid(payload, "asset_id"), _text(payload, "provider"), _text(payload, "provider_symbol"), _boolean(payload, "is_active"), _datetime(payload, "created_at"), _datetime(payload, "updated_at"))


@dataclass(frozen=True, slots=True)
class MarketQuoteRecord:
    id: UUID
    asset_id: UUID
    provider: str
    provider_symbol: str
    price: Decimal
    currency_code: str
    observed_at: datetime
    received_at: datetime
    quality: str
    created_at: datetime

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "MarketQuoteRecord":
        return cls(_uuid(payload, "id"), _uuid(payload, "asset_id"), _text(payload, "provider"), _text(payload, "provider_symbol"), _decimal(payload, "price"), _text(payload, "currency_code"), _datetime(payload, "observed_at"), _datetime(payload, "received_at"), _text(payload, "quality"), _datetime(payload, "created_at"))


@dataclass(frozen=True, slots=True)
class MarketCandleRecord:
    id: UUID
    asset_id: UUID
    provider: str
    provider_symbol: str
    interval: str
    observed_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None
    adjusted_close: Decimal | None
    received_at: datetime
    quality: str
    created_at: datetime

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "MarketCandleRecord":
        return cls(_uuid(payload, "id"), _uuid(payload, "asset_id"), _text(payload, "provider"), _text(payload, "provider_symbol"), _text(payload, "interval"), _datetime(payload, "observed_at"), _decimal(payload, "open"), _decimal(payload, "high"), _decimal(payload, "low"), _decimal(payload, "close"), _nullable_decimal(payload, "volume"), _nullable_decimal(payload, "adjusted_close"), _datetime(payload, "received_at"), _text(payload, "quality"), _datetime(payload, "created_at"))
