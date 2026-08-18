create table public.markets (
    id uuid primary key default gen_random_uuid(),
    code text not null,
    name text not null,
    country_code text,
    default_currency_id uuid,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint markets_code_unique unique (code),
    constraint markets_code_format_chk
        check (code ~ '^[A-Z0-9_]{2,16}$'),
    constraint markets_name_not_blank_chk
        check (btrim(name) <> ''),
    constraint markets_country_code_format_chk
        check (
            country_code is null
            or country_code ~ '^[A-Z]{2}$'
        ),
    constraint markets_default_currency_fk
        foreign key (default_currency_id)
        references public.currencies(id)
        on delete restrict
);
