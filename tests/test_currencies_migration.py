import re
from pathlib import Path


def get_currencies_migration() -> str:
    migrations = sorted(
        Path("supabase/migrations").glob(
            "*_create_currencies.sql"
        )
    )

    assert len(migrations) == 1

    return re.sub(
        r"\s+",
        " ",
        migrations[0].read_text(encoding="utf-8"),
    ).strip()


def test_currencies_migration_defines_required_columns():
    migration = get_currencies_migration()

    assert "create table public.currencies (" in migration
    assert "id uuid primary key default gen_random_uuid()" in migration
    assert "code text not null" in migration
    assert "name text not null" in migration
    assert "symbol text" in migration
    assert "decimal_places smallint not null default 2" in migration
    assert "is_active boolean not null default true" in migration
    assert "created_at timestamptz not null default now()" in migration
    assert "updated_at timestamptz not null default now()" in migration


def test_currencies_migration_defines_data_constraints():
    migration = get_currencies_migration()

    assert "constraint currencies_code_unique unique (code)" in migration
    assert "constraint currencies_code_format_chk" in migration
    assert "check (code ~ '^[A-Z0-9]{3,10}$')" in migration
    assert "constraint currencies_name_not_blank_chk" in migration
    assert "check (btrim(name) <> '')" in migration
    assert "constraint currencies_decimal_places_chk" in migration
    assert "check (decimal_places between 0 and 18)" in migration
