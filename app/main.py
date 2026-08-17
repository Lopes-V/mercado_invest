from app.config.settings import get_settings


def main() -> None:
    settings = get_settings()

    print(
        f"Investment Bot iniciado "
        f"[env={settings.environment.value}]"
    )


if __name__ == "__main__":
    main()