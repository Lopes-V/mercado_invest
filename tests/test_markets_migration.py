import re
from pathlib import Path


MIGRATIONS_DIR = Path("supabase/migrations")


def get_single_migration(name: str) -> Path:
    migrations = sorted(MIGRATIONS_DIR.glob(name))

    assert len(migrations) == 1

    return migrations[0]


def get_markets_migration() -> str:
    return re.sub(
        r"\s+",
        " ",
        get_single_migration(
            "*_create_markets.sql"
        ).read_text(encoding="utf-8"),
    ).strip()


def test_markets_migration_defines_required_columns():
    migration = get_markets_migration()

    assert "create table public.markets (" in migration
    assert "id uuid primary key default gen_random_uuid()" in migration
    assert "code text not null" in migration
    assert "name text not null" in migration
    assert "country_code text" in migration
    assert "country_code text not null" not in migration
    assert "default_currency_id uuid" in migration
    assert "is_active boolean not null default true" in migration
    assert "created_at timestamptz not null default now()" in migration
    assert "updated_at timestamptz not null default now()" in migration


def test_markets_migration_defines_constraints():
    migration = get_markets_migration()

    assert "constraint markets_code_unique unique (code)" in migration
    assert "constraint markets_code_format_chk" in migration
    assert "check (code ~ '^[A-Z0-9_]{2,16}$')" in migration
    assert "constraint markets_name_not_blank_chk" in migration
    assert "check (btrim(name) <> '')" in migration
    assert "constraint markets_country_code_format_chk" in migration
    assert (
        "country_code is null or country_code ~ '^[A-Z]{2}$'"
        in migration
    )
    assert "constraint markets_default_currency_fk" in migration
    assert "foreign key (default_currency_id)" in migration
    assert "references public.currencies(id)" in migration
    assert "on delete restrict" in migration
    assert "on delete cascade" not in migration.lower()


def test_markets_migration_has_no_seeds_or_future_tables():
    migration = get_markets_migration().lower()

    assert "insert into" not in migration
    assert "create table public.exchanges" not in migration
    assert "create table public.assets" not in migration
    assert "create table public.asset_provider_symbols" not in migration


def test_currencies_migration_precedes_markets_migration():
    currencies_migration = get_single_migration(
        "*_create_currencies.sql"
    )
    markets_migration = get_single_migration(
        "*_create_markets.sql"
    )

    assert currencies_migration.name < markets_migration.name
