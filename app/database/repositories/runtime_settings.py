from collections.abc import Mapping

from supabase import Client

from app.database.models import RepositoryDataError


class RuntimeSettingsRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    @staticmethod
    def _hour(row: Mapping[str, object]) -> int:
        value = row.get("telegram_summary_hour_brt")
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 23:
            raise RepositoryDataError("telegram_summary_hour_brt invalido")
        return value

    def get_telegram_summary_hour_brt(self) -> int | None:
        response = self._client.table("runtime_settings").select("telegram_summary_hour_brt").eq("id", True).limit(1).execute()
        rows = getattr(response, "data", None)
        if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
            raise RepositoryDataError("get runtime settings retornou dados invalidos")
        return None if not rows else self._hour(rows[0])

    def set_telegram_summary_hour_brt(self, hour: int) -> int:
        if isinstance(hour, bool) or not isinstance(hour, int) or not 0 <= hour <= 23:
            raise ValueError("telegram_summary_hour_brt deve estar entre 0 e 23")
        response = self._client.table("runtime_settings").update({"telegram_summary_hour_brt": hour}).eq("id", True).execute()
        rows = getattr(response, "data", None)
        if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
            raise RepositoryDataError("update runtime settings retornou dados invalidos")
        if rows:
            return self._hour(rows[0])
        created = self._client.table("runtime_settings").insert({"id": True, "telegram_summary_hour_brt": hour}).execute()
        created_rows = getattr(created, "data", None)
        if not isinstance(created_rows, list) or len(created_rows) != 1 or not isinstance(created_rows[0], Mapping):
            raise RepositoryDataError("create runtime settings retornou dados invalidos")
        return self._hour(created_rows[0])
