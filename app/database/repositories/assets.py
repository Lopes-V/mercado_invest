from uuid import UUID

from supabase import Client

from app.database.models import AssetRecord
from app.database.repositories._response import create_one, read_one_or_none


class AssetRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def create(
        self,
        *,
        market_id: UUID,
        exchange_id: UUID | None,
        currency_id: UUID,
        symbol: str,
        name: str,
        asset_type: str,
        isin: str | None = None,
        is_active: bool = True,
    ) -> AssetRecord:
        payload: dict[str, object] = {
            "market_id": str(market_id),
            "exchange_id": (
                str(exchange_id) if exchange_id is not None else None
            ),
            "currency_id": str(currency_id),
            "symbol": symbol,
            "name": name,
            "asset_type": asset_type,
            "is_active": is_active,
        }

        if isin is not None:
            payload["isin"] = isin

        response = self._client.table("assets").insert(payload).execute()

        return create_one(
            response,
            operation="create asset",
            parser=AssetRecord.from_payload,
        )

    def get_by_id(self, asset_id: UUID) -> AssetRecord | None:
        query = self._client.table("assets").select("*").eq(
            "id", str(asset_id)
        )

        return read_one_or_none(
            query,
            operation="get asset by id",
            parser=AssetRecord.from_payload,
        )

    def get_by_isin(self, isin: str) -> AssetRecord | None:
        query = self._client.table("assets").select("*").eq("isin", isin)

        return read_one_or_none(
            query,
            operation="get asset by isin",
            parser=AssetRecord.from_payload,
        )

    def get_by_identity(
        self,
        *,
        market_id: UUID,
        exchange_id: UUID | None,
        symbol: str,
        currency_id: UUID,
    ) -> AssetRecord | None:
        query = self._client.table("assets").select("*").eq(
            "market_id", str(market_id)
        )

        if exchange_id is None:
            query = query.is_("exchange_id", "null")
        else:
            query = query.eq("exchange_id", str(exchange_id))

        query = query.eq("symbol", symbol).eq(
            "currency_id", str(currency_id)
        )

        return read_one_or_none(
            query,
            operation="get asset by identity",
            parser=AssetRecord.from_payload,
        )
