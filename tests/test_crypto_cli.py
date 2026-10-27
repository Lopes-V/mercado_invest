import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app import crypto_radar
from app.market_data.errors import ProviderHttpError, ProviderRateLimitError


@pytest.mark.parametrize('error,status', [
    (ProviderHttpError('sensitive-response-body', status_code=403), 403),
    (ProviderHttpError('sensitive-response-body', status_code=503), 503),
    (ProviderRateLimitError('sensitive-response-body', status_code=429), 429),
    (ValueError('sensitive-response-body'), None),
    (ProviderHttpError('sensitive-response-body', status_code='sensitive-response-body'), None),
])
def test_cli_records_http_status_without_logging_provider_body(monkeypatch, capsys, tmp_path, error, status):
    from app.config import settings
    from app.database import client, repositories
    finishes = []
    class Jobs:
        def __init__(self, client): pass
        def start_run(self, **kwargs): return SimpleNamespace(id=uuid4())
        def finish_run(self, **kwargs): finishes.append(kwargs)
    def fail(request): raise error
    monkeypatch.setattr(settings, 'get_settings', lambda: object())
    monkeypatch.setattr(client, 'create_supabase_client', lambda settings: object())
    monkeypatch.setattr(repositories, 'JobRunRepository', Jobs)
    monkeypatch.setattr(crypto_radar, 'BybitProvider', lambda transport: SimpleNamespace(get_assets=fail))
    output = tmp_path / 'report.json'
    assert crypto_radar.main(['--bootstrap', '--apply', '--persist', '--output', str(output)]) == 1
    printed = capsys.readouterr().out
    report = json.loads(printed)
    assert json.loads(output.read_text()) == report
    assert report['status'] == 'FAILED'
    assert report['error_code'] == type(error).__name__
    assert report.get('http_status') == status
    expected = f'BYBIT_HTTP_{status}' if status else type(error).__name__
    assert finishes[0]['error_code'] == expected
    assert 'sensitive-response-body' not in printed
    assert 'sensitive-response-body' not in str(finishes)
