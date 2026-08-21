create table public.asset_provider_symbols (
    id uuid primary key default gen_random_uuid(),
    asset_id uuid not null,
    provider text not null,
    provider_symbol text not null,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint asset_provider_symbols_asset_fk foreign key (asset_id)
        references public.assets(id) on delete restrict,
    constraint asset_provider_symbols_provider_not_blank_chk check (btrim(provider) <> ''),
    constraint asset_provider_symbols_symbol_not_blank_chk check (btrim(provider_symbol) <> ''),
    constraint asset_provider_symbols_asset_provider_unique unique (asset_id, provider),
    constraint asset_provider_symbols_provider_symbol_unique unique (provider, provider_symbol)
);

create table public.market_quotes (
    id uuid primary key default gen_random_uuid(),
    asset_id uuid not null,
    provider text not null,
    provider_symbol text not null,
    price numeric(38,18) not null,
    currency_code text not null,
    observed_at timestamptz not null,
    received_at timestamptz not null,
    quality text not null,
    created_at timestamptz not null default now(),
    constraint market_quotes_asset_fk foreign key (asset_id)
        references public.assets(id) on delete restrict,
    constraint market_quotes_provider_not_blank_chk check (btrim(provider) <> ''),
    constraint market_quotes_symbol_not_blank_chk check (btrim(provider_symbol) <> ''),
    constraint market_quotes_price_chk check (price >= 0),
    constraint market_quotes_currency_code_chk check (currency_code ~ '^[A-Z0-9]{3,10}$'),
    constraint market_quotes_quality_chk check (quality in ('VALID', 'STALE', 'INCOMPLETE', 'OUTLIER', 'INVALID')),
    constraint market_quotes_identity_unique unique (asset_id, provider, observed_at)
);

create table public.market_candles (
    id uuid primary key default gen_random_uuid(),
    asset_id uuid not null,
    provider text not null,
    provider_symbol text not null,
    interval text not null,
    observed_at timestamptz not null,
    open numeric(38,18) not null,
    high numeric(38,18) not null,
    low numeric(38,18) not null,
    close numeric(38,18) not null,
    volume numeric(38,18),
    adjusted_close numeric(38,18),
    received_at timestamptz not null,
    quality text not null,
    created_at timestamptz not null default now(),
    constraint market_candles_asset_fk foreign key (asset_id)
        references public.assets(id) on delete restrict,
    constraint market_candles_provider_not_blank_chk check (btrim(provider) <> ''),
    constraint market_candles_symbol_not_blank_chk check (btrim(provider_symbol) <> ''),
    constraint market_candles_interval_chk check (interval in ('1m', '5m', '15m', '30m', '1h', '1d', '1wk', '1mo')),
    constraint market_candles_ohlc_chk check (open >= 0 and high >= 0 and low >= 0 and close >= 0 and high >= low and high >= open and high >= close and low <= open and low <= close),
    constraint market_candles_volume_chk check (volume is null or volume >= 0),
    constraint market_candles_adjusted_close_chk check (adjusted_close is null or adjusted_close >= 0),
    constraint market_candles_quality_chk check (quality in ('VALID', 'STALE', 'INCOMPLETE', 'OUTLIER', 'INVALID')),
    constraint market_candles_identity_unique unique (asset_id, provider, interval, observed_at)
);

alter table public.asset_provider_symbols enable row level security;
alter table public.market_quotes enable row level security;
alter table public.market_candles enable row level security;

revoke all privileges on table public.asset_provider_symbols from anon, authenticated, public;
revoke all privileges on table public.market_quotes from anon, authenticated, public;
revoke all privileges on table public.market_candles from anon, authenticated, public;
revoke all privileges on table public.asset_provider_symbols from service_role;
revoke all privileges on table public.market_quotes from service_role;
revoke all privileges on table public.market_candles from service_role;

grant select, insert, update, delete on table public.asset_provider_symbols to service_role;
grant select, insert, update, delete on table public.market_quotes to service_role;
grant select, insert, update, delete on table public.market_candles to service_role;
