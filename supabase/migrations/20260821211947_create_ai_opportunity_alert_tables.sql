create table public.ai_runs (
    id uuid primary key default gen_random_uuid(), analysis_id uuid references public.analyses(id) on delete restrict,
    asset_id uuid not null references public.assets(id) on delete restrict, provider text not null, model text not null, prompt_version text not null,
    started_at timestamptz not null, finished_at timestamptz not null, duration_ms integer not null, input_hash text not null,
    classification text not null, confidence numeric(38,18) not null, positive_factors jsonb not null, negative_factors jsonb not null, risks jsonb not null,
    summary text not null, input_tokens integer, output_tokens integer, created_at timestamptz not null default now(),
    constraint ai_runs_provider_non_blank check (btrim(provider) <> ''), constraint ai_runs_model_non_blank check (btrim(model) <> ''),
    constraint ai_runs_prompt_version_non_blank check (btrim(prompt_version) <> ''), constraint ai_runs_duration_check check (duration_ms >= 0),
    constraint ai_runs_classification_check check (classification in ('POSITIVE','NEUTRAL','NEGATIVE','INSUFFICIENT_EVIDENCE')),
    constraint ai_runs_confidence_check check (confidence >= 0 and confidence <= 1), constraint ai_runs_summary_non_blank check (btrim(summary) <> ''),
    constraint ai_runs_finished_check check (finished_at >= started_at)
);
create table public.opportunities (
    id uuid primary key default gen_random_uuid(), asset_id uuid not null references public.assets(id) on delete restrict,
    analysis_id uuid not null references public.analyses(id) on delete restrict, ai_run_id uuid references public.ai_runs(id) on delete restrict,
    level text not null, score numeric(38,18) not null, evidence_count integer not null, evaluated_at timestamptz not null, policy_version text not null,
    evidence jsonb, created_at timestamptz not null default now(),
    constraint opportunities_level_check check (level in ('NONE','WATCH','INTERESTING','HIGH_INTEREST')), constraint opportunities_score_check check (score >= 0 and score <= 100),
    constraint opportunities_evidence_count_check check (evidence_count >= 0), constraint opportunities_policy_version_non_blank check (btrim(policy_version) <> '')
);
create table public.alerts (
    id uuid primary key default gen_random_uuid(), asset_id uuid not null references public.assets(id) on delete restrict,
    opportunity_id uuid not null references public.opportunities(id) on delete restrict, channel text not null, status text not null, dedupe_key text not null,
    decided_at timestamptz not null, sent_at timestamptz, suppression_reason text, error_code text, created_at timestamptz not null default now(),
    constraint alerts_channel_non_blank check (btrim(channel) <> ''), constraint alerts_status_check check (status in ('PENDING','SENT','SUPPRESSED','FAILED')),
    constraint alerts_dedupe_key_unique unique (dedupe_key), constraint alerts_sent_check check (sent_at is null or sent_at >= decided_at)
);
alter table public.ai_runs enable row level security; alter table public.opportunities enable row level security; alter table public.alerts enable row level security;
revoke all privileges on table public.ai_runs, public.opportunities, public.alerts from anon, authenticated, public, service_role;
grant select, insert, update, delete on table public.ai_runs, public.opportunities, public.alerts to service_role;
