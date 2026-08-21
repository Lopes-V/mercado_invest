create index analyses_asset_interval_reference_at_idx
    on public.analyses (asset_id, interval, reference_at desc);

create index ai_runs_asset_finished_at_idx
    on public.ai_runs (asset_id, finished_at desc);

create index opportunities_asset_evaluated_at_idx
    on public.opportunities (asset_id, evaluated_at desc);

create index alerts_asset_status_sent_at_idx
    on public.alerts (asset_id, status, sent_at desc);

create index backtest_events_run_signal_at_idx
    on public.backtest_events (backtest_run_id, signal_at);

create index paper_orders_account_requested_at_idx
    on public.paper_orders (account_id, requested_at);

create index paper_trades_order_executed_at_idx
    on public.paper_trades (order_id, executed_at);

create index fixed_income_instruments_provider_id_idx
    on public.fixed_income_instruments (provider, id);

create index fixed_income_snapshots_asset_reference_date_idx
    on public.fixed_income_snapshots (asset_id, reference_date desc);

create index fixed_income_history_asset_reference_date_idx
    on public.fixed_income_history (asset_id, reference_date);

create index fx_rates_pair_provider_observed_at_idx
    on public.fx_rates (
        base_currency_code,
        quote_currency_code,
        provider,
        observed_at desc
    );
