import re
from pathlib import Path


MIGRATIONS_DIR = Path("supabase/migrations")


def get_single_migration(name: str) -> Path:
    migrations = sorted(MIGRATIONS_DIR.glob(name))

    assert len(migrations) == 1

    return migrations[0]


def get_exchanges_migration() -> str:
    return re.sub(
        r"\s+",
        " ",
        get_single_migration(
            "*_create_exchanges.sql"
        ).read_text(encoding="utf-8"),
    ).strip()


def test_exchanges_migration_defines_required_columns():
    migration = get_exchanges_migration()

    assert "create table public.exchanges (" in migration
    assert "id uuid primary key default gen_random_uuid()" in migration
    assert "market_id uuid not null" in migration
    assert "code text not null" in migration
    assert "name text not null" in migration
    assert "mic text" in migration
    assert "mic text not null" not in migration
    assert "timezone text not null" in migration
    assert "timezone text not null default" not in migration
    assert "is_active boolean not null default true" in migration
    assert "created_at timestamptz not null default now()" in migration
    assert "updated_at timestamptz not null default now()" in migration


def test_exchanges_migration_defines_constraints():
    migration = get_exchanges_migration()

    assert "constraint exchanges_market_fk" in migration
    assert "foreign key (market_id)" in migration
    assert "references public.markets(id)" in migration
    assert "on delete restrict" in migration
    assert "on delete cascade" not in migration.lower()
    assert (
        "constraint exchanges_market_code_unique unique (market_id, code)"
        in migration
    )
    assert "unique (code)" not in migration
    assert "constraint exchanges_code_format_chk" in migration
    assert "check (code ~ '^[A-Z0-9_]{2,20}$')" in migration
    assert "constraint exchanges_name_not_blank_chk" in migration
    assert "check (btrim(name) <> '')" in migration
    assert "constraint exchanges_mic_format_chk" in migration
    assert "mic is null or mic ~ '^[A-Z0-9]{4}$'" in migration
    assert "constraint exchanges_mic_unique unique (mic)" in migration
    assert "constraint exchanges_timezone_format_chk" in migration
    assert (
        "timezone ~ '^[A-Za-z0-9_+.-]+(/[A-Za-z0-9_+.-]+)*$'"
        in migration
    )


def test_exchanges_migration_has_no_future_schema_or_seeds():
    migration = get_exchanges_migration().lower()

    assert "insert into" not in migration
    assert "create table public.assets" not in migration
    assert "create table public.asset_provider_symbols" not in migration
    assert "trading_hours" not in migration
    assert "open_time" not in migration
    assert "close_time" not in migration
    assert "provider_code" not in migration


def test_migrations_are_ordered_by_dependencies():
    currencies_migration = get_single_migration(
        "*_create_currencies.sql"
    )
    markets_migration = get_single_migration(
        "*_create_markets.sql"
    )
    exchanges_migration = get_single_migration(
        "*_create_exchanges.sql"
    )

    assert (
        currencies_migration.name
        < markets_migration.name
        < exchanges_migration.name
    )
