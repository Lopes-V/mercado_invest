from pathlib import Path


MIGRATIONS_DIR = Path("supabase/migrations")


def market_data_migration() -> Path:
    matches = sorted(MIGRATIONS_DIR.glob("*_create_market_data_tables.sql"))
    assert len(matches) == 1, "deve existir exatamente uma migration create_market_data_tables"
    return matches[0]


def migration() -> str:
    return " ".join(market_data_migration().read_text(encoding="utf-8").lower().split())


def test_market_data_migration_creates_precise_auditable_tables():
    sql = migration()
    for table in ("asset_provider_symbols", "market_quotes", "market_candles"):
        assert f"create table public.{table}" in sql
        assert f"alter table public.{table} enable row level security;" in sql
        assert f"revoke all privileges on table public.{table} from anon, authenticated, public;" in sql
        assert f"revoke all privileges on table public.{table} from service_role;" in sql
        assert f"grant select, insert, update, delete on table public.{table} to service_role;" in sql
    assert "price numeric(38,18) not null" in sql
    assert "open numeric(38,18) not null" in sql
    assert "market_quotes_identity_unique unique (asset_id, provider, observed_at)" in sql
    assert "market_candles_identity_unique unique (asset_id, provider, interval, observed_at)" in sql


def test_market_data_migration_has_constraints_without_policies_or_extra_grants():
    sql = migration()
    assert "on delete restrict" in sql
    assert "quality in ('valid', 'stale', 'incomplete', 'outlier', 'invalid')" in sql
    assert "interval in ('1m', '5m', '15m', '30m', '1h', '1d', '1wk', '1mo')" in sql
    assert "create policy" not in sql
    for privilege in ("truncate", "trigger", "references", "maintain"):
        assert f"grant {privilege}" not in sql
