create table public.fx_rates (
    id uuid primary key default gen_random_uuid(), base_currency_code text not null, quote_currency_code text not null, rate numeric(38,18) not null,
    observed_at timestamptz not null, received_at timestamptz not null, provider text not null, quality text not null, created_at timestamptz not null default now(),
    constraint fx_rates_base_currency_check check (base_currency_code ~ '^[A-Z0-9]{3,10}$'), constraint fx_rates_quote_currency_check check (quote_currency_code ~ '^[A-Z0-9]{3,10}$'),
    constraint fx_rates_rate_check check (rate > 0), constraint fx_rates_provider_non_blank check (btrim(provider) <> ''),
    constraint fx_rates_quality_check check (quality in ('VALID','STALE','INCOMPLETE','OUTLIER','INVALID')), constraint fx_rates_identity_unique unique (base_currency_code, quote_currency_code, provider, observed_at)
);
alter table public.fx_rates enable row level security;
revoke all privileges on table public.fx_rates from anon, authenticated, public, service_role;
grant select, insert, update, delete on table public.fx_rates to service_role;
