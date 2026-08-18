from uuid import UUID

from supabase import Client

from app.database.models import CurrencyRecord
from app.database.repositories._response import create_one, read_one_or_none


class CurrencyRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def create(
        self,
        *,
        code: str,
        name: str,
        symbol: str | None = None,
        decimal_places: int = 2,
        is_active: bool = True,
    ) -> CurrencyRecord:
        payload: dict[str, object] = {
            "code": code,
            "name": name,
            "decimal_places": decimal_places,
            "is_active": is_active,
        }

        if symbol is not None:
            payload["symbol"] = symbol

        response = self._client.table("currencies").insert(payload).execute()

        return create_one(
            response,
            operation="create currency",
            parser=CurrencyRecord.from_payload,
        )

    def get_by_id(self, currency_id: UUID) -> CurrencyRecord | None:
        query = self._client.table("currencies").select("*").eq(
            "id", str(currency_id)
        )

        return read_one_or_none(
            query,
            operation="get currency by id",
            parser=CurrencyRecord.from_payload,
        )

    def get_by_code(self, code: str) -> CurrencyRecord | None:
        query = self._client.table("currencies").select("*").eq(
            "code", code
        )

        return read_one_or_none(
            query,
            operation="get currency by code",
            parser=CurrencyRecord.from_payload,
        )
