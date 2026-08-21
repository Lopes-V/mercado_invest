from dataclasses import dataclass
from decimal import Decimal
from typing import Callable
from app.market_data.models import Candle, DataQuality
from app.opportunity.core import OpportunityAssessment
from typing import Protocol
from uuid import UUID
@dataclass(frozen=True,slots=True)
class BacktestConfig: window_size:int; forward_horizon:int; analysis_version:str; opportunity_policy_version:str
@dataclass(frozen=True,slots=True)
class BacktestEvent: signal_at:object; level:object; score:Decimal; entry_reference_price:Decimal; forward_reference_price:Decimal; forward_return:Decimal
@dataclass(frozen=True,slots=True)
class BacktestSummary: observations:int; signals:int; positive_outcomes:int; hit_rate:Decimal; average_forward_return:Decimal; max_forward_gain:Decimal; max_forward_loss:Decimal
class BacktestEngine:
    """Walk-forward runner. `signal` sees a tuple ending at T and never future candles."""
    def run(self,candles:tuple[Candle,...]|list[Candle],*,config:BacktestConfig,signal:Callable[[tuple[Candle,...]],OpportunityAssessment])->tuple[tuple[BacktestEvent,...],BacktestSummary]:
        ordered=tuple(sorted(candles,key=lambda item:item.timestamp))
        if config.window_size<=0 or config.forward_horizon<=0: raise ValueError("window_size e forward_horizon devem ser positivos")
        if any(item.quality is not DataQuality.VALID for item in ordered): raise ValueError("backtest requer candles VALID")
        events=[]
        for index in range(config.window_size-1,len(ordered)-config.forward_horizon):
            window=ordered[index-config.window_size+1:index+1]; assessment=signal(window)
            if assessment.level.value in ("INTERESTING","HIGH_INTEREST"):
                entry=window[-1].close; future=ordered[index+config.forward_horizon].close
                events.append(BacktestEvent(window[-1].timestamp,assessment.level,assessment.score,entry,future,(future-entry)/entry))
        returns=[event.forward_return for event in events]
        summary=BacktestSummary(len(ordered),len(events),sum(item>0 for item in returns),Decimal(sum(item>0 for item in returns))/Decimal(len(returns)) if returns else Decimal("0"),sum(returns)/Decimal(len(returns)) if returns else Decimal("0"),max(returns,default=Decimal("0")),min(returns,default=Decimal("0")))
        return tuple(events),summary

class BacktestRunRepository(Protocol):
    def create(self, **payload): ...
class BacktestEventRepository(Protocol):
    def create_many(self, *, backtest_run_id: UUID, events: tuple[BacktestEvent,...]): ...
class BacktestService:
    def __init__(self, *, engine: BacktestEngine, runs: BacktestRunRepository, events: BacktestEventRepository): self._engine,self._runs,self._events=engine,runs,events
    def run(self, *, asset_id: UUID, interval: str, candles: tuple[Candle,...], config: BacktestConfig, signal):
        events,summary=self._engine.run(candles,config=config,signal=signal)
        record=self._runs.create(asset_id=asset_id,interval=interval,started_at=candles[0].timestamp,ended_at=candles[-1].timestamp,algorithm_version=config.analysis_version,opportunity_policy_version=config.opportunity_policy_version)
        self._events.create_many(backtest_run_id=record.id,events=events)
        return events,summary
