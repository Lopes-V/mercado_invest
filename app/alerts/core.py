from dataclasses import dataclass
from datetime import datetime,timedelta
from decimal import Decimal
from app.market_data.models import DataQuality
from app.opportunity.core import OpportunityLevel
from typing import Protocol
from uuid import UUID
from app.security.redaction import sanitize_sensitive_text
@dataclass(frozen=True,slots=True)
class AlertPolicy: minimum_level:OpportunityLevel=OpportunityLevel.INTERESTING; cooldown:timedelta=timedelta(hours=24); max_alerts_per_run:int|None=None
@dataclass(frozen=True,slots=True)
class AlertDecision: send:bool; reason:str
class AlertEngine:
    def __init__(self,policy:AlertPolicy): self._policy=policy
    def decide(self,*,level:OpportunityLevel,quality:DataQuality,last_sent_at:datetime|None,decided_at:datetime,recipient_authorized:bool,sent_count:int=0)->AlertDecision:
        if quality is not DataQuality.VALID:return AlertDecision(False,"quality_not_valid")
        if not recipient_authorized:return AlertDecision(False,"recipient_not_authorized")
        if level not in {OpportunityLevel.INTERESTING,OpportunityLevel.HIGH_INTEREST}:return AlertDecision(False,"level_below_minimum")
        if last_sent_at and decided_at-last_sent_at<self._policy.cooldown:return AlertDecision(False,"cooldown")
        if self._policy.max_alerts_per_run is not None and sent_count>=self._policy.max_alerts_per_run:return AlertDecision(False,"run_limit")
        return AlertDecision(True,"qualified")

class AlertRepository(Protocol):
    def create_pending(self, **payload): ...
    def mark_sent(self, *, alert_id: UUID, sent_at: datetime): ...
    def mark_suppressed(self, *, alert_id: UUID, reason: str): ...
    def mark_failed(self, *, alert_id: UUID, error_code: str, error_message: str): ...
    def get_latest_sent_for_asset(self, asset_id: UUID): ...
    def get_by_dedupe_key(self, dedupe_key: str): ...
class TelegramSender(Protocol):
    def send_message(self, chat_id: int, text: str): ...
class AlertService:
    def __init__(self, *, engine: AlertEngine, repository: AlertRepository, sender: TelegramSender) -> None: self._engine,self._repository,self._sender=engine,repository,sender
    @staticmethod
    def dedupe_key(*, asset_id: UUID, opportunity_id: UUID, evaluated_at: datetime) -> str: return f"{asset_id}:{opportunity_id}:{evaluated_at.astimezone().isoformat()}"
    @staticmethod
    def message(*, asset: str, timestamp: datetime, price: Decimal, level: OpportunityLevel, score: Decimal, factors: tuple[str,...], risks: tuple[str,...]) -> str:
        return f"Asset: {asset}\nTimestamp: {timestamp.isoformat()}\nValidated price: {price}\nLevel: {level.value}\nScore: {score}\nFactors: {', '.join(factors) or 'none'}\nRisks: {', '.join(risks) or 'none'}"
    def send(self, *, asset_id: UUID, opportunity_id: UUID, recipient_id: int, recipient_authorized: bool, level: OpportunityLevel, quality: DataQuality, decided_at: datetime, asset: str, timestamp: datetime, price: Decimal, score: Decimal, factors: tuple[str,...]=(), risks: tuple[str,...]=(), production_ready: bool=False, automation_enabled: bool=False):
        key=self.dedupe_key(asset_id=asset_id,opportunity_id=opportunity_id,evaluated_at=decided_at)
        existing=self._repository.get_by_dedupe_key(key)
        if existing is not None:return existing
        previous=self._repository.get_latest_sent_for_asset(asset_id)
        last_sent=getattr(previous,"sent_at",None) if previous else None
        decision=(AlertDecision(False,"production_gate") if not production_ready or not automation_enabled else self._engine.decide(level=level,quality=quality,last_sent_at=last_sent,decided_at=decided_at,recipient_authorized=recipient_authorized))
        alert=self._repository.create_pending(asset_id=asset_id,opportunity_id=opportunity_id,channel="telegram",dedupe_key=key,decided_at=decided_at)
        if not decision.send:return self._repository.mark_suppressed(alert_id=alert.id,reason=decision.reason)
        try:self._sender.send_message(recipient_id,self.message(asset=asset,timestamp=timestamp,price=price,level=level,score=score,factors=factors,risks=risks))
        except Exception as exc:
            self._repository.mark_failed(alert_id=alert.id,error_code=exc.__class__.__name__,error_message=sanitize_sensitive_text(exc));raise
        return self._repository.mark_sent(alert_id=alert.id,sent_at=decided_at)
