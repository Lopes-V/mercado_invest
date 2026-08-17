from supabase import Client, create_client

from app.config.settings import Settings


def create_supabase_client(
    settings: Settings,
) -> Client:
    return create_client(
        settings.supabase_url,
        settings.supabase_secret_key,
    )