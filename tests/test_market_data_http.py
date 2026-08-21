from decimal import Decimal

import httpx
import pytest

from app.market_data.errors import (
    ProviderHttpError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTransportError,
)
from app.market_data.http import ProviderHttpClient, RetryPolicy


def client_for(handler, *, policy=None, sleeps=None):
    return ProviderHttpClient(
        base_url="https://provider.test",
        transport=httpx.MockTransport(handler),
        retry_policy=policy or RetryPolicy(),
        sleep=(sleeps.append if sleeps is not None else lambda _: None),
    )


def test_get_json_returns_json_and_preserves_decimal_values():
    client = client_for(
        lambda request: httpx.Response(200, text='{"price": 10.25}')
    )

    payload = client.get_json("/data")

    assert payload == {"price": Decimal("10.25")}


@pytest.mark.parametrize("status_code", [400, 401, 404])
def test_non_retryable_client_errors_do_not_retry(status_code):
    requests = []
    client = client_for(
        lambda request: (
            requests.append(request) or httpx.Response(status_code)
        )
    )

    with pytest.raises(ProviderHttpError) as raised:
        client.get_json("/data")

    assert raised.value.status_code == status_code
    assert len(requests) == 1


@pytest.mark.parametrize("status_code", [429, 500, 503])
def test_retryable_status_codes_retry_then_return_json(status_code):
    calls = []
    sleeps = []

    def handler(request):
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(status_code)
        return httpx.Response(200, text='{"ok": true}')

    client = client_for(handler, sleeps=sleeps)

    assert client.get_json("/data") == {"ok": True}
    assert len(calls) == 3
    assert sleeps == [0.1, 0.2]


def test_rate_limit_after_max_attempts_raises_domain_error():
    calls = []
    client = client_for(
        lambda request: (
            calls.append(request) or httpx.Response(429)
        ),
        policy=RetryPolicy(max_attempts=2),
    )

    with pytest.raises(ProviderRateLimitError) as raised:
        client.get_json("/data")

    assert raised.value.status_code == 429
    assert len(calls) == 2


@pytest.mark.parametrize(
    "exception",
    [httpx.ReadTimeout("timeout"), httpx.ConnectError("network")],
)
def test_transient_network_errors_retry_then_raise_domain_error(exception):
    calls = []
    sleeps = []

    def handler(request):
        calls.append(request)
        raise exception

    client = client_for(
        handler,
        policy=RetryPolicy(max_attempts=2),
        sleeps=sleeps,
    )

    with pytest.raises(ProviderTransportError, match="após tentativas"):
        client.get_json("/data")

    assert len(calls) == 2
    assert sleeps == [0.1]


def test_retry_policy_uses_bounded_exponential_backoff():
    policy = RetryPolicy(
        base_delay_seconds=0.5,
        max_delay_seconds=1.0,
    )

    assert [policy.delay_for_retry(index) for index in range(3)] == [
        0.5,
        1.0,
        1.0,
    ]


def test_invalid_json_raises_provider_response_error():
    client = client_for(lambda request: httpx.Response(200, text="{"))

    with pytest.raises(ProviderResponseError, match="JSON inválido"):
        client.get_json("/data")


def test_authorization_value_is_not_disclosed_in_http_error():
    token = "secret-token-value"
    client = client_for(lambda request: httpx.Response(401))

    with pytest.raises(ProviderHttpError) as raised:
        client.get_json(
            "/data", headers={"Authorization": f"Bearer {token}"}
        )

    assert token not in str(raised.value)


def test_redirect_is_not_followed_automatically():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            302,
            headers={"Location": "https://other-provider.test/data"},
        )

    client = client_for(handler)

    with pytest.raises(ProviderHttpError) as raised:
        client.get_json("/data")

    assert raised.value.status_code == 302
    assert len(calls) == 1


def test_close_and_context_manager_close_client():
    client = client_for(lambda request: httpx.Response(200, text="{}"))
    assert not client.is_closed
    client.close()
    assert client.is_closed
    with pytest.raises(ProviderTransportError, match="fechado"):
        client.get_json("/data")

    with client_for(lambda request: httpx.Response(200, text="{}")) as scoped:
        assert not scoped.is_closed
    assert scoped.is_closed
