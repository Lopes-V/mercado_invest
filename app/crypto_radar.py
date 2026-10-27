"""Public Bybit spot radar CLI. No orders, private exchange keys or Telegram."""
import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.crypto.catalog import CryptoCatalog, DEFAULT_SYMBOLS, validate_symbols
from app.market_data.contracts import AssetSearchRequest
from app.market_data.http import ProviderHttpClient
from app.market_data.providers.bybit import BybitProvider


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols', default=os.getenv('CRYPTO_SYMBOLS', ','.join(DEFAULT_SYMBOLS)))
    parser.add_argument('--bootstrap', action='store_true', help='Plan the catalog; --apply creates missing records.')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--persist', action='store_true', help='Persist only validated quote/candle/analysis facts.')
    parser.add_argument('--output', type=Path, help='Optional report path, outside tracked source.')
    args = parser.parse_args(argv)
    if args.apply and not args.bootstrap: parser.error('--apply requires --bootstrap')
    from app.analysis.crypto import CryptoAnalysisEngine
    from app.crypto.radar import CryptoRadarService
    from app.crypto.storage import CryptoStore
    from app.config.settings import get_settings
    from app.database.client import create_supabase_client
    from app.database.repositories import JobRunRepository
    from app.jobs.models import JobRunStatus, JobTrigger
    run = None
    jobs = None
    report = None
    code = 0
    try:
        symbols = validate_symbols(tuple(args.symbols.split(',')))
        client = create_supabase_client(get_settings())
        jobs = JobRunRepository(client)
        if args.persist:
            now = datetime.now(UTC)
            run = jobs.start_run(job_name='crypto_radar:bybit:spot', run_key='crypto_radar:manual:'+str(uuid4()), trigger=JobTrigger.MANUAL, scheduled_for=now, correlation_id=uuid4(), started_at=now)
        with ProviderHttpClient(base_url='https://api.bybit.com') as transport:
            provider = BybitProvider(transport)
            instruments = []
            for symbol in symbols:
                instruments.extend(provider.get_assets(AssetSearchRequest(query=symbol)))
            catalog = CryptoCatalog.from_client(client).bootstrap(instruments, symbols=symbols, apply=args.apply)
            if args.bootstrap and not args.persist:
                report = {**catalog, 'assets': [{'id':str(a.id), 'symbol':a.symbol} for a in catalog['assets']]}
            else:
                if len(catalog['assets']) != len(symbols): raise ValueError('CATALOG_NOT_READY_RUN_BOOTSTRAP_APPLY')
                report = CryptoRadarService(provider=provider, engine=CryptoAnalysisEngine(), store=CryptoStore(client)).scan(catalog['assets'], persist=args.persist)
                if any(p['status'] != 'READY' for p in report['pairs']): code = 1
        if run:
            jobs.finish_run(run_id=run.id, terminal_status=JobRunStatus.FAILED if code else JobRunStatus.SUCCEEDED, finished_at=datetime.now(UTC), error_code='CRYPTO_REPORT_INCOMPLETE' if code else None)
    except Exception as exc:
        # CLI boundary reports only error class; SDK exceptions may embed secrets.
        if run and jobs:
            try:
                jobs.finish_run(run_id=run.id, terminal_status=JobRunStatus.FAILED, finished_at=datetime.now(UTC), error_code=type(exc).__name__)
            except Exception as finish_error:
                print('Failed to record job status: '+type(finish_error).__name__, file=sys.stderr)
        report = {'status':'FAILED', 'error_code':type(exc).__name__}
        code = 1
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized+'\n')
    print(serialized)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
