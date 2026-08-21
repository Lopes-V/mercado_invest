from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

from app.market_data.contracts import (
    AssetSearchRequest,
    HistoryRequest,
    MarketStatusRequest,
    QuoteRequest,
)
from app.market_data.errors import (
    MarketDataValidationError,
    ProviderCapabilityError,
    ProviderResponseError,
)
from app.market_data.http import ProviderHttpClient
from app.market_data.models import (
    Candle,
    CandleInterval,
    MarketStatus,
    ProviderAsset,
    Quote,
    ensure_utc_datetime,
)


_INTERVALS: Final = {
    CandleInterval.ONE_MINUTE: "1m",
    CandleInterval.FIVE_MINUTES: "5m",
    CandleInterval.FIFTEEN_MINUTES: "15m",
    CandleInterval.THIRTY_MINUTES: "30m",
    CandleInterval.ONE_HOUR: "1h",
    CandleInterval.ONE_DAY: "1d",
    CandleInterval.ONE_WEEK: "1wk",
    CandleInterval.ONE_MONTH: "1mo",
}


class BrapiProvider:
    def __init__(
        self,
        http_client: ProviderHttpClient,
        *,
        token: str | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not isinstance(http_client, ProviderHttpClient):
            raise ValueError("http_client deve ser ProviderHttpClient")
        if token is not None and (not isinstance(token, str) or not token.strip()):
            raise ValueError("token deve ser texto não vazio ou None")
        if not callable(clock):
            raise ValueError("clock deve ser chamável")

        self._http_client = http_client
        self._token = token
        self._clock = clock

    @property
    def name(self) -> str:
        return "brapi"

    def get_quote(self, request: QuoteRequest) -> Quote:
        payload = self._get_json(
            "/api/v2/stocks/quote",
            params={"symbols": request.provider_symbol},
        )
        result = _single_result(payload)
        _ensure_identity(result, request.provider_symbol)
        data = _mapping(_required(result, "data"), field="data")
        try:
            return Quote(
                asset_id=request.asset_id,
                provider_symbol=request.provider_symbol,
                price=_decimal(_required(data, "regularMarketPrice"), "price"),
                currency_code=_text(_required(data, "currency"), "currency"),
                timestamp=_provider_datetime(
                    _required(data, "regularMarketTime"), "regularMarketTime"
                ),
                received_at=self._received_at(),
                provider=self.name,
                quality=None,
            )
        except MarketDataValidationError as exc:
            raise ProviderResponseError("cotação BRAPI inválida") from exc

    def get_history(self, request: HistoryRequest) -> Sequence[Candle]:
        if request.start is None or request.end is None:
            raise ProviderCapabilityError(
                "BRAPI exige start e end explícitos para histórico"
            )
        try:
            provider_interval = _INTERVALS[request.interval]
        except KeyError as exc:
            raise ProviderCapabilityError("intervalo não suportado pela BRAPI") from exc

        payload = self._get_json(
            "/api/v2/stocks/historical",
            params={
                "symbols": request.provider_symbol,
                "interval": provider_interval,
                "startDate": request.start.date().isoformat(),
                "endDate": request.end.date().isoformat(),
                "sortOrder": "asc",
            },
        )
        result = _single_result(payload)
        _ensure_identity(result, request.provider_symbol)
        data = _mapping(_required(result, "data"), field="data")
        historical_data = _required(data, "historicalDataPrice")
        if not isinstance(historical_data, list):
            raise ProviderResponseError("historicalDataPrice deve ser lista")

        received_at = self._received_at()
        candles: list[Candle] = []
        for point in historical_data:
            candles.append(
                _candle_from_point(
                    _mapping(point, field="historicalDataPrice"),
                    request=request,
                    received_at=received_at,
                )
            )
        return candles

    def get_assets(self, request: AssetSearchRequest) -> Sequence[ProviderAsset]:
        if request.market_code is not None or request.exchange_code is not None:
            raise ProviderCapabilityError(
                "BRAPI não oferece filtro equivalente de market/exchange"
            )
        params = {"search": request.query} if request.query is not None else None
        payload = self._get_json("/api/v2/tickers", params=params)
        root = _mapping(payload, field="resposta")
        results = _required(root, "results")
        if not isinstance(results, list):
            raise ProviderResponseError("results deve ser lista")

        assets: list[ProviderAsset] = []
        for item in results:
            data = _mapping(item, field="results")
            try:
                assets.append(
                    ProviderAsset(
                        provider=self.name,
                        provider_symbol=_text(_required(data, "symbol"), "symbol"),
                        name=_text(_required(data, "name"), "name"),
                        asset_type=_optional_text(data.get("subType")),
                        currency_code=_optional_text(data.get("currency")),
                        exchange_code=_optional_text(data.get("exchange")),
                        market_code=None,
                        isin=None,
                    )
                )
            except MarketDataValidationError as exc:
                raise ProviderResponseError("ticker BRAPI inválido") from exc
        return assets

    def get_market_status(self, request: MarketStatusRequest) -> MarketStatus:
        raise ProviderCapabilityError(
            "BRAPI não possui endpoint dedicado de market status neste adapter"
        )

    def close(self) -> None:
        self._http_client.close()

    def _get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> object:
        return self._http_client.get_json(
            path,
            params=params,
            headers=(
                {"Authorization": f"Bearer {self._token}"}
                if self._token is not None
                else None
            ),
        )

    def _received_at(self) -> datetime:
        try:
            return ensure_utc_datetime(self._clock(), field="clock")
        except MarketDataValidationError as exc:
            raise ProviderResponseError("clock do provider retornou datetime inválido") from exc


def _single_result(payload: object) -> Mapping[str, object]:
    root = _mapping(payload, field="resposta")
    results = _required(root, "results")
    if not isinstance(results, list) or len(results) != 1:
        raise ProviderResponseError("BRAPI deve retornar exatamente um resultado")
    return _mapping(results[0], field="results")


def _ensure_identity(result: Mapping[str, object], expected_symbol: str) -> None:
    changed = _required(result, "changed")
    if not isinstance(changed, bool):
        raise ProviderResponseError("changed deve ser booleano")
    symbol = _text(_required(result, "symbol"), "symbol")
    requested_symbol = _text(
        _required(result, "requestedSymbol"), "requestedSymbol"
    )
    if changed or symbol != expected_symbol or requested_symbol != expected_symbol:
        raise ProviderResponseError("ticker BRAPI mudou e requer reavaliação do mapping")


def _candle_from_point(
    point: Mapping[str, object],
    *,
    request: HistoryRequest,
    received_at: datetime,
) -> Candle:
    try:
        return Candle(
            asset_id=request.asset_id,
            provider_symbol=request.provider_symbol,
            timestamp=_epoch_datetime(_required(point, "date"), "date"),
            open=_decimal(_required(point, "open"), "open"),
            high=_decimal(_required(point, "high"), "high"),
            low=_decimal(_required(point, "low"), "low"),
            close=_decimal(_required(point, "close"), "close"),
            volume=_optional_decimal(point.get("volume"), "volume"),
            interval=request.interval,
            provider="brapi",
            received_at=received_at,
            quality=None,
            adjusted_close=_optional_decimal(
                point.get("adjustedClose"), "adjustedClose"
            ),
        )
    except MarketDataValidationError as exc:
        raise ProviderResponseError("candle BRAPI inválido") from exc


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ProviderResponseError(f"{field} deve ser objeto")
    return value


def _required(payload: Mapping[str, object], field: str) -> object:
    try:
        return payload[field]
    except KeyError as exc:
        raise ProviderResponseError(f"campo obrigatório ausente: {field}") from exc


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProviderResponseError(f"{field} deve ser texto não vazio")
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _text(value, "campo opcional")


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, int)):
        raise ProviderResponseError(f"{field} deve ser Decimal ou inteiro")
    return Decimal(value)


def _optional_decimal(value: object, field: str) -> Decimal | None:
    if value is None:
        return None
    return _decimal(value, field)


def _epoch_datetime(value: object, field: str) -> datetime:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProviderResponseError(f"{field} deve ser epoch inteiro")
    try:
        return datetime.fromtimestamp(value, UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise ProviderResponseError(f"{field} contém epoch inválido") from exc


def _provider_datetime(value: object, field: str) -> datetime:
    if isinstance(value, int) and not isinstance(value, bool):
        return _epoch_datetime(value, field)
    if not isinstance(value, str):
        raise ProviderResponseError(f"{field} deve ser epoch ou timestamp ISO 8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return ensure_utc_datetime(parsed, field=field)
    except (ValueError, MarketDataValidationError) as exc:
        raise ProviderResponseError(f"{field} contém timestamp inválido") from exc
