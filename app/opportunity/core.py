from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from app.market_data.models import DataQuality
from typing import Protocol
from uuid import UUID

class OpportunityLevel(StrEnum): NONE="NONE"; WATCH="WATCH"; INTERESTING="INTERESTING"; HIGH_INTEREST="HIGH_INTEREST"
class MetricOperator(StrEnum): GT="GT"; GTE="GTE"; LT="LT"; LTE="LTE"
class EvidenceCategory(StrEnum): TREND="TREND"; MOMENTUM="MOMENTUM"; RISK="RISK"; VOLUME="VOLUME"; AI_CONTEXT="AI_CONTEXT"
@dataclass(frozen=True,slots=True)
class MetricRule: metric_name:str; operator:MetricOperator; threshold:Decimal; weight:Decimal; evidence_category: str
@dataclass(frozen=True,slots=True)
class OpportunityPolicy:
    version:str; rules:tuple[MetricRule,...]; minimum_categories:int=2; max_ai_weight:Decimal=Decimal("20"); max_age:timedelta=timedelta(minutes=15)
@dataclass(frozen=True,slots=True)
class OpportunityAssessment: level:OpportunityLevel; score:Decimal; evidence_count:int; reasons:tuple[str,...]
class OpportunityEngine:
    def __init__(self,policy:OpportunityPolicy): self._policy=policy
    def assess(self,*,metrics:dict[str,Decimal], price_quality:DataQuality, reference_at:datetime,evaluated_at:datetime,ai_positive:bool=False)->OpportunityAssessment:
        if price_quality is not DataQuality.VALID or reference_at.tzinfo is None or evaluated_at.tzinfo is None or evaluated_at.astimezone(UTC)-reference_at.astimezone(UTC)>self._policy.max_age: return OpportunityAssessment(OpportunityLevel.NONE,Decimal("0"),0,("quality_or_timestamp_invalid",))
        score=Decimal("0"); categories=set(); reasons=[]
        for rule in self._policy.rules:
            value=metrics.get(rule.metric_name)
            if value is None: continue
            matched={MetricOperator.GT:value>rule.threshold,MetricOperator.GTE:value>=rule.threshold,MetricOperator.LT:value<rule.threshold,MetricOperator.LTE:value<=rule.threshold}[rule.operator]
            if matched:
                weight=min(rule.weight,self._policy.max_ai_weight) if rule.evidence_category==EvidenceCategory.AI_CONTEXT.value else rule.weight
                score+=weight; categories.add(rule.evidence_category); reasons.append(rule.metric_name)
        if ai_positive and "AI_CONTEXT" not in categories: categories.add("AI_CONTEXT"); score+=min(self._policy.max_ai_weight,Decimal("1")); reasons.append("ai_context")
        score=min(Decimal("100"),score); count=len(categories)
        if count==0: level=OpportunityLevel.NONE
        elif count<self._policy.minimum_categories: level=OpportunityLevel.WATCH
        elif score>=Decimal("70"): level=OpportunityLevel.HIGH_INTEREST
        elif score>=Decimal("40"): level=OpportunityLevel.INTERESTING
        else: level=OpportunityLevel.WATCH
        return OpportunityAssessment(level,score,count,tuple(reasons))

class OpportunityRepository(Protocol):
    def create(self, **payload): ...

class OpportunityService:
    def __init__(self, *, engine: OpportunityEngine, repository: OpportunityRepository) -> None: self._engine,self._repository=engine,repository
    def assess(self, *, asset_id: UUID, analysis_id: UUID, metrics: dict[str,Decimal], quote_quality: DataQuality, reference_at: datetime, evaluated_at: datetime, ai_run_id: UUID|None=None, ai_positive: bool=False) -> OpportunityAssessment:
        result=self._engine.assess(metrics=metrics,price_quality=quote_quality,reference_at=reference_at,evaluated_at=evaluated_at,ai_positive=ai_positive)
        self._repository.create(asset_id=asset_id,analysis_id=analysis_id,ai_run_id=ai_run_id,level=result.level.value,score=str(result.score),evidence_count=result.evidence_count,evaluated_at=evaluated_at,policy_version=self._engine._policy.version,evidence=list(result.reasons))
        return result
