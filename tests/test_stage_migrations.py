from pathlib import Path
import pytest

MIGRATIONS=Path("supabase/migrations")
PURPOSES=("create_portfolio_tables","create_analysis_tables","create_ai_opportunity_alert_tables","create_backtesting_paper_trading_tables","harden_job_runs","create_fixed_income_tables","create_fx_rates","add_policy_lifecycle_shadow")
@pytest.mark.parametrize("purpose",PURPOSES)
def test_stage_migration_is_unique_and_secured(purpose):
    matches=sorted(MIGRATIONS.glob(f"*_{purpose}.sql"));assert len(matches)==1
    sql=matches[0].read_text().lower()
    if purpose != "harden_job_runs":
        assert "enable row level security" in sql and "from anon, authenticated, public, service_role" in sql and "grant select, insert, update, delete" in sql
    assert "numeric(38,18)" in sql or purpose=="harden_job_runs"


def test_policy_lifecycle_migration_has_idempotency_and_only_justified_indexes():
    matches = sorted(MIGRATIONS.glob("*_add_policy_lifecycle_shadow.sql"))
    assert len(matches) == 1
    assert matches[0].name == "20260821235316_add_policy_lifecycle_shadow.sql"
    sql = matches[0].read_text().lower()
    assert "prediction_key text not null unique" in sql
    assert "where realized_at is null" in sql
    assert "enable row level security" in sql
    assert "from anon, authenticated, public, service_role" in sql
    assert "grant select, insert, update, delete" in sql
    assert "policy " not in sql

def test_stage_query_indexes_migration_is_unique_and_only_adds_expected_indexes():
    matches=sorted(MIGRATIONS.glob("*_add_stage5_16_query_indexes.sql"));assert len(matches)==1
    sql=matches[0].read_text().lower()
    expected=(
        "analyses_asset_interval_reference_at_idx",
        "ai_runs_asset_finished_at_idx",
        "opportunities_asset_evaluated_at_idx",
        "alerts_asset_status_sent_at_idx",
        "backtest_events_run_signal_at_idx",
        "paper_orders_account_requested_at_idx",
        "paper_trades_order_executed_at_idx",
        "fixed_income_instruments_provider_id_idx",
        "fixed_income_snapshots_asset_reference_date_idx",
        "fixed_income_history_asset_reference_date_idx",
        "fx_rates_pair_provider_observed_at_idx",
    )
    assert all(name in sql for name in expected)
    assert sql.count("create index") == len(expected)
    assert "drop " not in sql and "alter " not in sql and "grant " not in sql and "policy" not in sql
