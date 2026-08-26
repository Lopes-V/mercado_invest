import httpx


class TelegramClient:
    def __init__(
        self,
        token: str | None,
        timeout: float = 10.0,
        dry_run: bool = False,
    ) -> None:
        if not dry_run and (not isinstance(token, str) or not token.strip()):
            raise ValueError("Telegram token é obrigatório fora do dry-run")
        self._dry_run = dry_run
        self._dry_run_messages: list[tuple[int, str]] = []
        self._base_url = f"https://api.telegram.org/bot{token or ''}"

        self._client = httpx.Client(
            timeout=timeout,
        )

    @property
    def dry_run_messages(self) -> tuple[tuple[int, str], ...]:
        return tuple(self._dry_run_messages)

    def get_me(self) -> dict:
        response = self._client.get(
            f"{self._base_url}/getMe"
        )

        response.raise_for_status()

        payload = response.json()

        if not payload.get("ok"):
            raise RuntimeError(
                "Telegram rejeitou a requisição."
            )

        return payload["result"]

    def get_updates(
        self,
        offset: int | None = None,
        timeout: int = 30,
        limit: int = 100,
    ) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError(
                "Telegram getUpdates limit "
                "deve estar entre 1 e 100."
            )

        if timeout < 0:
            raise ValueError(
                "Telegram getUpdates timeout "
                "não pode ser negativo."
            )

        params = {
            "timeout": timeout,
            "limit": limit,
        }

        if offset is not None:
            params["offset"] = offset

        response = self._client.get(
            f"{self._base_url}/getUpdates",
            params=params,
        )

        response.raise_for_status()

        payload = response.json()

        if not payload.get("ok"):
            raise RuntimeError(
                "Telegram rejeitou getUpdates."
            )

        return payload["result"]

    def send_message(
        self,
        chat_id: int,
        text: str,
    ) -> dict:
        if self._dry_run:
            self._dry_run_messages.append((chat_id, text))
            return {"message_id": len(self._dry_run_messages), "dry_run": True}
        response = self._client.post(
            f"{self._base_url}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
            },
        )

        response.raise_for_status()

        payload = response.json()

        if not payload.get("ok"):
            raise RuntimeError(
                "Telegram rejeitou sendMessage."
            )

        return payload["result"]

    def close(self) -> None:
        self._client.close()
