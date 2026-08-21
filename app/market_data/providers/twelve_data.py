from collections.abc import Mapping, Sequence
from datetime import UTC,datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from app.market_data.contracts import AssetSearchRequest,HistoryRequest,MarketStatusRequest,QuoteRequest
from app.market_data.errors import ProviderCapabilityError,ProviderResponseError
from app.market_data.http import ProviderHttpClient
from app.market_data.models import Candle,CandleInterval,MarketStatus,ProviderAsset,Quote,ensure_utc_datetime
_INTERVALS={CandleInterval.ONE_MINUTE:"1min",CandleInterval.FIVE_MINUTES:"5min",CandleInterval.FIFTEEN_MINUTES:"15min",CandleInterval.THIRTY_MINUTES:"30min",CandleInterval.ONE_HOUR:"1h",CandleInterval.ONE_DAY:"1day",CandleInterval.ONE_WEEK:"1week",CandleInterval.ONE_MONTH:"1month"}
class TwelveDataProvider:
    name="twelve_data"
    def __init__(self,http_client:ProviderHttpClient,*,api_key:str,clock=lambda:datetime.now(UTC)):
        if not isinstance(api_key,str) or not api_key.strip():raise ValueError("Twelve Data requer API key")
        self._http=http_client;self._key=api_key;self._clock=clock
    def _get(self,path,params):return self._http.get_json(path,params=params,headers={"Authorization":f"apikey {self._key}"})
    def get_quote(self,request:QuoteRequest)->Quote:
        row=self._mapping(self._get("/quote",{"symbol":request.provider_symbol}))
        if self._text(row,"symbol")!=request.provider_symbol:raise ProviderResponseError("symbol Twelve Data não corresponde ao mapping")
        return Quote(request.asset_id,request.provider_symbol,self._dec(row,"close"),self._text(row,"currency"),self._timestamp(row),ensure_utc_datetime(self._clock(),field="clock"),self.name,None)
    def get_history(self,request:HistoryRequest)->Sequence[Candle]:
        if request.start is None or request.end is None:raise ProviderCapabilityError("Twelve Data requer range explícito")
        payload=self._mapping(self._get("/time_series",{"symbol":request.provider_symbol,"interval":_INTERVALS[request.interval],"start_date":request.start.isoformat(),"end_date":request.end.isoformat(),"order":"ASC"})); meta=self._mapping(payload.get("meta")); values=payload.get("values")
        if not isinstance(values,list):raise ProviderResponseError("values ausente")
        received=ensure_utc_datetime(self._clock(),field="clock"); return tuple(Candle(request.asset_id,request.provider_symbol,self._local_timestamp(self._text(row,"datetime"),self._text(meta,"exchange_timezone")),self._dec(row,"open"),self._dec(row,"high"),self._dec(row,"low"),self._dec(row,"close"),self._optional_dec(row.get("volume")),request.interval,self.name,received,None) for row in values if isinstance(row,Mapping))
    def get_assets(self,request:AssetSearchRequest)->Sequence[ProviderAsset]:
        if request.market_code or request.exchange_code:raise ProviderCapabilityError("Twelve Data symbol_search não garante esses filtros")
        payload=self._mapping(self._get("/symbol_search",{"symbol":request.query or ""})); rows=payload.get("data")
        if not isinstance(rows,list):raise ProviderResponseError("symbol_search inválido")
        return tuple(ProviderAsset(self.name,self._text(row,"symbol"),self._text(row,"instrument_name"),row.get("instrument_type") if isinstance(row.get("instrument_type"),str) else None,row.get("currency") if isinstance(row.get("currency"),str) else None,row.get("exchange") if isinstance(row.get("exchange"),str) else None,None,None) for row in rows if isinstance(row,Mapping))
    def get_market_status(self,request:MarketStatusRequest)->MarketStatus: raise ProviderCapabilityError("market status não implementado no adapter Twelve Data")
    @staticmethod
    def _mapping(value):
        if not isinstance(value,Mapping):raise ProviderResponseError("resposta Twelve Data inválida")
        return value
    @staticmethod
    def _text(row,field):
        value=row.get(field)
        if not isinstance(value,str) or not value.strip():raise ProviderResponseError(f"{field} ausente")
        return value
    @staticmethod
    def _dec(row,field):
        value=row.get(field)
        if not isinstance(value,str):raise ProviderResponseError(f"{field} deve ser texto decimal")
        try:return Decimal(value)
        except Exception as exc:raise ProviderResponseError(f"{field} inválido") from exc
    @classmethod
    def _optional_dec(cls,value):return None if value is None else cls._dec({"value":value},"value")
    @classmethod
    def _timestamp(cls,row):
        value=row.get("timestamp")
        if not isinstance(value,int):raise ProviderResponseError("timestamp ausente")
        return datetime.fromtimestamp(value,UTC)
    @staticmethod
    def _local_timestamp(value,timezone):
        try:return datetime.fromisoformat(value).replace(tzinfo=ZoneInfo(timezone)).astimezone(UTC)
        except Exception as exc:raise ProviderResponseError("datetime/timezone Twelve Data inválido") from exc
