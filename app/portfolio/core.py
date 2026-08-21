"""Deterministic portfolio accounting; this module has no broker or market-provider dependency."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.market_data.models import DataQuality


ZERO = Decimal("0")


class PortfolioError(ValueError):
    pass


class CurrencyConversionRequired(PortfolioError):
    pass


class TransactionType(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


def _decimal(value: Decimal, field: str, *, positive: bool = False) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or (value <= ZERO if positive else value < ZERO):
        raise PortfolioError(f"{field} deve ser Decimal finito {'positivo' if positive else 'não negativo'}")
    return value


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise PortfolioError(f"{field} deve possuir timezone")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class PortfolioTransaction:
    asset_id: UUID
    transaction_type: TransactionType
    quantity: Decimal
    unit_price: Decimal
    fees: Decimal
    currency_code: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.asset_id, UUID) or not isinstance(self.transaction_type, TransactionType):
            raise PortfolioError("transaction inválida")
        _decimal(self.quantity, "quantity", positive=True); _decimal(self.unit_price, "unit_price"); _decimal(self.fees, "fees")
        if not isinstance(self.currency_code, str) or not self.currency_code:
            raise PortfolioError("currency_code não pode ser vazio")
        object.__setattr__(self, "occurred_at", _utc(self.occurred_at, "occurred_at"))


@dataclass(frozen=True, slots=True)
class PortfolioPosition:
    asset_id: UUID
    quantity: Decimal
    average_cost: Decimal
    cost_basis: Decimal
    market_price: Decimal | None = None
    market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None


@dataclass(frozen=True, slots=True)
class PortfolioCalculation:
    positions: tuple[PortfolioPosition, ...]
    realized_pnl: Decimal


class PortfolioCalculator:
    def calculate(self, transactions: tuple[PortfolioTransaction, ...] | list[PortfolioTransaction]) -> PortfolioCalculation:
        state: dict[UUID, tuple[Decimal, Decimal]] = {}
        realized = ZERO
        for tx in sorted(transactions, key=lambda item: item.occurred_at):
            quantity, cost_basis = state.get(tx.asset_id, (ZERO, ZERO))
            if tx.transaction_type is TransactionType.BUY:
                quantity += tx.quantity; cost_basis += tx.quantity * tx.unit_price + tx.fees
            else:
                if tx.quantity > quantity:
                    raise PortfolioError("SELL não pode exceder posição existente")
                average = cost_basis / quantity
                realized += tx.quantity * tx.unit_price - tx.fees - tx.quantity * average
                quantity -= tx.quantity; cost_basis -= tx.quantity * average
                if quantity == ZERO:
                    cost_basis = ZERO
            state[tx.asset_id] = (quantity, cost_basis)
        positions = tuple(PortfolioPosition(asset, qty, (basis / qty if qty else ZERO), basis) for asset, (qty, basis) in sorted(state.items(), key=lambda entry: str(entry[0])))
        return PortfolioCalculation(positions, realized)


@dataclass(frozen=True, slots=True)
class Valuation:
    price: Decimal
    currency_code: str
    quality: DataQuality
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class FxRate:
    base_currency_code: str
    quote_currency_code: str
    rate: Decimal
    quality: DataQuality
    observed_at: datetime

    def __post_init__(self) -> None:
        _decimal(self.rate, "rate", positive=True)


class AssetValuationSource(Protocol):
    def get_valuation(self, asset_id: UUID, *, as_of: datetime) -> Valuation: ...


class FxRateProvider(Protocol):
    def get_fx_rate(self, *, base_currency_code: str, quote_currency_code: str, as_of: datetime) -> FxRate: ...


class PortfolioValuationService:
    def value(self, positions: tuple[PortfolioPosition, ...], *, source: AssetValuationSource, base_currency_code: str, as_of: datetime, fx_source: FxRateProvider | None = None) -> tuple[PortfolioPosition, ...]:
        _utc(as_of, "as_of")
        valued: list[PortfolioPosition] = []
        for position in positions:
            valuation = source.get_valuation(position.asset_id, as_of=as_of)
            if valuation.quality is not DataQuality.VALID:
                raise PortfolioError("valuation requer quote VALID")
            price = valuation.price
            if valuation.currency_code != base_currency_code:
                if fx_source is None:
                    raise CurrencyConversionRequired("conversão FX explícita é necessária")
                fx = fx_source.get_fx_rate(base_currency_code=valuation.currency_code, quote_currency_code=base_currency_code, as_of=as_of)
                if fx.quality is not DataQuality.VALID:
                    raise PortfolioError("conversão FX requer rate VALID")
                price *= fx.rate
            _decimal(price, "market_price")
            value = position.quantity * price
            valued.append(PortfolioPosition(position.asset_id, position.quantity, position.average_cost, position.cost_basis, price, value, value - position.cost_basis))
        return tuple(valued)
