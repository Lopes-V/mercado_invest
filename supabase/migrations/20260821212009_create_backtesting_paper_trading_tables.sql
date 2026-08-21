create table public.backtest_runs (
    id uuid primary key default gen_random_uuid(), asset_id uuid not null references public.assets(id) on delete restrict, interval text not null,
    started_at timestamptz not null, ended_at timestamptz not null, algorithm_version text not null, opportunity_policy_version text not null, created_at timestamptz not null default now(),
    constraint backtest_runs_interval_check check (interval in ('1m','5m','15m','30m','1h','1d','1wk','1mo')), constraint backtest_runs_period_check check (ended_at >= started_at)
);
create table public.backtest_events (
    id uuid primary key default gen_random_uuid(), backtest_run_id uuid not null references public.backtest_runs(id) on delete restrict,
    signal_at timestamptz not null, level text not null, score numeric(38,18) not null, entry_reference_price numeric(38,18) not null,
    forward_reference_price numeric(38,18) not null, forward_return numeric(38,18) not null, created_at timestamptz not null default now(),
    constraint backtest_events_level_check check (level in ('NONE','WATCH','INTERESTING','HIGH_INTEREST')), constraint backtest_events_score_check check (score >= 0 and score <= 100)
);
create table public.paper_accounts (
    id uuid primary key default gen_random_uuid(), name text not null, base_currency_code text not null, initial_cash numeric(38,18) not null, created_at timestamptz not null default now(),
    constraint paper_accounts_name_non_blank check (btrim(name) <> ''), constraint paper_accounts_currency_check check (base_currency_code ~ '^[A-Z0-9]{3,10}$'), constraint paper_accounts_cash_check check (initial_cash >= 0)
);
create table public.paper_orders (
    id uuid primary key default gen_random_uuid(), account_id uuid not null references public.paper_accounts(id) on delete restrict, asset_id uuid not null references public.assets(id) on delete restrict,
    side text not null, quantity numeric(38,18) not null, status text not null, requested_at timestamptz not null, created_at timestamptz not null default now(),
    constraint paper_orders_side_check check (side in ('BUY','SELL')), constraint paper_orders_status_check check (status in ('PENDING','FILLED','REJECTED','CANCELLED')), constraint paper_orders_quantity_check check (quantity > 0)
);
create table public.paper_trades (
    id uuid primary key default gen_random_uuid(), order_id uuid not null references public.paper_orders(id) on delete restrict, asset_id uuid not null references public.assets(id) on delete restrict,
    side text not null, quantity numeric(38,18) not null, price numeric(38,18) not null, fees numeric(38,18) not null, executed_at timestamptz not null, created_at timestamptz not null default now(),
    constraint paper_trades_side_check check (side in ('BUY','SELL')), constraint paper_trades_quantity_check check (quantity > 0), constraint paper_trades_price_check check (price >= 0), constraint paper_trades_fees_check check (fees >= 0)
);
alter table public.backtest_runs enable row level security; alter table public.backtest_events enable row level security; alter table public.paper_accounts enable row level security; alter table public.paper_orders enable row level security; alter table public.paper_trades enable row level security;
revoke all privileges on table public.backtest_runs, public.backtest_events, public.paper_accounts, public.paper_orders, public.paper_trades from anon, authenticated, public, service_role;
grant select, insert, update, delete on table public.backtest_runs, public.backtest_events, public.paper_accounts, public.paper_orders, public.paper_trades to service_role;
