from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID
from app.market_data.models import Candle
from typing import Protocol
class PaperSide(StrEnum): BUY="BUY"; SELL="SELL"
@dataclass(frozen=True,slots=True)
class PaperAccount: account_id:UUID; cash:Decimal; positions:tuple[tuple[UUID,Decimal],...]=()
@dataclass(frozen=True,slots=True)
class PaperOrder: account_id:UUID; asset_id:UUID; side:PaperSide; quantity:Decimal; requested_at:datetime
@dataclass(frozen=True,slots=True)
class PaperTrade: order:PaperOrder; price:Decimal; fees:Decimal; executed_at:datetime
class PaperExecutionEngine:
    """Simulation only: fills at an explicitly supplied next candle OPEN, never the signal candle."""
    def __init__(self,*,slippage:Decimal=Decimal("0"),fee:Decimal=Decimal("0")): self.slippage=slippage; self.fee=fee
    def execute(self,account:PaperAccount,order:PaperOrder,*,next_candle:Candle)->tuple[PaperAccount,PaperTrade]:
        if order.quantity<=0: raise ValueError("quantity deve ser positiva")
        price=next_candle.open*(Decimal("1")+self.slippage if order.side is PaperSide.BUY else Decimal("1")-self.slippage); total=order.quantity*price+self.fee; positions=dict(account.positions); held=positions.get(order.asset_id,Decimal("0"))
        if order.side is PaperSide.BUY:
            if total>account.cash: raise ValueError("paper account sem cash suficiente")
            cash=account.cash-total; positions[order.asset_id]=held+order.quantity
        else:
            if order.quantity>held: raise ValueError("paper account sem posição suficiente")
            cash=account.cash+order.quantity*price-self.fee; positions[order.asset_id]=held-order.quantity
        return PaperAccount(account.account_id,cash,tuple(sorted(positions.items(),key=lambda item:str(item[0])))),PaperTrade(order,price,self.fee,next_candle.timestamp)

class PaperAccountRepository(Protocol):
    def get_by_id(self, account_id: UUID): ...
class PaperOrderRepository(Protocol):
    def create(self, **payload): ...
    def mark_filled(self, *, order_id: UUID): ...
class PaperTradeRepository(Protocol):
    def create(self, **payload): ...
class PaperTradingService:
    def __init__(self, *, engine: PaperExecutionEngine, accounts: PaperAccountRepository, orders: PaperOrderRepository, trades: PaperTradeRepository): self._engine,self._accounts,self._orders,self._trades=engine,accounts,orders,trades
    def execute_next_open(self, *, account_id: UUID, asset_id: UUID, side: PaperSide, quantity: Decimal, requested_at: datetime, next_candle: Candle):
        account=self._accounts.get_by_id(account_id); order_record=self._orders.create(account_id=account_id,asset_id=asset_id,side=side.value,quantity=str(quantity),requested_at=requested_at)
        updated,trade=self._engine.execute(account,PaperOrder(account_id,asset_id,side,quantity,requested_at),next_candle=next_candle)
        self._trades.create(order_id=order_record.id,asset_id=asset_id,side=side.value,quantity=str(quantity),price=str(trade.price),fees=str(trade.fees),executed_at=trade.executed_at);self._orders.mark_filled(order_id=order_record.id)
        return updated,trade
