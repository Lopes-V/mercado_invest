alter table public.shadow_predictions
    add column reference_at timestamptz;

-- Existing deployments had no explicit reference timestamp.  Preserve their
-- already-valid temporal relationship before making the new field mandatory.
update public.shadow_predictions
set reference_at = predicted_at
where reference_at is null;

alter table public.shadow_predictions
    alter column reference_at set not null,
    drop constraint shadow_predictions_due_check,
    add constraint shadow_predictions_due_check check (outcome_due_at > reference_at),
    add constraint shadow_predictions_reference_identity_unique
        unique (policy_id, asset_id, provider, interval, reference_at);
