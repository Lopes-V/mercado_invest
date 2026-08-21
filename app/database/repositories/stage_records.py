"""Typed PostgREST repositories for the post-Stage-4 tables.

They deliberately use inserts/updates only: idempotency is owned by services and DB
constraints, never an implicit upsert.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from supabase import Client
from app.database.models import RepositoryDataError, _datetime, _decimal, _nullable_datetime, _nullable_text, _text, _uuid
from app.database.repositories._response import create_one, read_one_or_none

def _rows(response, operation, parser):
    data=getattr(response,"data",None)
    if not isinstance(data,list): raise RepositoryDataError(f"{operation} retornou dados inválidos")
    return tuple(parser(row) for row in data)
def _payload(**kwargs):
    return {key:(str(value) if isinstance(value,(UUID,Decimal)) else value.isoformat() if isinstance(value,datetime) else value) for key,value in kwargs.items()}
@dataclass(frozen=True,slots=True)
class AnalysisRecord:
    id:UUID;asset_id:UUID;interval:str;reference_at:datetime;algorithm_version:str;created_at:datetime
    @classmethod
    def from_payload(cls,p:Mapping[str,object]):return cls(_uuid(p,"id"),_uuid(p,"asset_id"),_text(p,"interval"),_datetime(p,"reference_at"),_text(p,"algorithm_version"),_datetime(p,"created_at"))
@dataclass(frozen=True,slots=True)
class AnalysisMetricRecord:
    id:UUID;analysis_id:UUID;metric_name:str;metric_value:Decimal;reference_period:int|None;created_at:datetime
    @classmethod
    def from_payload(cls,p):
        value=p.get("reference_period");
        if value is not None and (isinstance(value,bool) or not isinstance(value,int)):raise RepositoryDataError("reference_period inválido")
        return cls(_uuid(p,"id"),_uuid(p,"analysis_id"),_text(p,"metric_name"),_decimal(p,"metric_value"),value,_datetime(p,"created_at"))
class AnalysisRepository:
    def __init__(self,client:Client):self._client=client
    def create(self,**kwargs):return create_one(self._client.table("analyses").insert(_payload(**kwargs)).execute(),operation="create analysis",parser=AnalysisRecord.from_payload)
    def get_by_id(self,record_id:UUID):return read_one_or_none(self._client.table("analyses").select("*").eq("id",str(record_id)),operation="get analysis",parser=AnalysisRecord.from_payload)
    def get_latest_for_asset(self,asset_id:UUID,interval:str):return read_one_or_none(self._client.table("analyses").select("*").eq("asset_id",str(asset_id)).eq("interval",interval).order("reference_at",desc=True),operation="latest analysis",parser=AnalysisRecord.from_payload)
class AnalysisMetricRepository:
    def __init__(self,client:Client):self._client=client
    def create_many(self,*,analysis_id:UUID,metrics):
        data=[_payload(analysis_id=analysis_id,metric_name=item.name,metric_value=item.value,reference_period=item.reference_period) for item in metrics]
        return _rows(self._client.table("analysis_metrics").insert(data).execute(),"create metrics",AnalysisMetricRecord.from_payload)
    def list_by_analysis(self,analysis_id:UUID):return _rows(self._client.table("analysis_metrics").select("*").eq("analysis_id",str(analysis_id)).order("metric_name").execute(),"list metrics",AnalysisMetricRecord.from_payload)

@dataclass(frozen=True,slots=True)
class AIRunRecord:
    id:UUID;asset_id:UUID;provider:str;model:str;classification:str;confidence:Decimal;summary:str;started_at:datetime;finished_at:datetime;created_at:datetime
    @classmethod
    def from_payload(cls,p):return cls(_uuid(p,"id"),_uuid(p,"asset_id"),_text(p,"provider"),_text(p,"model"),_text(p,"classification"),_decimal(p,"confidence"),_text(p,"summary"),_datetime(p,"started_at"),_datetime(p,"finished_at"),_datetime(p,"created_at"))
class AIRunRepository:
    def __init__(self,client):self._client=client
    def create(self,**kwargs):return create_one(self._client.table("ai_runs").insert(_payload(**kwargs)).execute(),operation="create AI run",parser=AIRunRecord.from_payload)
    def get_by_id(self,record_id):return read_one_or_none(self._client.table("ai_runs").select("*").eq("id",str(record_id)),operation="get AI run",parser=AIRunRecord.from_payload)
    def get_latest_for_asset(self,asset_id):return read_one_or_none(self._client.table("ai_runs").select("*").eq("asset_id",str(asset_id)).order("finished_at",desc=True),operation="latest AI run",parser=AIRunRecord.from_payload)

@dataclass(frozen=True,slots=True)
class OpportunityRecord:
    id:UUID;asset_id:UUID;analysis_id:UUID;level:str;score:Decimal;evidence_count:int;evaluated_at:datetime;policy_version:str;created_at:datetime
    @classmethod
    def from_payload(cls,p):
        count=p.get("evidence_count");
        if isinstance(count,bool) or not isinstance(count,int):raise RepositoryDataError("evidence_count inválido")
        return cls(_uuid(p,"id"),_uuid(p,"asset_id"),_uuid(p,"analysis_id"),_text(p,"level"),_decimal(p,"score"),count,_datetime(p,"evaluated_at"),_text(p,"policy_version"),_datetime(p,"created_at"))
class OpportunityRepository:
    def __init__(self,client):self._client=client
    def create(self,**kwargs):return create_one(self._client.table("opportunities").insert(_payload(**kwargs)).execute(),operation="create opportunity",parser=OpportunityRecord.from_payload)
    def get_by_id(self,record_id):return read_one_or_none(self._client.table("opportunities").select("*").eq("id",str(record_id)),operation="get opportunity",parser=OpportunityRecord.from_payload)
    def get_latest_for_asset(self,asset_id):return read_one_or_none(self._client.table("opportunities").select("*").eq("asset_id",str(asset_id)).order("evaluated_at",desc=True),operation="latest opportunity",parser=OpportunityRecord.from_payload)
    def list_recent_for_asset(self,asset_id,limit):return _rows(self._client.table("opportunities").select("*").eq("asset_id",str(asset_id)).order("evaluated_at",desc=True).limit(limit).execute(),"recent opportunities",OpportunityRecord.from_payload)

@dataclass(frozen=True,slots=True)
class AlertRecord:
    id:UUID;asset_id:UUID;opportunity_id:UUID;channel:str;status:str;dedupe_key:str;decided_at:datetime;sent_at:datetime|None
    @classmethod
    def from_payload(cls,p):return cls(_uuid(p,"id"),_uuid(p,"asset_id"),_uuid(p,"opportunity_id"),_text(p,"channel"),_text(p,"status"),_text(p,"dedupe_key"),_datetime(p,"decided_at"),_nullable_datetime(p,"sent_at"))
class AlertRepository:
    def __init__(self,client):self._client=client
    def create_pending(self,**kwargs):return create_one(self._client.table("alerts").insert(_payload(status="PENDING",**kwargs)).execute(),operation="create alert",parser=AlertRecord.from_payload)
    def _mark(self,record_id,status,**kwargs):return create_one(self._client.table("alerts").update(_payload(status=status,**kwargs)).eq("id",str(record_id)).execute(),operation=f"mark alert {status}",parser=AlertRecord.from_payload)
    def mark_sent(self,*,alert_id,sent_at):return self._mark(alert_id,"SENT",sent_at=sent_at)
    def mark_suppressed(self,*,alert_id,reason):return self._mark(alert_id,"SUPPRESSED",suppression_reason=reason)
    def mark_failed(self,*,alert_id,error_code,error_message):return self._mark(alert_id,"FAILED",error_code=error_code,error_message=error_message)
    def get_by_id(self,record_id):return read_one_or_none(self._client.table("alerts").select("*").eq("id",str(record_id)),operation="get alert",parser=AlertRecord.from_payload)
    def get_by_dedupe_key(self,key):return read_one_or_none(self._client.table("alerts").select("*").eq("dedupe_key",key),operation="get alert dedupe",parser=AlertRecord.from_payload)
    def get_latest_sent_for_asset(self,asset_id):return read_one_or_none(self._client.table("alerts").select("*").eq("asset_id",str(asset_id)).eq("status","SENT").order("sent_at",desc=True),operation="latest sent alert",parser=AlertRecord.from_payload)

@dataclass(frozen=True,slots=True)
class BacktestRunRecord:
    id:UUID;asset_id:UUID;interval:str;started_at:datetime;ended_at:datetime;algorithm_version:str;opportunity_policy_version:str
    @classmethod
    def from_payload(cls,p):return cls(_uuid(p,"id"),_uuid(p,"asset_id"),_text(p,"interval"),_datetime(p,"started_at"),_datetime(p,"ended_at"),_text(p,"algorithm_version"),_text(p,"opportunity_policy_version"))
@dataclass(frozen=True,slots=True)
class BacktestEventRecord:
    id:UUID;backtest_run_id:UUID;signal_at:datetime;score:Decimal;entry_reference_price:Decimal;forward_reference_price:Decimal;forward_return:Decimal
    @classmethod
    def from_payload(cls,p):return cls(_uuid(p,"id"),_uuid(p,"backtest_run_id"),_datetime(p,"signal_at"),_decimal(p,"score"),_decimal(p,"entry_reference_price"),_decimal(p,"forward_reference_price"),_decimal(p,"forward_return"))
class BacktestRunRepository:
    def __init__(self,client):self._client=client
    def create(self,**kwargs):return create_one(self._client.table("backtest_runs").insert(_payload(**kwargs)).execute(),operation="create backtest run",parser=BacktestRunRecord.from_payload)
    def finish(self,*,run_id,ended_at):return create_one(self._client.table("backtest_runs").update(_payload(ended_at=ended_at)).eq("id",str(run_id)).execute(),operation="finish backtest run",parser=BacktestRunRecord.from_payload)
    def get_by_id(self,record_id):return read_one_or_none(self._client.table("backtest_runs").select("*").eq("id",str(record_id)),operation="get backtest run",parser=BacktestRunRecord.from_payload)
class BacktestEventRepository:
    def __init__(self,client):self._client=client
    def create_many(self,*,backtest_run_id,events):return _rows(self._client.table("backtest_events").insert([_payload(backtest_run_id=backtest_run_id,signal_at=e.signal_at,level=e.level.value,score=e.score,entry_reference_price=e.entry_reference_price,forward_reference_price=e.forward_reference_price,forward_return=e.forward_return) for e in events]).execute(),"create backtest events",BacktestEventRecord.from_payload)
    def list_by_run(self,run_id):return _rows(self._client.table("backtest_events").select("*").eq("backtest_run_id",str(run_id)).order("signal_at").execute(),"list backtest events",BacktestEventRecord.from_payload)

@dataclass(frozen=True,slots=True)
class PaperAccountRecord:
    id:UUID;name:str;base_currency_code:str;initial_cash:Decimal;created_at:datetime
    @classmethod
    def from_payload(cls,p):return cls(_uuid(p,"id"),_text(p,"name"),_text(p,"base_currency_code"),_decimal(p,"initial_cash"),_datetime(p,"created_at"))
@dataclass(frozen=True,slots=True)
class PaperOrderRecord:
    id:UUID;account_id:UUID;asset_id:UUID;side:str;quantity:Decimal;status:str;requested_at:datetime
    @classmethod
    def from_payload(cls,p):return cls(_uuid(p,"id"),_uuid(p,"account_id"),_uuid(p,"asset_id"),_text(p,"side"),_decimal(p,"quantity"),_text(p,"status"),_datetime(p,"requested_at"))
@dataclass(frozen=True,slots=True)
class PaperTradeRecord:
    id:UUID;order_id:UUID;asset_id:UUID;side:str;quantity:Decimal;price:Decimal;fees:Decimal;executed_at:datetime
    @classmethod
    def from_payload(cls,p):return cls(_uuid(p,"id"),_uuid(p,"order_id"),_uuid(p,"asset_id"),_text(p,"side"),_decimal(p,"quantity"),_decimal(p,"price"),_decimal(p,"fees"),_datetime(p,"executed_at"))
class PaperAccountRepository:
    def __init__(self,client):self._client=client
    def create(self,**kwargs):return create_one(self._client.table("paper_accounts").insert(_payload(**kwargs)).execute(),operation="create paper account",parser=PaperAccountRecord.from_payload)
    def get_by_id(self,record_id):return read_one_or_none(self._client.table("paper_accounts").select("*").eq("id",str(record_id)),operation="get paper account",parser=PaperAccountRecord.from_payload)
class PaperOrderRepository:
    def __init__(self,client):self._client=client
    def create(self,**kwargs):return create_one(self._client.table("paper_orders").insert(_payload(status="PENDING",**kwargs)).execute(),operation="create paper order",parser=PaperOrderRecord.from_payload)
    def update_status(self,*,order_id,status):return create_one(self._client.table("paper_orders").update({"status":status}).eq("id",str(order_id)).execute(),operation="update paper order",parser=PaperOrderRecord.from_payload)
    def mark_filled(self,*,order_id):return self.update_status(order_id=order_id,status="FILLED")
    def get_by_id(self,record_id):return read_one_or_none(self._client.table("paper_orders").select("*").eq("id",str(record_id)),operation="get paper order",parser=PaperOrderRecord.from_payload)
    def list_by_account(self,account_id):return _rows(self._client.table("paper_orders").select("*").eq("account_id",str(account_id)).order("requested_at").execute(),"list paper orders",PaperOrderRecord.from_payload)
class PaperTradeRepository:
    def __init__(self,client):self._client=client
    def create(self,**kwargs):return create_one(self._client.table("paper_trades").insert(_payload(**kwargs)).execute(),operation="create paper trade",parser=PaperTradeRecord.from_payload)
    def get_by_id(self,record_id):return read_one_or_none(self._client.table("paper_trades").select("*").eq("id",str(record_id)),operation="get paper trade",parser=PaperTradeRecord.from_payload)
    def list_by_account(self,account_id):return _rows(self._client.table("paper_trades").select("*, paper_orders!inner(account_id)").eq("paper_orders.account_id",str(account_id)).order("executed_at").execute(),"list paper trades",PaperTradeRecord.from_payload)

@dataclass(frozen=True,slots=True)
class FixedIncomeInstrumentRecord:
    id:UUID;asset_id:UUID;provider:str;provider_symbol:str;bond_type:str;indexer:str;maturity_date:str;currency_code:str
    @classmethod
    def from_payload(cls,p):return cls(_uuid(p,"id"),_uuid(p,"asset_id"),_text(p,"provider"),_text(p,"provider_symbol"),_text(p,"bond_type"),_text(p,"indexer"),_text(p,"maturity_date"),_text(p,"currency_code"))
@dataclass(frozen=True,slots=True)
class FixedIncomeSnapshotRecord:
    id:UUID;asset_id:UUID;provider_symbol:str;reference_date:str;buy_rate:Decimal|None;sell_rate:Decimal|None;buy_price:Decimal|None;sell_price:Decimal|None;base_price:Decimal|None;received_at:datetime;quality:str
    @classmethod
    def from_payload(cls,p):
        nullable=lambda key:None if p.get(key) is None else _decimal(p,key)
        return cls(_uuid(p,"id"),_uuid(p,"asset_id"),_text(p,"provider_symbol"),_text(p,"reference_date"),nullable("buy_rate"),nullable("sell_rate"),nullable("buy_price"),nullable("sell_price"),nullable("base_price"),_datetime(p,"received_at"),_text(p,"quality"))
class FixedIncomeInstrumentRepository:
    def __init__(self,client):self._client=client
    def create(self,**kwargs):return create_one(self._client.table("fixed_income_instruments").insert(_payload(**kwargs)).execute(),operation="create fixed income instrument",parser=FixedIncomeInstrumentRecord.from_payload)
    def get_by_id(self,record_id):return read_one_or_none(self._client.table("fixed_income_instruments").select("*").eq("id",str(record_id)),operation="get fixed income instrument",parser=FixedIncomeInstrumentRecord.from_payload)
    def get_by_provider_symbol(self,provider,provider_symbol):return read_one_or_none(self._client.table("fixed_income_instruments").select("*").eq("provider",provider).eq("provider_symbol",provider_symbol),operation="get fixed income instrument provider symbol",parser=FixedIncomeInstrumentRecord.from_payload)
class FixedIncomeSnapshotRepository:
    def __init__(self,client):self._client=client
    def create(self,**kwargs):return create_one(self._client.table("fixed_income_snapshots").insert(_payload(**kwargs)).execute(),operation="create fixed income snapshot",parser=FixedIncomeSnapshotRecord.from_payload)
    def get_latest(self,asset_id,provider):return read_one_or_none(self._client.table("fixed_income_snapshots").select("*, fixed_income_instruments!inner(provider)").eq("asset_id",str(asset_id)).eq("fixed_income_instruments.provider",provider).order("reference_date",desc=True),operation="latest fixed income snapshot",parser=FixedIncomeSnapshotRecord.from_payload)
class FixedIncomeHistoryRepository:
    def __init__(self,client):self._client=client
    def create_many(self,items):return _rows(self._client.table("fixed_income_history").insert([_payload(**item) for item in items]).execute(),"create fixed income history",FixedIncomeSnapshotRecord.from_payload)
    def get_range(self,asset_id,provider,start,end):return _rows(self._client.table("fixed_income_history").select("*, fixed_income_instruments!inner(provider)").eq("asset_id",str(asset_id)).eq("fixed_income_instruments.provider",provider).gte("reference_date",str(start)).lte("reference_date",str(end)).order("reference_date").execute(),"fixed income history range",FixedIncomeSnapshotRecord.from_payload)

@dataclass(frozen=True,slots=True)
class FxRateRecord:
    id:UUID;base_currency_code:str;quote_currency_code:str;rate:Decimal;observed_at:datetime;received_at:datetime;provider:str;quality:str
    @classmethod
    def from_payload(cls,p):return cls(_uuid(p,"id"),_text(p,"base_currency_code"),_text(p,"quote_currency_code"),_decimal(p,"rate"),_datetime(p,"observed_at"),_datetime(p,"received_at"),_text(p,"provider"),_text(p,"quality"))
class FxRateRepository:
    def __init__(self,client):self._client=client
    def create(self,**kwargs):return create_one(self._client.table("fx_rates").insert(_payload(**kwargs)).execute(),operation="create fx rate",parser=FxRateRecord.from_payload)
    def get_by_id(self,record_id):return read_one_or_none(self._client.table("fx_rates").select("*").eq("id",str(record_id)),operation="get fx rate",parser=FxRateRecord.from_payload)
    def get_latest(self,base_currency_code,quote_currency_code,provider):return read_one_or_none(self._client.table("fx_rates").select("*").eq("base_currency_code",base_currency_code).eq("quote_currency_code",quote_currency_code).eq("provider",provider).order("observed_at",desc=True),operation="latest fx rate",parser=FxRateRecord.from_payload)
    def get_range(self,base_currency_code,quote_currency_code,provider,start,end):return _rows(self._client.table("fx_rates").select("*").eq("base_currency_code",base_currency_code).eq("quote_currency_code",quote_currency_code).eq("provider",provider).gte("observed_at",start.isoformat()).lte("observed_at",end.isoformat()).order("observed_at").execute(),"fx range",FxRateRecord.from_payload)
