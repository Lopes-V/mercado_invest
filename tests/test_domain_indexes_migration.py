import re
from pathlib import Path


MIGRATIONS_DIR = Path("supabase/migrations")


def get_single_migration(name: str) -> Path:
    migrations = sorted(MIGRATIONS_DIR.glob(name))

    assert len(migrations) == 1

    return migrations[0]


def get_domain_indexes_migration() -> str:
    return re.sub(
        r"\s+",
        " ",
        get_single_migration(
            "*_add_domain_indexes.sql"
        ).read_text(encoding="utf-8"),
    ).strip()


def test_domain_indexes_migration_adds_required_indexes():
    migration = get_domain_indexes_migration()

    assert (
        "create index markets_default_currency_id_idx "
        "on public.markets (default_currency_id);"
        in migration
    )
    assert (
        "create index assets_currency_id_idx "
        "on public.assets (currency_id);"
        in migration
    )


def test_domain_indexes_migration_avoids_redundant_indexes():
    migration = get_domain_indexes_migration()

    redundant_indexes = (
        "on public.currencies (id)",
        "on public.currencies (code)",
        "on public.markets (id)",
        "on public.markets (code)",
        "on public.exchanges (id)",
        "on public.exchanges (market_id)",
        "on public.exchanges (mic)",
        "on public.assets (id)",
        "on public.assets (market_id)",
        "on public.assets (isin)",
    )

    assert all(index not in migration for index in redundant_indexes)


def test_domain_indexes_migration_avoids_speculative_indexes():
    migration = get_domain_indexes_migration()

    speculative_indexes = (
        "on public.assets (symbol)",
        "on public.assets (exchange_id)",
        "on public.assets (asset_type)",
        "on public.assets (is_active)",
        "on public.markets (country_code)",
        "on public.exchanges (timezone)",
    )

    assert all(index not in migration for index in speculative_indexes)


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
    indexes_migration = get_single_migration(
        "*_add_domain_indexes.sql"
    )

    assert (
        currencies_migration.name
        < markets_migration.name
        < exchanges_migration.name
        < assets_migration.name
        < indexes_migration.name
    )
