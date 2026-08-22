create table public.frozen_opportunity_policies (
    id uuid primary key default gen_random_uuid(),
    policy_version text not null unique,
    source_calibration_run text not null,
    created_at timestamptz not null,
    analysis_algorithm_version text not null,
    train_started_at timestamptz not null,
    train_ended_at timestamptz not null,
    validation_started_at timestamptz not null,
    validation_ended_at timestamptz not null,
    holdout_started_at timestamptz not null,
    holdout_ended_at timestamptz not null,
    metric_rules jsonb not null,
    gross_metrics jsonb not null,
    net_metrics jsonb not null,
    bootstrap_metadata jsonb not null,
    calibration_release_ready boolean not null,
    status text not null,
    constraint frozen_opportunity_policies_version_non_blank check (btrim(policy_version) <> ''),
    constraint frozen_opportunity_policies_source_non_blank check (btrim(source_calibration_run) <> ''),
    constraint frozen_opportunity_policies_algorithm_non_blank check (btrim(analysis_algorithm_version) <> ''),
    constraint frozen_opportunity_policies_status_check check (status in ('FROZEN', 'RETIRED')),
    constraint frozen_opportunity_policies_ranges_check check (
        train_started_at <= train_ended_at
        and validation_started_at <= validation_ended_at
        and holdout_started_at <= holdout_ended_at
        and train_ended_at < validation_started_at
        and validation_ended_at < holdout_started_at
    )
);

create table public.shadow_predictions (
    id uuid primary key default gen_random_uuid(),
    policy_id uuid not null references public.frozen_opportunity_policies(id) on delete restrict,
    asset_id uuid not null references public.assets(id) on delete restrict,
    provider text not null,
    interval text not null,
    prediction_key text not null unique,
    predicted_at timestamptz not null,
    outcome_due_at timestamptz not null,
    reference_price numeric(38,18) not null,
    quality text not null,
    opportunity_level text not null,
    opportunity_score numeric(38,18) not null,
    metrics jsonb not null,
    round_trip_cost_bps numeric(38,18) not null,
    realized_at timestamptz,
    realized_price numeric(38,18),
    gross_return numeric(38,18),
    net_return numeric(38,18),
    realized_positive boolean,
    created_at timestamptz not null default now(),
    constraint shadow_predictions_provider_non_blank check (btrim(provider) <> ''),
    constraint shadow_predictions_interval_check check (interval in ('1m','5m','15m','30m','1h','1d','1wk','1mo')),
    constraint shadow_predictions_key_non_blank check (btrim(prediction_key) <> ''),
    constraint shadow_predictions_prices_positive check (reference_price > 0 and (realized_price is null or realized_price > 0)),
    constraint shadow_predictions_cost_non_negative check (round_trip_cost_bps >= 0),
    constraint shadow_predictions_quality_check check (quality = 'VALID'),
    constraint shadow_predictions_level_check check (opportunity_level in ('NONE','WATCH','INTERESTING','HIGH_INTEREST')),
    constraint shadow_predictions_score_check check (opportunity_score >= 0 and opportunity_score <= 100),
    constraint shadow_predictions_due_check check (outcome_due_at > predicted_at),
    constraint shadow_predictions_outcome_check check (
        (realized_at is null and realized_price is null and gross_return is null and net_return is null and realized_positive is null)
        or (realized_at is not null and realized_price is not null and gross_return is not null and net_return is not null and realized_positive is not null and realized_at >= outcome_due_at)
    )
);

create index frozen_opportunity_policies_status_created_at_idx
    on public.frozen_opportunity_policies (status, created_at desc);
create index shadow_predictions_pending_due_at_idx
    on public.shadow_predictions (outcome_due_at asc)
    where realized_at is null;
create index shadow_predictions_policy_predicted_at_idx
    on public.shadow_predictions (policy_id, predicted_at desc);

alter table public.frozen_opportunity_policies enable row level security;
alter table public.shadow_predictions enable row level security;
revoke all privileges on table public.frozen_opportunity_policies, public.shadow_predictions from anon, authenticated, public, service_role;
grant select, insert, update, delete on table public.frozen_opportunity_policies, public.shadow_predictions to service_role;
