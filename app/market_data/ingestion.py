from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.database.models import MarketCandleRecord, MarketQuoteRecord
from app.database.repositories.market_data import MarketCandleRepository, MarketQuoteRepository, ProviderSymbolRepository
from app.market_data.contracts import HistoryRequest, MarketDataProvider, QuoteRequest
from app.market_data.errors import MarketDataIngestionError
from app.market_data.models import CandleInterval
from app.market_data.quality import QualityAssessment, QualityEngine


@dataclass(frozen=True, slots=True)
class QuoteIngestionResult:
    assessment: QualityAssessment
    record: MarketQuoteRecord
    created: bool


@dataclass(frozen=True, slots=True)
class HistoryIngestionResult:
    assessments: tuple[QualityAssessment, ...]
    records: tuple[MarketCandleRecord, ...]

    def __post_init__(self) -> None:
        if len(self.assessments) != len(self.records):
            raise MarketDataIngestionError("assessments e records devem ter mesma quantidade")


class MarketDataIngestionService:
    def __init__(self, *, provider: MarketDataProvider, quality_engine: QualityEngine, provider_symbols: ProviderSymbolRepository, quotes: MarketQuoteRepository, candles: MarketCandleRepository) -> None:
        self._provider = provider
        self._quality_engine = quality_engine
        self._provider_symbols = provider_symbols
        self._quotes = quotes
        self._candles = candles

    def ingest_quote(self, asset_id: UUID, *, evaluated_at: datetime, reference_price: Decimal | None = None) -> QuoteIngestionResult:
        mapping = self._mapping(asset_id)
        quote = self._provider.get_quote(QuoteRequest(asset_id, mapping.provider_symbol))
        assessment = self._quality_engine.assess_quote(quote, evaluated_at=evaluated_at, reference_price=reference_price)
        saved = self._quotes.create_from_quote(assessment.data)
        return QuoteIngestionResult(
            assessment=assessment,
            record=saved.record,
            created=saved.created,
        )

    def ingest_history(self, asset_id: UUID, interval: CandleInterval, start: datetime, end: datetime, *, evaluated_at: datetime) -> HistoryIngestionResult:
        mapping = self._mapping(asset_id)
        history = self._provider.get_history(HistoryRequest(asset_id, mapping.provider_symbol, interval, start, end))
        assessments = tuple(self._quality_engine.assess_candle(candle, evaluated_at=evaluated_at) for candle in history)
        records = self._candles.create_many_idempotent(
            tuple(assessment.data for assessment in assessments)
        )
        return HistoryIngestionResult(assessments=assessments, records=records)

    def _mapping(self, asset_id: UUID):
        mapping = self._provider_symbols.get_by_asset_and_provider(asset_id, self._provider.name)
        if mapping is None:
            raise MarketDataIngestionError("provider symbol mapping não encontrado")
        if mapping.provider != self._provider.name:
            raise MarketDataIngestionError("mapping pertence a provider diferente")
        return mapping
