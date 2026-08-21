from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Mapping
from uuid import UUID
from app.fixed_income.models import FixedIncomeHistoryPoint,FixedIncomeInstrument,FixedIncomeSnapshot
from app.market_data.errors import ProviderResponseError
from app.market_data.http import ProviderHttpClient
@dataclass(frozen=True,slots=True)
class FixedIncomeQualityPolicy: max_age:timedelta; future_tolerance:timedelta
class BrapiTreasuryProvider:
    name="brapi_treasury"
    def __init__(self,http_client:ProviderHttpClient,*,token:str|None=None,clock=lambda:datetime.now(UTC)):
        self._http=http_client;self._token=token;self._clock=clock
    def list_instruments(self,*,asset_id_by_symbol:Mapping[str,UUID],indexer:str|None=None)->tuple[FixedIncomeInstrument,...]:
        payload=self._get("/api/v2/treasury/list",{"indexer":indexer} if indexer else None); rows=self._rows(payload)
        result=[]
        for row in rows:
            symbol=self._text(row,"symbol"); asset_id=asset_id_by_symbol.get(symbol)
            if asset_id is None: continue
            result.append(FixedIncomeInstrument(asset_id,self.name,symbol,self._text(row,"bondType"),self._text(row,"indexer"),row.get("couponType") if isinstance(row.get("couponType"),str) else None,date.fromisoformat(self._text(row,"maturityDate")),self._text(row,"currency")))
        return tuple(result)
    def get_snapshot(self,*,asset_id:UUID,symbol:str)->FixedIncomeSnapshot:
        rows=self._rows(self._get("/api/v2/treasury/indicators",{"symbols":symbol}));
        if len(rows)!=1:raise ProviderResponseError("BRAPI treasury deve retornar exatamente um resultado")
        return self._point(rows[0],asset_id,symbol,FixedIncomeSnapshot)
    def get_history(self,*,asset_id:UUID,symbol:str,start:date,end:date)->tuple[FixedIncomeHistoryPoint,...]:
        if start>end:raise ValueError("start não pode ser posterior a end")
        rows=self._rows(self._get("/api/v2/treasury/indicators/history",{"symbols":symbol,"startDate":start.isoformat(),"endDate":end.isoformat(),"sortOrder":"asc"}));
        if len(rows)!=1:raise ProviderResponseError("BRAPI treasury deve retornar uma série")
        history=rows[0].get("historicalData") or rows[0].get("history")
        if not isinstance(history,list):raise ProviderResponseError("histórico treasury ausente")
        return tuple(self._point(item,asset_id,symbol,FixedIncomeHistoryPoint) for item in history if isinstance(item,Mapping))
    def _get(self,path:str,params:dict[str,str]|None):return self._http.get_json(path,params=params,headers={"Authorization":f"Bearer {self._token}"} if self._token else None)
    @staticmethod
    def _rows(payload:object)->list[Mapping[str,object]]:
        if not isinstance(payload,Mapping) or not isinstance(payload.get("results"),list):raise ProviderResponseError("resposta treasury inválida")
        rows=payload["results"]
        if not all(isinstance(row,Mapping) for row in rows):raise ProviderResponseError("resultado treasury inválido")
        return rows
    @staticmethod
    def _text(row:Mapping[str,object],field:str)->str:
        value=row.get(field)
        if not isinstance(value,str) or not value.strip():raise ProviderResponseError(f"{field} ausente")
        return value
    def _point(self,row:Mapping[str,object],asset_id:UUID,symbol:str,cls:type[FixedIncomeSnapshot])->FixedIncomeSnapshot:
        def dec(name):
            value=row.get(name)
            if value is None:return None
            if isinstance(value,bool) or not isinstance(value,(Decimal,int)):raise ProviderResponseError(f"{name} deve ser decimal")
            return Decimal(value)
        raw=row.get("baseDate") or row.get("referenceDate")
        if not isinstance(raw,str):raise ProviderResponseError("baseDate ausente")
        return cls(asset_id,symbol,date.fromisoformat(raw[:10]),dec("buyRate"),dec("sellRate"),dec("buyPrice"),dec("sellPrice"),dec("basePrice"),self._clock(),None)

class FixedIncomeService:
    """Persists only the explicitly assessed snapshot/history supplied by its provider boundary."""
    def __init__(self, *, provider: BrapiTreasuryProvider, snapshots, history): self._provider,self._snapshots,self._history=provider,snapshots,history
    def ingest_snapshot(self, *, asset_id: UUID, symbol: str, quality):
        snapshot=self._provider.get_snapshot(asset_id=asset_id,symbol=symbol)
        if quality is None: raise ValueError("quality avaliada é obrigatória antes da persistência")
        return self._snapshots.create(asset_id=asset_id,provider_symbol=symbol,reference_date=snapshot.reference_date,buy_rate=snapshot.buy_rate,sell_rate=snapshot.sell_rate,buy_price=snapshot.buy_price,sell_price=snapshot.sell_price,base_price=snapshot.base_price,received_at=snapshot.received_at,quality=quality.value)
