create table public.exchanges (
    id uuid primary key default gen_random_uuid(),
    market_id uuid not null,
    code text not null,
    name text not null,
    mic text,
    timezone text not null,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint exchanges_market_fk
        foreign key (market_id)
        references public.markets(id)
        on delete restrict,
    constraint exchanges_market_code_unique
        unique (market_id, code),
    constraint exchanges_code_format_chk
        check (code ~ '^[A-Z0-9_]{2,20}$'),
    constraint exchanges_name_not_blank_chk
        check (btrim(name) <> ''),
    constraint exchanges_mic_format_chk
        check (mic is null or mic ~ '^[A-Z0-9]{4}$'),
    constraint exchanges_mic_unique unique (mic),
    constraint exchanges_timezone_format_chk
        check (
            timezone ~ '^[A-Za-z0-9_+.-]+(/[A-Za-z0-9_+.-]+)*$'
        )
);
