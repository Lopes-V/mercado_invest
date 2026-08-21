create table public.analyses (
    id uuid primary key default gen_random_uuid(), asset_id uuid not null references public.assets(id) on delete restrict,
    interval text not null, reference_at timestamptz not null, algorithm_version text not null, created_at timestamptz not null default now(),
    constraint analyses_interval_check check (interval in ('1m','5m','15m','30m','1h','1d','1wk','1mo')),
    constraint analyses_algorithm_version_non_blank check (btrim(algorithm_version) <> '')
);
create table public.analysis_metrics (
    id uuid primary key default gen_random_uuid(), analysis_id uuid not null references public.analyses(id) on delete restrict,
    metric_name text not null, metric_value numeric(38,18) not null, reference_period integer, created_at timestamptz not null default now(),
    constraint analysis_metrics_name_non_blank check (btrim(metric_name) <> ''),
    constraint analysis_metrics_reference_period_check check (reference_period is null or reference_period > 0),
    constraint analysis_metrics_identity_unique unique nulls not distinct (analysis_id, metric_name, reference_period)
);
alter table public.analyses enable row level security; alter table public.analysis_metrics enable row level security;
revoke all privileges on table public.analyses, public.analysis_metrics from anon, authenticated, public, service_role;
grant select, insert, update, delete on table public.analyses, public.analysis_metrics to service_role;
