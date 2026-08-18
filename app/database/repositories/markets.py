from uuid import UUID

from supabase import Client

from app.database.models import MarketRecord
from app.database.repositories._response import create_one, read_one_or_none


class MarketRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def create(
        self,
        *,
        code: str,
        name: str,
        country_code: str | None = None,
        default_currency_id: UUID | None = None,
        is_active: bool = True,
    ) -> MarketRecord:
        payload: dict[str, object] = {
            "code": code,
            "name": name,
            "is_active": is_active,
        }

        if country_code is not None:
            payload["country_code"] = country_code
        if default_currency_id is not None:
            payload["default_currency_id"] = str(default_currency_id)

        response = self._client.table("markets").insert(payload).execute()

        return create_one(
            response,
            operation="create market",
            parser=MarketRecord.from_payload,
        )

    def get_by_id(self, market_id: UUID) -> MarketRecord | None:
        query = self._client.table("markets").select("*").eq(
            "id", str(market_id)
        )

        return read_one_or_none(
            query,
            operation="get market by id",
            parser=MarketRecord.from_payload,
        )

    def get_by_code(self, code: str) -> MarketRecord | None:
        query = self._client.table("markets").select("*").eq(
            "code", code
        )

        return read_one_or_none(
            query,
            operation="get market by code",
            parser=MarketRecord.from_payload,
        )
