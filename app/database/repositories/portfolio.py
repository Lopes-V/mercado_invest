from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from supabase import Client
from app.database.models import RepositoryDataError, _datetime, _decimal, _text, _uuid
from app.database.repositories._response import create_one,read_one_or_none

@dataclass(frozen=True,slots=True)
class PortfolioRecord:
    id:UUID; name:str; base_currency_code:str; is_active:bool; created_at:datetime; updated_at:datetime
    @classmethod
    def from_payload(cls,p:Mapping[str,object]):
        value=p.get("is_active")
        if not isinstance(value,bool):raise RepositoryDataError("is_active deve ser booleano")
        return cls(_uuid(p,"id"),_text(p,"name"),_text(p,"base_currency_code"),value,_datetime(p,"created_at"),_datetime(p,"updated_at"))
@dataclass(frozen=True,slots=True)
class PortfolioTransactionRecord:
    id:UUID;portfolio_id:UUID;asset_id:UUID;transaction_type:str;quantity:Decimal;unit_price:Decimal;fees:Decimal;currency_code:str;occurred_at:datetime
    @classmethod
    def from_payload(cls,p:Mapping[str,object]):return cls(_uuid(p,"id"),_uuid(p,"portfolio_id"),_uuid(p,"asset_id"),_text(p,"transaction_type"),_decimal(p,"quantity"),_decimal(p,"unit_price"),_decimal(p,"fees"),_text(p,"currency_code"),_datetime(p,"occurred_at"))
class PortfolioRepository:
    def __init__(self,client:Client):self._client=client
    def create(self,*,name:str,base_currency_code:str)->PortfolioRecord:return create_one(self._client.table("portfolios").insert({"name":name,"base_currency_code":base_currency_code}).execute(),operation="create portfolio",parser=PortfolioRecord.from_payload)
    def get_by_id(self,portfolio_id:UUID)->PortfolioRecord|None:return read_one_or_none(self._client.table("portfolios").select("*").eq("id",str(portfolio_id)),operation="get portfolio",parser=PortfolioRecord.from_payload)
class PortfolioTransactionRepository:
    def __init__(self,client:Client):self._client=client
    def create(self,*,portfolio_id:UUID,asset_id:UUID,transaction_type:str,quantity:Decimal,unit_price:Decimal,fees:Decimal,currency_code:str,occurred_at:datetime,external_reference:str|None=None)->PortfolioTransactionRecord:
        payload={"portfolio_id":str(portfolio_id),"asset_id":str(asset_id),"transaction_type":transaction_type,"quantity":str(quantity),"unit_price":str(unit_price),"fees":str(fees),"currency_code":currency_code,"occurred_at":occurred_at.isoformat(),"external_reference":external_reference}
        return create_one(self._client.table("portfolio_transactions").insert(payload).execute(),operation="create portfolio transaction",parser=PortfolioTransactionRecord.from_payload)

@dataclass(frozen=True,slots=True)
class PortfolioSnapshotRecord:
    id:UUID;portfolio_id:UUID;as_of:datetime;total_cost_basis:Decimal;market_value:Decimal;unrealized_pnl:Decimal
    @classmethod
    def from_payload(cls,p:Mapping[str,object]):return cls(_uuid(p,"id"),_uuid(p,"portfolio_id"),_datetime(p,"as_of"),_decimal(p,"total_cost_basis"),_decimal(p,"market_value"),_decimal(p,"unrealized_pnl"))
class PortfolioSnapshotRepository:
    def __init__(self,client:Client):self._client=client
    def create(self,*,portfolio_id:UUID,as_of:datetime,total_cost_basis:Decimal,market_value:Decimal,unrealized_pnl:Decimal)->PortfolioSnapshotRecord:
        return create_one(self._client.table("portfolio_snapshots").insert({"portfolio_id":str(portfolio_id),"as_of":as_of.isoformat(),"total_cost_basis":str(total_cost_basis),"market_value":str(market_value),"unrealized_pnl":str(unrealized_pnl)}).execute(),operation="create portfolio snapshot",parser=PortfolioSnapshotRecord.from_payload)
