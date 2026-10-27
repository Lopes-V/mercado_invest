from types import SimpleNamespace
import pytest
from app.config.settings import Settings, Environment, LogLevel


def test_repeated_collection_runs_on_minute_slots_and_stops_before_deadline():
    from app.market_refresh import run_repeated
    time=[0.];calls=[]
    def sleep(delay):time[0]+=delay
    def collect():
        calls.append(time[0]);time[0]+=5
        return {'status':'SUCCEEDED'}
    result=run_repeated(collect,interval_seconds=60,duration_seconds=270,clock=lambda:time[0],sleep=sleep)
    assert calls==[0,60,120,180,240]
    assert result['rounds']==5 and result['failed_rounds']==0
    assert time[0]==245


def test_slow_collection_skips_missed_slots_instead_of_catching_up():
    from app.market_refresh import run_repeated
    time=[0.];calls=[]
    def collect():calls.append(time[0]);time[0]+=75;return {'status':'SUCCEEDED'}
    def sleep(delay):time[0]+=delay
    run_repeated(collect,interval_seconds=60,duration_seconds=270,clock=lambda:time[0],sleep=sleep)
    assert calls==[0,120,240]


def test_failure_is_visible_and_later_rounds_continue_without_exposing_message():
    from app.market_refresh import run_repeated
    time=[0.];calls=[]
    def collect():
        calls.append(time[0])
        if len(calls)==1:raise RuntimeError('sensitive-secret-value')
        return {'status':'SUCCEEDED'}
    def sleep(delay):time[0]+=delay
    result=run_repeated(collect,interval_seconds=60,duration_seconds=121,clock=lambda:time[0],sleep=sleep)
    assert calls==[0,60,120] and result['failed_rounds']==1
    assert result['last']['status']=='SUCCEEDED'
    assert 'sensitive-secret-value' not in str(result)


def test_zero_duration_collects_once_and_invalid_interval_cannot_spin():
    from app.market_refresh import run_repeated
    calls=[]
    result=run_repeated(lambda:calls.append(1) or {'status':'SUCCEEDED'},interval_seconds=60,duration_seconds=0)
    assert len(calls)==result['rounds']==1
    for value in [0,1,29,True,float('nan')]:
        with pytest.raises(ValueError):run_repeated(lambda:None,interval_seconds=value,duration_seconds=0)


def test_stock_configuration_disables_every_non_quote_gate_and_preserves_credentials():
    from app.market_refresh import quote_only_settings
    settings=Settings(Environment.TEST,LogLevel.INFO,'https://test.supabase.co','supabase','telegram',frozenset(),
        automated_pipeline_enabled=True,automation_enabled=True,production_ready=True,pipeline_simulation_enabled=True,
        shadow_mode_enabled=True,market_history_enabled=True,telegram_summary_enabled=True,
        brapi_token='brapi',twelve_data_api_key='twelve',gemini_api_key='gemini')
    safe=quote_only_settings(settings)
    assert safe.market_quotes_enabled and safe.market_quotes_interval_seconds==300
    assert not any([safe.automated_pipeline_enabled,safe.automation_enabled,safe.production_ready,
        safe.pipeline_simulation_enabled,safe.shadow_mode_enabled,safe.market_history_enabled,safe.telegram_summary_enabled,safe.dry_run_allow_ai])
    assert safe.telegram_bot_token is None and safe.gemini_api_key is None
    assert safe.brapi_token=='brapi' and safe.twelve_data_api_key=='twelve'
    assert settings.automated_pipeline_enabled


def test_stock_round_closes_application_and_reports_scheduler_failures(monkeypatch):
    from app import market_refresh
    closed=[]
    app=SimpleNamespace(scheduler=SimpleNamespace(run_due=lambda **kw:SimpleNamespace(successes=(),failures=(SimpleNamespace(job_name='market_quotes:brapi',error=ValueError('sensitive')),))),close=lambda:closed.append(1))
    settings=Settings(Environment.TEST,LogLevel.INFO,'url','supabase',None,frozenset())
    captured=[]
    monkeypatch.setattr(market_refresh,'get_settings',lambda:settings)
    monkeypatch.setattr(market_refresh,'build_application',lambda s:captured.append(s) or app)
    report=market_refresh.stock_round()
    assert report['status']=='FAILED' and closed==[1]
    assert report['jobs'][0]['error_code']=='ValueError'
    assert 'sensitive' not in str(report)
    assert captured[0].market_quotes_enabled and not captured[0].automation_enabled
