from uuid import UUID

from supabase import Client

from app.database.models import ExchangeRecord
from app.database.repositories._response import create_one, read_one_or_none


class ExchangeRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def create(
        self,
        *,
        market_id: UUID,
        code: str,
        name: str,
        timezone: str,
        mic: str | None = None,
        is_active: bool = True,
    ) -> ExchangeRecord:
        payload: dict[str, object] = {
            "market_id": str(market_id),
            "code": code,
            "name": name,
            "timezone": timezone,
            "is_active": is_active,
        }

        if mic is not None:
            payload["mic"] = mic

        response = self._client.table("exchanges").insert(payload).execute()

        return create_one(
            response,
            operation="create exchange",
            parser=ExchangeRecord.from_payload,
        )

    def get_by_id(self, exchange_id: UUID) -> ExchangeRecord | None:
        query = self._client.table("exchanges").select("*").eq(
            "id", str(exchange_id)
        )

        return read_one_or_none(
            query,
            operation="get exchange by id",
            parser=ExchangeRecord.from_payload,
        )

    def get_by_market_and_code(
        self, market_id: UUID, code: str
    ) -> ExchangeRecord | None:
        query = (
            self._client.table("exchanges")
            .select("*")
            .eq("market_id", str(market_id))
            .eq("code", code)
        )

        return read_one_or_none(
            query,
            operation="get exchange by market and code",
            parser=ExchangeRecord.from_payload,
        )
