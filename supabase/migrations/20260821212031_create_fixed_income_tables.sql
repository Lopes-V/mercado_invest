create table public.fixed_income_instruments (
    id uuid primary key default gen_random_uuid(), asset_id uuid not null references public.assets(id) on delete restrict, provider text not null, provider_symbol text not null,
    bond_type text not null, indexer text not null, coupon_type text, maturity_date date not null, currency_code text not null, created_at timestamptz not null default now(),
    constraint fixed_income_instruments_provider_non_blank check (btrim(provider) <> ''), constraint fixed_income_instruments_symbol_non_blank check (btrim(provider_symbol) <> ''),
    constraint fixed_income_instruments_identity_unique unique (asset_id, provider), constraint fixed_income_instruments_currency_check check (currency_code ~ '^[A-Z0-9]{3,10}$')
);
create table public.fixed_income_snapshots (
    id uuid primary key default gen_random_uuid(), asset_id uuid not null references public.assets(id) on delete restrict, provider_symbol text not null, reference_date date not null,
    buy_rate numeric(38,18), sell_rate numeric(38,18), buy_price numeric(38,18), sell_price numeric(38,18), base_price numeric(38,18), received_at timestamptz not null, quality text not null, created_at timestamptz not null default now(),
    constraint fixed_income_snapshots_quality_check check (quality in ('VALID','STALE','INCOMPLETE','OUTLIER','INVALID')), constraint fixed_income_snapshots_identity_unique unique (asset_id, provider_symbol, reference_date)
);
create table public.fixed_income_history (
    id uuid primary key default gen_random_uuid(), asset_id uuid not null references public.assets(id) on delete restrict, provider_symbol text not null, reference_date date not null,
    buy_rate numeric(38,18), sell_rate numeric(38,18), buy_price numeric(38,18), sell_price numeric(38,18), base_price numeric(38,18), received_at timestamptz not null, quality text not null, created_at timestamptz not null default now(),
    constraint fixed_income_history_quality_check check (quality in ('VALID','STALE','INCOMPLETE','OUTLIER','INVALID')), constraint fixed_income_history_identity_unique unique (asset_id, provider_symbol, reference_date)
);
alter table public.fixed_income_instruments enable row level security; alter table public.fixed_income_snapshots enable row level security; alter table public.fixed_income_history enable row level security;
revoke all privileges on table public.fixed_income_instruments, public.fixed_income_snapshots, public.fixed_income_history from anon, authenticated, public, service_role;
grant select, insert, update, delete on table public.fixed_income_instruments, public.fixed_income_snapshots, public.fixed_income_history to service_role;
