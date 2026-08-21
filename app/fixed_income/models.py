from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID
from app.market_data.models import DataQuality
class FixedIncomeError(ValueError): pass
@dataclass(frozen=True,slots=True)
class FixedIncomeInstrument:
    asset_id:UUID; provider:str; provider_symbol:str; bond_type:str; indexer:str; coupon_type:str|None; maturity_date:date; currency_code:str
@dataclass(frozen=True,slots=True)
class FixedIncomeSnapshot:
    asset_id:UUID; provider_symbol:str; reference_date:date; buy_rate:Decimal|None; sell_rate:Decimal|None; buy_price:Decimal|None; sell_price:Decimal|None; base_price:Decimal|None; received_at:datetime; quality:DataQuality|None
    def __post_init__(self):
        if self.received_at.tzinfo is None or self.received_at.utcoffset() is None: raise FixedIncomeError("received_at deve possuir timezone")
        object.__setattr__(self,"received_at",self.received_at.astimezone(UTC))
        for value in (self.buy_rate,self.sell_rate,self.buy_price,self.sell_price,self.base_price):
            if value is not None and (not isinstance(value,Decimal) or not value.is_finite()): raise FixedIncomeError("taxas e preços devem ser Decimal finito")
@dataclass(frozen=True,slots=True)
class FixedIncomeHistoryPoint(FixedIncomeSnapshot): pass
