create table public.currencies (
    id uuid primary key default gen_random_uuid(),
    code text not null,
    name text not null,
    symbol text,
    decimal_places smallint not null default 2,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint currencies_code_unique unique (code),
    constraint currencies_code_format_chk
        check (code ~ '^[A-Z0-9]{3,10}$'),
    constraint currencies_name_not_blank_chk
        check (btrim(name) <> ''),
    constraint currencies_decimal_places_chk
        check (decimal_places between 0 and 18)
);
