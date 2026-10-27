"""Public Bybit V5 spot data; prices and volumes are never synthesized."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation, localcontext
import re

from app.market_data.contracts import (
    AssetSearchRequest, HistoryRequest, MarketStatusRequest, QuoteRequest,
)
from app.market_data.errors import (
    ProviderCapabilityError, ProviderResponseError,
)
from app.market_data.http import ProviderHttpClient
from app.market_data.models import (
    Candle, CandleInterval, MarketStatus, ProviderAsset, Quote, ensure_utc_datetime,
)

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_SYMBOL = re.compile(r"[A-Z0-9]{1,30}USDT\Z")
_COIN = re.compile(r"[A-Z0-9]{1,30}\Z")
_INTERVALS = {
    CandleInterval.ONE_MINUTE: ("1", timedelta(minutes=1)),
    CandleInterval.FIVE_MINUTES: ("5", timedelta(minutes=5)),
    CandleInterval.FIFTEEN_MINUTES: ("15", timedelta(minutes=15)),
    CandleInterval.THIRTY_MINUTES: ("30", timedelta(minutes=30)),
    CandleInterval.ONE_HOUR: ("60", timedelta(hours=1)),
    CandleInterval.ONE_DAY: ("D", timedelta(days=1)),
}
_PAGE_LIMIT = 1000
_MAX_PAGES = 100
_FUTURE_TOLERANCE = timedelta(minutes=2)


@dataclass(frozen=True, slots=True)
class BybitLiquidity:
    symbol: str
    bid: Decimal
    ask: Decimal
    volume24h: Decimal
    turnover24h: Decimal
    timestamp: datetime

    @property
    def spread_bps(self) -> Decimal:
        """(ask - bid) / midpoint * 10,000; no fee assumptions."""
        with localcontext() as context:
            context.prec = 38
            return (self.ask - self.bid) / ((self.ask + self.bid) / 2) * 10000


class BybitProvider:
    name = "bybit"

    def __init__(
        self,
        http_client: ProviderHttpClient,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._http = http_client
        self._clock = clock
        self._instruments: dict[str, ProviderAsset] = {}
        self._catalog_loaded = False

    def get_quote(self, request: QuoteRequest) -> Quote:
        asset = self._instrument(request.provider_symbol)
        result, _ = self._get(
            "/v5/market/recent-trade", symbol=request.provider_symbol, limit=1,
        )
        row = self._single(result)
        self._identity(row, request.provider_symbol)
        received = self._now()
        timestamp = self._timestamp(row.get("time"), received)
        return Quote(
            request.asset_id, request.provider_symbol,
            self._decimal(row.get("price"), "price", positive=True),
            asset.currency_code, timestamp, received, self.name, None,
        )

    def get_history(self, request: HistoryRequest) -> Sequence[Candle]:
        """Fetch an inclusive start-time range, returning only closed candles.

        Bybit returns newest first. Pages move backwards by one millisecond;
        identical overlapping facts are accepted, conflicting ones fail closed.
        A bounded request never returns a silently truncated result.
        """
        if request.start is None or request.end is None:
            raise ProviderCapabilityError("Bybit requer range explícito")
        if request.interval not in _INTERVALS:
            raise ProviderCapabilityError("intervalo Bybit não suportado")
        interval, duration = _INTERVALS[request.interval]
        self._instrument(request.provider_symbol)
        received = self._now()
        start_ms, end_ms = self._milliseconds(request.start), self._milliseconds(request.end)
        cursor = end_ms
        facts: dict[datetime, tuple[Decimal, ...]] = {}
        for _ in range(_MAX_PAGES):
            result, _ = self._get(
                "/v5/market/kline", symbol=request.provider_symbol,
                interval=interval, start=start_ms, end=cursor, limit=_PAGE_LIMIT,
            )
            self._identity(result, request.provider_symbol)
            rows = self._rows(result)
            if len(rows) > _PAGE_LIMIT:
                raise ProviderResponseError("página Bybit excede limite")
            if not rows:
                break
            oldest = cursor + 1
            for row in rows:
                if not isinstance(row, list) or len(row) != 7:
                    raise ProviderResponseError("candle Bybit malformado")
                timestamp = self._timestamp(row[0], received)
                row_ms = self._milliseconds(timestamp)
                if (timestamp - _EPOCH) % duration != timedelta(0):
                    raise ProviderResponseError("candle Bybit desalinhado com intervalo")
                if not start_ms <= row_ms <= end_ms:
                    raise ProviderResponseError("candle Bybit fora do range")
                values = tuple(
                    self._decimal(value, field, positive=index < 4)
                    for index, (field, value) in enumerate(zip(
                        ("open", "high", "low", "close", "volume", "turnover"), row[1:], strict=True,
                    ))
                )
                open_, high, low, close, _, _ = values
                if high < max(open_, close) or low > min(open_, close) or high < low:
                    raise ProviderResponseError("OHLC Bybit incoerente")
                previous = facts.get(timestamp)
                if previous is not None and previous != values:
                    raise ProviderResponseError("candles Bybit duplicados conflitantes")
                if row_ms > cursor and previous is None:
                    raise ProviderResponseError("página Bybit fora do cursor")
                facts[timestamp] = values
                oldest = min(oldest, row_ms)
            if oldest <= start_ms or len(rows) < _PAGE_LIMIT:
                break
            if oldest > cursor:
                raise ProviderResponseError("paginação Bybit sem progresso")
            cursor = oldest - 1
        else:
            raise ProviderResponseError("paginação Bybit excedeu limite seguro")
        return tuple(
            Candle(
                request.asset_id, request.provider_symbol, timestamp,
                values[0], values[1], values[2], values[3], values[4],
                request.interval, self.name, received, None,
            )
            for timestamp, values in sorted(facts.items())
            if timestamp + duration <= received
        )

    def get_assets(self, request: AssetSearchRequest) -> Sequence[ProviderAsset]:
        if request.market_code not in (None, "CRYPTO") or request.exchange_code not in (None, "BYBIT"):
            raise ProviderCapabilityError("Bybit suporta somente CRYPTO/BYBIT spot")
        if not self._catalog_loaded:
            # Spot instruments-info explicitly has no pagination support.
            result, _ = self._get("/v5/market/instruments-info")
            assets: dict[str, ProviderAsset] = {}
            for raw in self._rows(result):
                row = self._mapping(raw)
                asset = self._asset(row)
                if asset is None:
                    continue
                if asset.provider_symbol in assets:
                    raise ProviderResponseError("instrumento Bybit duplicado")
                assets[asset.provider_symbol] = asset
            self._instruments = assets
            self._catalog_loaded = True
        query = request.query.upper() if request.query else None
        return tuple(
            asset for symbol, asset in sorted(self._instruments.items())
            if query is None or query in symbol or query in asset.name.upper()
        )

    def get_market_status(self, request: MarketStatusRequest) -> MarketStatus:
        raise ProviderCapabilityError("market status Bybit não implementado")

    def get_liquidity(self, symbol: str) -> BybitLiquidity:
        self._instrument(symbol)
        result, payload = self._get("/v5/market/tickers", symbol=symbol)
        row = self._single(result)
        self._identity(row, symbol)
        bid = self._decimal(row.get("bid1Price"), "bid1Price", positive=True)
        ask = self._decimal(row.get("ask1Price"), "ask1Price", positive=True)
        if ask < bid:
            raise ProviderResponseError("livro Bybit cruzado")
        return BybitLiquidity(
            symbol, bid, ask,
            self._decimal(row.get("volume24h"), "volume24h"),
            self._decimal(row.get("turnover24h"), "turnover24h"),
            self._timestamp(payload.get("time"), self._now()),
        )

    def _instrument(self, symbol: str) -> ProviderAsset:
        if not isinstance(symbol, str) or not _SYMBOL.fullmatch(symbol):
            raise ProviderCapabilityError("Bybit requer símbolo spot USDT uppercase")
        if symbol not in self._instruments:
            if self._catalog_loaded:
                raise ProviderResponseError("instrumento Bybit Trading USDT ausente")
            result, _ = self._get("/v5/market/instruments-info", symbol=symbol)
            row = self._single(result)
            self._identity(row, symbol)
            asset = self._asset(row)
            if asset is None:
                raise ProviderResponseError("instrumento Bybit requer Trading e USDT")
            self._instruments[symbol] = asset
        return self._instruments[symbol]

    def _get(self, path: str, **params: str | int) -> tuple[Mapping, Mapping]:
        payload = self._mapping(self._http.get_json(path, params={"category": "spot", **params}))
        code = payload.get("retCode")
        if type(code) is not int or code != 0:
            raise ProviderResponseError("retCode Bybit inválido ou operação recusada")
        result = self._mapping(payload.get("result"))
        if result.get("category") != "spot":
            raise ProviderResponseError("category Bybit deve ser spot")
        return result, payload

    @classmethod
    def _asset(cls, row: Mapping) -> ProviderAsset | None:
        symbol, base, quote, status = (cls._text(row, field) for field in ("symbol", "baseCoin", "quoteCoin", "status"))
        if not _COIN.fullmatch(base) or not _COIN.fullmatch(quote) or symbol != base + quote:
            raise ProviderResponseError("identidade base/quote Bybit inválida")
        if quote != "USDT" or status != "Trading":
            return None
        return ProviderAsset("bybit", symbol, base, "CRYPTO", "USDT", "BYBIT", "CRYPTO")

    def _now(self) -> datetime:
        return ensure_utc_datetime(self._clock(), field="clock")

    @staticmethod
    def _mapping(value: object) -> Mapping:
        if not isinstance(value, Mapping):
            raise ProviderResponseError("objeto Bybit malformado")
        return value

    @staticmethod
    def _text(row: Mapping, field: str) -> str:
        value = row.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ProviderResponseError(f"{field} Bybit ausente")
        return value

    @staticmethod
    def _rows(result: Mapping) -> list:
        rows = result.get("list")
        if not isinstance(rows, list):
            raise ProviderResponseError("list Bybit ausente")
        return rows

    @classmethod
    def _single(cls, result: Mapping) -> Mapping:
        rows = cls._rows(result)
        if len(rows) != 1:
            raise ProviderResponseError("Bybit requer exatamente um resultado")
        return cls._mapping(rows[0])

    @staticmethod
    def _identity(row: Mapping, symbol: str) -> None:
        if row.get("symbol") != symbol:
            raise ProviderResponseError("symbol Bybit não corresponde ao mapping")

    @staticmethod
    def _decimal(value: object, field: str, *, positive: bool = False) -> Decimal:
        if not isinstance(value, str) or not value.strip():
            raise ProviderResponseError(f"{field} Bybit deve ser texto decimal")
        try:
            parsed = Decimal(value)
        except InvalidOperation as exc:
            raise ProviderResponseError(f"{field} Bybit inválido") from exc
        if not parsed.is_finite() or parsed < 0 or (positive and parsed == 0):
            raise ProviderResponseError(f"{field} Bybit inválido")
        return parsed

    @staticmethod
    def _timestamp(value: object, received: datetime) -> datetime:
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ProviderResponseError("timestamp Bybit inválido")
        if isinstance(value, str) and (not value.isascii() or not value.isdigit()):
            raise ProviderResponseError("timestamp Bybit inválido")
        try:
            milliseconds = int(value)
            if milliseconds <= 0:
                raise ValueError("timestamp não positivo")
            timestamp = _EPOCH + timedelta(milliseconds=milliseconds)
        except (ValueError, OverflowError) as exc:
            raise ProviderResponseError("timestamp Bybit inválido") from exc
        if timestamp > received + _FUTURE_TOLERANCE:
            raise ProviderResponseError("timestamp Bybit futuro")
        return timestamp

    @staticmethod
    def _milliseconds(value: datetime) -> int:
        return (value - _EPOCH) // timedelta(milliseconds=1)
