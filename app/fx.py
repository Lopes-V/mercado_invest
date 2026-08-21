from dataclasses import dataclass
from datetime import UTC,datetime
from decimal import Decimal
from typing import Protocol
from app.market_data.models import DataQuality
@dataclass(frozen=True,slots=True)
class NormalizedFxRate:
    base_currency_code:str;quote_currency_code:str;rate:Decimal;observed_at:datetime;received_at:datetime;provider:str;quality:DataQuality|None
class FxRateProvider(Protocol):
    def get_rate(self, *, base_currency_code:str, quote_currency_code:str) -> NormalizedFxRate: ...
class FxRateService:
    def __init__(self, *, provider:FxRateProvider, repository):self._provider,self._repository=provider,repository
    def ingest(self, *, base_currency_code:str, quote_currency_code:str, quality:DataQuality):
        rate=self._provider.get_rate(base_currency_code=base_currency_code,quote_currency_code=quote_currency_code)
        if rate.quality is not None: rate=NormalizedFxRate(rate.base_currency_code,rate.quote_currency_code,rate.rate,rate.observed_at,rate.received_at,rate.provider,quality)
        return self._repository.create(base_currency_code=rate.base_currency_code,quote_currency_code=rate.quote_currency_code,rate=rate.rate,observed_at=rate.observed_at,received_at=rate.received_at,provider=rate.provider,quality=quality.value)
