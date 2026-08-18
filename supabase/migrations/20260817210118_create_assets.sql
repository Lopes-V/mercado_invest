alter table public.exchanges
    add constraint exchanges_id_market_unique
    unique (id, market_id);

create table public.assets (
    id uuid primary key default gen_random_uuid(),
    market_id uuid not null,
    exchange_id uuid,
    currency_id uuid not null,
    symbol text not null,
    name text not null,
    asset_type text not null,
    isin text,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint assets_market_fk
        foreign key (market_id)
        references public.markets(id)
        on delete restrict,
    constraint assets_exchange_market_fk
        foreign key (exchange_id, market_id)
        references public.exchanges(id, market_id)
        on delete restrict,
    constraint assets_currency_fk
        foreign key (currency_id)
        references public.currencies(id)
        on delete restrict,
    constraint assets_symbol_format_chk
        check (
            char_length(symbol) between 1 and 64
            and symbol !~ '[[:space:]]'
        ),
    constraint assets_name_not_blank_chk
        check (btrim(name) <> ''),
    constraint assets_type_format_chk
        check (asset_type ~ '^[A-Z][A-Z0-9_]{1,31}$'),
    constraint assets_isin_format_chk
        check (isin is null or isin ~ '^[A-Z]{2}[A-Z0-9]{9}[0-9]$'),
    constraint assets_isin_unique unique (isin),
    constraint assets_identity_unique
        unique nulls not distinct (
            market_id,
            exchange_id,
            symbol,
            currency_id
        )
);
