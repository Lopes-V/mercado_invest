import re
from pathlib import Path


MIGRATIONS_DIR = Path("supabase/migrations")
DOMAIN_TABLES = ("currencies", "markets", "exchanges", "assets")


def get_security_migration() -> str:
    migrations = sorted(
        MIGRATIONS_DIR.glob("*_secure_domain_tables.sql")
    )

    assert len(migrations) == 1

    return re.sub(
        r"\s+",
        " ",
        migrations[0].read_text(encoding="utf-8"),
    ).strip().lower()


def get_service_role_correction_migration() -> str:
    migrations = sorted(
        MIGRATIONS_DIR.glob(
            "*_restrict_service_role_privileges.sql"
        )
    )

    assert len(migrations) == 1

    return re.sub(
        r"\s+",
        " ",
        migrations[0].read_text(encoding="utf-8"),
    ).strip().lower()


def test_security_migration_enables_rls_for_domain_tables():
    migration = get_security_migration()

    for table in DOMAIN_TABLES:
        assert (
            f"alter table public.{table} enable row level security;"
            in migration
        )


def test_security_migration_uses_table_specific_deny_by_default_grants():
    migration = get_security_migration()

    for table in DOMAIN_TABLES:
        assert (
            f"revoke all privileges on table public.{table} "
            "from anon, authenticated, public;"
            in migration
        )
        assert (
            f"grant select, insert, update, delete on table public.{table} "
            "to service_role;"
            in migration
        )


def test_security_migration_has_no_policy_or_security_bypass():
    migration = get_security_migration()

    forbidden_fragments = (
        "disable row level security",
        "force row level security",
        "create policy",
        "auth.role()",
        "security definer",
        "create table",
        "insert into",
    )

    assert all(fragment not in migration for fragment in forbidden_fragments)


def test_security_migration_follows_domain_indexes_migration():
    indexes_migration = next(
        MIGRATIONS_DIR.glob("*_add_domain_indexes.sql")
    )
    security_migration = next(
        MIGRATIONS_DIR.glob("*_secure_domain_tables.sql")
    )

    assert indexes_migration.name < security_migration.name


def test_service_role_correction_restricts_each_domain_table():
    migration = get_service_role_correction_migration()

    grants = re.findall(
        r"grant (.+?) on table public\.\w+ to service_role;",
        migration,
    )

    assert grants == ["select, insert, update, delete"] * 4

    for table in DOMAIN_TABLES:
        assert (
            f"revoke all privileges on table public.{table} "
            "from service_role;"
            in migration
        )
        assert (
            f"grant select, insert, update, delete on table public.{table} "
            "to service_role;"
            in migration
        )


def test_service_role_correction_does_not_change_rls_or_other_roles():
    migration = get_service_role_correction_migration()

    forbidden_fragments = (
        "truncate",
        "trigger",
        "references",
        "maintain",
        "row level security",
        "create policy",
        "alter table",
        "create table",
        "insert into",
        "anon",
        "authenticated",
        "from public",
    )

    assert all(fragment not in migration for fragment in forbidden_fragments)


def test_service_role_correction_follows_security_migration():
    security_migration = next(
        MIGRATIONS_DIR.glob("*_secure_domain_tables.sql")
    )
    correction_migration = next(
        MIGRATIONS_DIR.glob(
            "*_restrict_service_role_privileges.sql"
        )
    )

    assert security_migration.name < correction_migration.name


def test_service_role_correction_is_separate_from_original_rls_migration():
    security_migration = get_security_migration()

    assert not re.search(
        r"revoke all privileges on table public\.\w+ from service_role;",
        security_migration,
    )
