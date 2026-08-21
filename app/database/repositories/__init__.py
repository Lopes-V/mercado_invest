from app.database.repositories.assets import AssetRepository
from app.database.repositories.currencies import CurrencyRepository
from app.database.repositories.exchanges import ExchangeRepository
from app.database.repositories.markets import MarketRepository
from app.database.repositories.jobs import JobRunRepository
from app.database.repositories.market_data import (
    MarketCandleRepository,
    MarketQuoteRepository,
    ProviderSymbolRepository,
)
from app.database.repositories.portfolio import PortfolioRepository, PortfolioSnapshotRepository, PortfolioTransactionRepository
from app.database.repositories.stage_records import AnalysisRepository, AnalysisMetricRepository, AIRunRepository, OpportunityRepository, AlertRepository, BacktestRunRepository, BacktestEventRepository, PaperAccountRepository, PaperOrderRepository, PaperTradeRepository, FixedIncomeInstrumentRepository, FixedIncomeSnapshotRepository, FixedIncomeHistoryRepository, FxRateRepository


__all__ = [
    "AssetRepository",
    "CurrencyRepository",
    "ExchangeRepository",
    "JobRunRepository",
    "MarketRepository",
    "MarketCandleRepository",
    "MarketQuoteRepository",
    "ProviderSymbolRepository",
    "PortfolioRepository",
    "PortfolioTransactionRepository",
    "PortfolioSnapshotRepository",
    "AnalysisRepository", "AnalysisMetricRepository", "AIRunRepository", "OpportunityRepository", "AlertRepository", "BacktestRunRepository", "BacktestEventRepository", "PaperAccountRepository", "PaperOrderRepository", "PaperTradeRepository", "FixedIncomeInstrumentRepository", "FixedIncomeSnapshotRepository", "FixedIncomeHistoryRepository", "FxRateRepository",
]
