import re
from pathlib import Path


MIGRATIONS_DIR = Path("supabase/migrations")


def get_single_migration(name: str) -> Path:
    migrations = sorted(MIGRATIONS_DIR.glob(name))

    assert len(migrations) == 1

    return migrations[0]


def get_assets_migration() -> str:
    return re.sub(
        r"\s+",
        " ",
        get_single_migration(
            "*_create_assets.sql"
        ).read_text(encoding="utf-8"),
    ).strip()


def test_assets_migration_defines_required_columns():
    migration = get_assets_migration()

    assert "create table public.assets (" in migration
    assert "id uuid primary key default gen_random_uuid()" in migration
    assert "market_id uuid not null" in migration
    assert "exchange_id uuid" in migration
    assert "exchange_id uuid not null" not in migration
    assert "currency_id uuid not null" in migration
    assert "symbol text not null" in migration
    assert "name text not null" in migration
    assert "asset_type text not null" in migration
    assert "isin text" in migration
    assert "isin text not null" not in migration
    assert "is_active boolean not null default true" in migration
    assert "created_at timestamptz not null default now()" in migration
    assert "updated_at timestamptz not null default now()" in migration


def test_assets_migration_enforces_referential_integrity():
    migration = get_assets_migration()

    assert (
        "alter table public.exchanges add constraint "
        "exchanges_id_market_unique unique (id, market_id);"
        in migration
    )
    assert "constraint assets_market_fk" in migration
    assert "foreign key (market_id)" in migration
    assert "references public.markets(id)" in migration
    assert "constraint assets_exchange_market_fk" in migration
    assert "foreign key (exchange_id, market_id)" in migration
    assert "references public.exchanges(id, market_id)" in migration
    assert "constraint assets_currency_fk" in migration
    assert "foreign key (currency_id)" in migration
    assert "references public.currencies(id)" in migration
    assert "on delete cascade" not in migration.lower()
    assert migration.count("on delete restrict") == 3


def test_assets_migration_enforces_canonical_identity():
    migration = get_assets_migration()

    assert "constraint assets_symbol_format_chk" in migration
    assert "char_length(symbol) between 1 and 64" in migration
    assert "symbol !~ '[[:space:]]'" in migration
    assert "constraint assets_name_not_blank_chk" in migration
    assert "check (btrim(name) <> '')" in migration
    assert "constraint assets_type_format_chk" in migration
    assert "asset_type ~ '^[A-Z][A-Z0-9_]{1,31}$'" in migration
    assert "asset_type in (" not in migration.lower()
    assert "constraint assets_isin_format_chk" in migration
    assert "isin is null or isin ~ '^[A-Z]{2}[A-Z0-9]{9}[0-9]$'" in migration
    assert "constraint assets_isin_unique unique (isin)" in migration
    assert "constraint assets_identity_unique" in migration
    assert re.search(
        r"unique nulls not distinct\s*\(\s*market_id, "
        r"exchange_id, symbol, currency_id\s*\)",
        migration,
    )


def test_assets_migration_has_no_future_scope_or_hardcodes():
    migration = get_assets_migration().lower()

    assert "insert into" not in migration
    assert "create table public.asset_provider_symbols" not in migration
    assert "create table public.market_quotes" not in migration
    assert "create table public.market_candles" not in migration
    assert "create table public.portfolios" not in migration
    assert "provider_symbol" not in migration
    assert "yahoo_symbol" not in migration
    assert "brapi_symbol" not in migration
    assert "last_price" not in migration
    assert "average_price" not in migration
    assert "quantity" not in migration
    assert "petr" not in migration
    assert "vale" not in migration
    assert "b3" not in migration
    assert "nyse" not in migration
    assert "nasdaq" not in migration


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
    assets_migration = get_single_migration(
        "*_create_assets.sql"
    )

    assert (
        currencies_migration.name
        < markets_migration.name
        < exchanges_migration.name
        < assets_migration.name
    )
