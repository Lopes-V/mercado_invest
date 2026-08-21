from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Generic, Mapping, TypeVar

from app.market_data.errors import (
    MarketDataQualityError,
    MarketDataValidationError,
    QualityPolicyError,
)
from app.market_data.models import (
    Candle,
    CandleInterval,
    DataQuality,
    MarketSessionStatus,
    MarketStatus,
    Quote,
    ensure_utc_datetime,
)


class QualityIssueCode(StrEnum):
    FUTURE_TIMESTAMP = "FUTURE_TIMESTAMP"
    FUTURE_RECEIVED_AT = "FUTURE_RECEIVED_AT"
    TIMESTAMP_AFTER_RECEIVED_AT = "TIMESTAMP_AFTER_RECEIVED_AT"
    STALE = "STALE"
    MISSING_VOLUME = "MISSING_VOLUME"
    MISSING_ADJUSTED_CLOSE = "MISSING_ADJUSTED_CLOSE"
    UNKNOWN_MARKET_STATUS = "UNKNOWN_MARKET_STATUS"
    PRICE_OUTLIER = "PRICE_OUTLIER"


_INVALID_ISSUES = frozenset(
    {
        QualityIssueCode.FUTURE_TIMESTAMP,
        QualityIssueCode.FUTURE_RECEIVED_AT,
        QualityIssueCode.TIMESTAMP_AFTER_RECEIVED_AT,
    }
)
_INCOMPLETE_ISSUES = frozenset(
    {
        QualityIssueCode.MISSING_VOLUME,
        QualityIssueCode.MISSING_ADJUSTED_CLOSE,
        QualityIssueCode.UNKNOWN_MARKET_STATUS,
    }
)
_OUTLIER_ISSUES = frozenset({QualityIssueCode.PRICE_OUTLIER})
_STALE_ISSUES = frozenset({QualityIssueCode.STALE})


@dataclass(frozen=True, slots=True)
class QualityPolicy:
    quote_max_age: timedelta
    market_status_max_age: timedelta
    candle_max_age: Mapping[CandleInterval, timedelta]
    future_tolerance: timedelta
    max_relative_price_deviation: Decimal | None = None
    require_candle_volume: bool = False
    require_adjusted_close: bool = False
    unknown_market_status_is_incomplete: bool = True

    def __post_init__(self) -> None:
        _ensure_non_negative_timedelta(
            self.quote_max_age, field="quote_max_age"
        )
        _ensure_non_negative_timedelta(
            self.market_status_max_age, field="market_status_max_age"
        )
        _ensure_non_negative_timedelta(
            self.future_tolerance, field="future_tolerance"
        )
        if not isinstance(self.candle_max_age, Mapping):
            raise QualityPolicyError("candle_max_age deve ser Mapping")

        candle_max_age: dict[CandleInterval, timedelta] = {}
        for interval, max_age in self.candle_max_age.items():
            if not isinstance(interval, CandleInterval):
                raise QualityPolicyError(
                    "candle_max_age deve usar CandleInterval como chave"
                )
            _ensure_non_negative_timedelta(
                max_age, field=f"candle_max_age[{interval.value}]"
            )
            candle_max_age[interval] = max_age

        if self.max_relative_price_deviation is not None:
            _ensure_non_negative_finite_decimal(
                self.max_relative_price_deviation,
                field="max_relative_price_deviation",
            )
        for field in (
            "require_candle_volume",
            "require_adjusted_close",
            "unknown_market_status_is_incomplete",
        ):
            if not isinstance(getattr(self, field), bool):
                raise QualityPolicyError(f"{field} deve ser bool")

        object.__setattr__(
            self, "candle_max_age", MappingProxyType(candle_max_age)
        )


@dataclass(frozen=True, slots=True)
class QualityIssue:
    code: QualityIssueCode
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, QualityIssueCode):
            raise MarketDataQualityError(
                "code deve ser QualityIssueCode"
            )
        if not isinstance(self.message, str) or not self.message.strip():
            raise MarketDataQualityError("message não pode ser vazia")


T = TypeVar("T", Quote, Candle, MarketStatus)


