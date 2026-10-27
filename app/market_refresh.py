"""Bounded quote refresh loops for scheduled runners; no alerts or trading."""
import argparse
from dataclasses import replace
from datetime import UTC, datetime
import json
from math import floor
from pathlib import Path
from time import monotonic, sleep as default_sleep

from app.bootstrap import build_application
from app.config.settings import get_settings


def run_repeated(collect, *, interval_seconds=60, duration_seconds=270, clock=monotonic, sleep=default_sleep):
    if type(interval_seconds) is not int or not 30 <= interval_seconds <= 3600:
        raise ValueError('Intervalo deve ser inteiro entre 30 e 3600 segundos')
    if type(duration_seconds) is not int or not 0 <= duration_seconds <= 3600:
        raise ValueError('Duração deve ser inteiro entre 0 e 3600 segundos')
    start = clock()
    rounds = failed = 0
    last = None
    while True:
        try:
            last = collect()
            if not isinstance(last, dict) or last.get('status') not in ('SUCCEEDED', 'FAILED'):
                raise ValueError('Resultado de coleta inválido')
        except Exception as error:
            last = {'status': 'FAILED', 'error_code': type(error).__name__}
        rounds += 1
        failed += last['status'] != 'SUCCEEDED'
        if duration_seconds == 0:
            break
        # Skip elapsed slots. A slow request never creates a catch-up burst.
        next_at = start + (floor((clock() - start) / interval_seconds) + 1) * interval_seconds
        if next_at >= start + duration_seconds:
            break
        sleep(max(0, next_at - clock()))
    return {'rounds': rounds, 'failed_rounds': failed, 'last': last}


def quote_only_settings(settings):
    return replace(settings, market_quotes_enabled=True, market_quotes_interval_seconds=300,
        market_history_enabled=False, automated_pipeline_enabled=False, automation_enabled=False,
        production_ready=False, pipeline_simulation_enabled=False, shadow_mode_enabled=False,
        telegram_summary_enabled=False, dry_run_allow_ai=False, telegram_bot_token=None,
        telegram_alert_chat_ids=(), gemini_api_key=None, gemini_model=None,
        market_history_candle_interval='1d', automated_pipeline_candle_interval='1d', shadow_candle_interval='1d')


def stock_round():
    application = build_application(quote_only_settings(get_settings()))
    try:
        result = application.scheduler.run_due(now=datetime.now(UTC))
        jobs = []
        for success in result.successes:
            status = success.run.status.value
            jobs.append({'job_name': success.run.job_name, 'status': status,
                         'processed': success.job_result.processed_count if success.job_result else None,
                         'already_executed': success.already_executed})
        for failure in result.failures:
            job = {'job_name': failure.job_name, 'status': 'FAILED', 'error_code': type(failure.error).__name__}
            status = getattr(failure.error, 'status_code', None)
            if type(status) is int and 100 <= status <= 599:
                job['http_status'] = status
            jobs.append(job)
        return {'status': 'FAILED' if any(j['status'] == 'FAILED' for j in jobs) else 'SUCCEEDED', 'jobs': jobs}
    finally:
        application.close()


def crypto_round(output):
    from app.crypto_radar import main as crypto_main
    code = crypto_main(['--provider', 'kraken', '--bootstrap', '--apply', '--persist', '--output', str(output)])
    return {'status': 'SUCCEEDED' if code == 0 else 'FAILED', 'report': json.loads(output.read_text())}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('crypto', 'stocks'), required=True)
    parser.add_argument('--interval', type=int, default=60)
    parser.add_argument('--duration', type=int, default=0)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    collect = (lambda: crypto_round(args.output)) if args.mode == 'crypto' else stock_round
    result = run_repeated(collect, interval_seconds=args.interval, duration_seconds=args.duration)
    report = result['last'].get('report', result['last']).copy()
    report['refresh'] = {key: value for key, value in result.items() if key != 'last'}
    report['refresh']['interval_seconds'] = args.interval
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if result['failed_rounds'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
