create table public.job_runs (
    id uuid primary key default gen_random_uuid(),
    job_name text not null,
    run_key text not null,
    trigger_type text not null,
    scheduled_for timestamptz not null,
    status text not null,
    correlation_id uuid not null,
    started_at timestamptz not null,
    finished_at timestamptz,
    error_code text,
    error_message text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint job_runs_job_name_non_blank check (btrim(job_name) <> ''),
    constraint job_runs_run_key_non_blank check (btrim(run_key) <> ''),
    constraint job_runs_trigger_type_check check (trigger_type in ('SCHEDULED', 'MANUAL')),
    constraint job_runs_status_check check (status in ('RUNNING', 'SUCCEEDED', 'FAILED', 'SKIPPED')),
    constraint job_runs_run_key_unique unique (run_key),
    constraint job_runs_correlation_id_unique unique (correlation_id),
    constraint job_runs_finished_after_started check (finished_at is null or finished_at >= started_at),
    constraint job_runs_status_finished_coherence check ((status = 'RUNNING' and finished_at is null) or (status <> 'RUNNING' and finished_at is not null)),
    constraint job_runs_error_code_non_blank check (error_code is null or btrim(error_code) <> ''),
    constraint job_runs_error_message_non_blank check (error_message is null or btrim(error_message) <> '')
);

create index job_runs_job_name_scheduled_for_idx on public.job_runs (job_name, scheduled_for desc);

alter table public.job_runs enable row level security;
revoke all privileges on table public.job_runs from anon, authenticated, public;
revoke all privileges on table public.job_runs from service_role;
grant select, insert, update, delete on table public.job_runs to service_role;
