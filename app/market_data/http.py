import json
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final

import httpx

from app.market_data.errors import (
    ProviderHttpError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTransportError,
)


_DEFAULT_RETRY_STATUS_CODES: Final = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.1
    max_delay_seconds: float = 1.0
    retry_status_codes: frozenset[int] = field(
        default_factory=lambda: _DEFAULT_RETRY_STATUS_CODES
    )

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_attempts, bool)
            or not isinstance(self.max_attempts, int)
            or self.max_attempts < 1
        ):
            raise ValueError("max_attempts deve ser inteiro positivo")
        if not isinstance(self.base_delay_seconds, (int, float)):
            raise ValueError("base_delay_seconds deve ser numérico")
        if not isinstance(self.max_delay_seconds, (int, float)):
            raise ValueError("max_delay_seconds deve ser numérico")
        if (
            not math.isfinite(self.base_delay_seconds)
            or not math.isfinite(self.max_delay_seconds)
            or self.base_delay_seconds < 0
            or self.max_delay_seconds < 0
        ):
            raise ValueError("delays não podem ser negativos")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds deve ser maior ou igual ao base")
        if not isinstance(self.retry_status_codes, frozenset):
            raise ValueError("retry_status_codes deve ser frozenset")
        if not all(
            isinstance(status_code, int) and 100 <= status_code <= 599
            for status_code in self.retry_status_codes
        ):
            raise ValueError("retry_status_codes possui status inválido")

    def delay_for_retry(self, retry_number: int) -> float:
        if retry_number < 0:
            raise ValueError("retry_number não pode ser negativo")
        return min(
            self.base_delay_seconds * (2**retry_number),
            self.max_delay_seconds,
        )


class ProviderHttpClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 10.0,
        retry_policy: RetryPolicy | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url não pode ser vazio")
        if (
            not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds deve ser positivo")
        if not callable(sleep):
            raise ValueError("sleep deve ser chamável")

        self._retry_policy = retry_policy or RetryPolicy()
        if not isinstance(self._retry_policy, RetryPolicy):
            raise ValueError("retry_policy deve ser RetryPolicy")
        self._sleep = sleep
        self._client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
            transport=transport,
        )

    @property
    def is_closed(self) -> bool:
        return self._client.is_closed

    def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> object:
        if self._client.is_closed:
            raise ProviderTransportError("client HTTP está fechado")
        if not isinstance(path, str) or not path.startswith("/"):
            raise ValueError("path deve iniciar com '/'")

        for attempt in range(self._retry_policy.max_attempts):
            try:
                response = self._client.get(
                    path,
                    params=params,
                    headers=headers,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if self._has_next_attempt(attempt):
                    self._sleep_for_retry(attempt)
                    continue
                raise ProviderTransportError(
                    "requisição HTTP ao provider falhou após tentativas"
                ) from exc

            if 200 <= response.status_code < 300:
                return self._parse_json(response.text)
            if (
                response.status_code in self._retry_policy.retry_status_codes
                and self._has_next_attempt(attempt)
            ):
                self._sleep_for_retry(attempt)
                continue
            if response.status_code == 429:
                raise ProviderRateLimitError(
                    "provider limitou requisições",
                    status_code=response.status_code,
                )
            raise ProviderHttpError(
                "provider respondeu com status HTTP inválido",
                status_code=response.status_code,
            )

        raise AssertionError("loop de retry terminou inesperadamente")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ProviderHttpClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _has_next_attempt(self, attempt: int) -> bool:
        return attempt + 1 < self._retry_policy.max_attempts

    def _sleep_for_retry(self, attempt: int) -> None:
        self._sleep(self._retry_policy.delay_for_retry(attempt))

    @staticmethod
    def _parse_json(payload: str) -> object:
        try:
            return json.loads(payload, parse_float=Decimal)
        except json.JSONDecodeError as exc:
            raise ProviderResponseError("provider retornou JSON inválido") from exc