@dataclass(frozen=True, slots=True)
class QualityAssessment(Generic[T]):
    data: T
    quality: DataQuality
    evaluated_at: datetime
    issues: tuple[QualityIssue, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.data, (Quote, Candle, MarketStatus)):
            raise MarketDataQualityError(
                "data deve ser Quote, Candle ou MarketStatus"
            )
        if not isinstance(self.quality, DataQuality):
            raise MarketDataQualityError("quality deve ser DataQuality")
        if self.data.quality != self.quality:
            raise MarketDataQualityError(
                "data.quality deve corresponder a quality"
            )
        if not isinstance(self.issues, tuple):
            raise MarketDataQualityError("issues deve ser tuple")
        if not all(isinstance(issue, QualityIssue) for issue in self.issues):
            raise MarketDataQualityError(
                "issues deve conter QualityIssue"
            )

        object.__setattr__(
            self,
            "evaluated_at",
            _ensure_evaluated_at(self.evaluated_at),
        )


class QualityEngine:
    def __init__(self, policy: QualityPolicy) -> None:
        if not isinstance(policy, QualityPolicy):
            raise QualityPolicyError("policy deve ser QualityPolicy")
        self._policy = policy

    def assess_quote(
        self,
        quote: Quote,
        *,
        evaluated_at: datetime,
        reference_price: Decimal | None = None,
    ) -> QualityAssessment[Quote]:
        if not isinstance(quote, Quote):
            raise MarketDataQualityError("quote deve ser Quote")

        normalized_evaluated_at = _ensure_evaluated_at(evaluated_at)
        _validate_reference_price(reference_price)
        issues = self._temporal_issues(
            timestamp=quote.timestamp,
            received_at=quote.received_at,
            evaluated_at=normalized_evaluated_at,
            max_age=self._policy.quote_max_age,
        )
        outlier_issue = self._outlier_issue(
            value=quote.price, reference_price=reference_price
        )
        if outlier_issue is not None:
            issues.append(outlier_issue)

        return _assessment(quote, normalized_evaluated_at, issues)

    def assess_candle(
        self,
        candle: Candle,
        *,
        evaluated_at: datetime,
        reference_price: Decimal | None = None,
    ) -> QualityAssessment[Candle]:
        if not isinstance(candle, Candle):
            raise MarketDataQualityError("candle deve ser Candle")

        normalized_evaluated_at = _ensure_evaluated_at(evaluated_at)
        _validate_reference_price(reference_price)
        try:
            max_age = self._policy.candle_max_age[candle.interval]
        except KeyError as exc:
            raise QualityPolicyError(
                "candle_max_age não possui configuração para "
                f"{candle.interval.value}"
            ) from exc

        issues = self._temporal_issues(
            timestamp=candle.timestamp,
            received_at=candle.received_at,
            evaluated_at=normalized_evaluated_at,
            max_age=max_age,
        )
        if self._policy.require_candle_volume and candle.volume is None:
            issues.append(
                QualityIssue(
                    QualityIssueCode.MISSING_VOLUME,
                    "volume é obrigatório pela QualityPolicy",
                )
            )
        if self._policy.require_adjusted_close and candle.adjusted_close is None:
            issues.append(
                QualityIssue(
                    QualityIssueCode.MISSING_ADJUSTED_CLOSE,
                    "adjusted_close é obrigatório pela QualityPolicy",
                )
            )
        outlier_issue = self._outlier_issue(
            value=candle.close, reference_price=reference_price
        )
        if outlier_issue is not None:
            issues.append(outlier_issue)

        return _assessment(candle, normalized_evaluated_at, issues)

    def assess_market_status(
        self,
        status: MarketStatus,
        *,
        evaluated_at: datetime,
    ) -> QualityAssessment[MarketStatus]:
        if not isinstance(status, MarketStatus):
            raise MarketDataQualityError("status deve ser MarketStatus")

        normalized_evaluated_at = _ensure_evaluated_at(evaluated_at)
        issues = self._temporal_issues(
            timestamp=status.timestamp,
            received_at=status.received_at,
            evaluated_at=normalized_evaluated_at,
            max_age=self._policy.market_status_max_age,
        )
        if (
            self._policy.unknown_market_status_is_incomplete
            and status.status is MarketSessionStatus.UNKNOWN
        ):
            issues.append(
                QualityIssue(
                    QualityIssueCode.UNKNOWN_MARKET_STATUS,
                    "status de mercado desconhecido",
                )
            )

        return _assessment(status, normalized_evaluated_at, issues)

    def _temporal_issues(
        self,
        *,
        timestamp: datetime,
        received_at: datetime,
        evaluated_at: datetime,
        max_age: timedelta,
    ) -> list[QualityIssue]:
        issues: list[QualityIssue] = []
        future_limit = evaluated_at + self._policy.future_tolerance
        if timestamp > future_limit:
            issues.append(
                QualityIssue(
                    QualityIssueCode.FUTURE_TIMESTAMP,
                    "timestamp está além da tolerância futura",
                )
            )
        if received_at > future_limit:
            issues.append(
                QualityIssue(
                    QualityIssueCode.FUTURE_RECEIVED_AT,
                    "received_at está além da tolerância futura",
                )
            )
        if timestamp > received_at + self._policy.future_tolerance:
            issues.append(
                QualityIssue(
                    QualityIssueCode.TIMESTAMP_AFTER_RECEIVED_AT,
                    "timestamp está além da tolerância em relação a received_at",
                )
            )
        if evaluated_at - timestamp > max_age:
            issues.append(
                QualityIssue(
                    QualityIssueCode.STALE,
                    "timestamp excede a idade máxima configurada",
                )
            )

        return issues

    def _outlier_issue(
        self,
        *,
        value: Decimal,
        reference_price: Decimal | None,
    ) -> QualityIssue | None:
        threshold = self._policy.max_relative_price_deviation
        if threshold is None or reference_price is None:
            return None

        relative_deviation = abs(value - reference_price) / reference_price
        if relative_deviation > threshold:
            return QualityIssue(
                QualityIssueCode.PRICE_OUTLIER,
                "desvio relativo excede o limite configurado",
            )

        return None


