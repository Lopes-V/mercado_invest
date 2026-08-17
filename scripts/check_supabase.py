from app.config.settings import get_settings
from app.database.client import create_supabase_client


def main() -> None:
    try:
        settings = get_settings()

        client = create_supabase_client(settings)

        client.auth.admin.list_users(
            page=1,
            per_page=1,
        )

    except Exception as exc:
        print(
            "Supabase connection: FAILED "
            f"[{type(exc).__name__}]"
        )

        raise SystemExit(1) from None

    print("Supabase connection: OK")


if __name__ == "__main__":
    main()