from __future__ import annotations

from typing import Any

import httpx

from app.shared.config import settings


class BackendAPIClient:
    def __init__(self, *, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.backend_base_url).rstrip("/")

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self.base_url}{path}", params=params)
            response.raise_for_status()
            return response.json()