def _ensure_non_negative_timedelta(value: timedelta, *, field: str) -> None:
    if not isinstance(value, timedelta):
        raise QualityPolicyError(f"{field} deve ser timedelta")
    if value < timedelta():
        raise QualityPolicyError(f"{field} não pode ser negativo")


def _ensure_non_negative_finite_decimal(value: Decimal, *, field: str) -> None:
    if not isinstance(value, Decimal):
        raise QualityPolicyError(f"{field} deve ser Decimal")
    if not value.is_finite():
        raise QualityPolicyError(f"{field} deve ser finito")
    if value < 0:
        raise QualityPolicyError(f"{field} não pode ser negativo")


def _ensure_evaluated_at(value: datetime) -> datetime:
    try:
        return ensure_utc_datetime(value, field="evaluated_at")
    except MarketDataValidationError as exc:
        raise MarketDataQualityError(str(exc)) from exc


def _validate_reference_price(reference_price: Decimal | None) -> None:
    if reference_price is None:
        return
    if not isinstance(reference_price, Decimal):
        raise MarketDataQualityError("reference_price deve ser Decimal")
    if not reference_price.is_finite():
        raise MarketDataQualityError("reference_price deve ser finito")
    if reference_price <= 0:
        raise MarketDataQualityError("reference_price deve ser maior que zero")


def _assessment(
    data: T,
    evaluated_at: datetime,
    issues: list[QualityIssue],
) -> QualityAssessment[T]:
    issues_tuple = tuple(issues)
    quality = _quality_for_issues(issues_tuple)
    qualified_data = replace(data, quality=quality)
    return QualityAssessment(
        data=qualified_data,
        quality=quality,
        evaluated_at=evaluated_at,
        issues=issues_tuple,
    )


def _quality_for_issues(issues: tuple[QualityIssue, ...]) -> DataQuality:
    issue_codes = {issue.code for issue in issues}
    if issue_codes & _INVALID_ISSUES:
        return DataQuality.INVALID
    if issue_codes & _INCOMPLETE_ISSUES:
        return DataQuality.INCOMPLETE
    if issue_codes & _OUTLIER_ISSUES:
        return DataQuality.OUTLIER
    if issue_codes & _STALE_ISSUES:
        return DataQuality.STALE

    return DataQuality.VALID
