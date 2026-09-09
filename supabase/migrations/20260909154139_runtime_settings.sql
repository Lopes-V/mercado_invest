create table public.runtime_settings (
    id boolean primary key default true,
    telegram_summary_hour_brt integer not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint runtime_settings_singleton_check check (id),
    constraint runtime_settings_telegram_summary_hour_brt_check
        check (telegram_summary_hour_brt between 0 and 23)
);

alter table public.runtime_settings enable row level security;
revoke all privileges on table public.runtime_settings from anon, authenticated, public;
revoke all privileges on table public.runtime_settings from service_role;
grant select, insert, update, delete on table public.runtime_settings to service_role;
