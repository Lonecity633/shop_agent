from __future__ import annotations

import time
from typing import Any

import httpx

from app.shared.config import settings
from app.shared.constants import INTERNAL_SECRET_HEADER
from app.shared.logging import get_logger

logger = get_logger(__name__)


class BackendAPIClient:
    def __init__(self, *, base_url: str | None = None, internal_secret: str | None = None) -> None:
        self.base_url = (base_url or settings.backend_base_url).rstrip("/")
        self.internal_secret = internal_secret or settings.mcp_internal_secret

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {INTERNAL_SECRET_HEADER: self.internal_secret}
        started_at = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=settings.mcp_tool_timeout_seconds) as client:
                response = await client.get(f"{self.base_url}{path}", params=params, headers=headers)
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.info(
                "mcp_backend_api_completed path=%s status_code=%s duration_ms=%s params_keys=%s",
                path,
                response.status_code,
                duration_ms,
                sorted((params or {}).keys()),
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.exception(
                "mcp_backend_api_failed path=%s duration_ms=%s error=%s params_keys=%s",
                path,
                duration_ms,
                exc.__class__.__name__,
                sorted((params or {}).keys()),
            )
            raise
        return payload.get("data") if isinstance(payload, dict) and "data" in payload else payload

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {INTERNAL_SECRET_HEADER: self.internal_secret}
        started_at = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=settings.mcp_tool_timeout_seconds) as client:
                response = await client.post(f"{self.base_url}{path}", json=payload, headers=headers)
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.info(
                "mcp_backend_api_post_completed path=%s status_code=%s duration_ms=%s payload_keys=%s",
                path,
                response.status_code,
                duration_ms,
                sorted(payload.keys()),
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.exception(
                "mcp_backend_api_post_failed path=%s duration_ms=%s error=%s payload_keys=%s",
                path,
                duration_ms,
                exc.__class__.__name__,
                sorted(payload.keys()),
            )
            raise
        return data.get("data") if isinstance(data, dict) and "data" in data else data

    async def get_order_detail(self, *, user_id: int, user_role: str, order_id: str) -> dict[str, Any]:
        return await self._get(
            f"/api/internal/tools/orders/{order_id}",
            {"user_id": user_id, "user_role": user_role},
        )

    async def list_user_orders(self, *, user_id: int, user_role: str, limit: int = 10) -> list[dict[str, Any]]:
        data = await self._get(
            f"/api/internal/tools/users/{user_id}/orders",
            {"user_role": user_role, "limit": limit},
        )
        return data if isinstance(data, list) else []

    async def search_products(self, *, keyword: str, limit: int = 5) -> list[dict[str, Any]]:
        data = await self._get("/api/internal/tools/products/search", {"keyword": keyword, "limit": limit})
        return data if isinstance(data, list) else []

    async def get_product_detail(self, *, product_id: int) -> dict[str, Any] | None:
        data = await self._get(f"/api/internal/tools/products/{product_id}")
        return data if isinstance(data, dict) else None

    async def get_refund_status(self, *, user_id: int, user_role: str, refund_id: int) -> dict[str, Any] | None:
        data = await self._get(
            f"/api/internal/tools/refunds/{refund_id}",
            {"user_id": user_id, "user_role": user_role},
        )
        return data if isinstance(data, dict) else None

    async def get_payment_status(
        self,
        *,
        user_id: int,
        user_role: str,
        order_id: str | None = None,
        payment_no: str | None = None,
    ) -> list[dict[str, Any]]:
        data = await self._get(
            "/api/internal/tools/payments/status",
            {"user_id": user_id, "user_role": user_role, "order_id": order_id, "payment_no": payment_no},
        )
        return data if isinstance(data, list) else []

    async def create_support_ticket(self, **payload: Any) -> dict[str, Any] | None:
        data = await self._post("/api/internal/tools/support-tickets", payload)
        return data if isinstance(data, dict) else None

    async def list_support_tickets(self, *, user_id: int, user_role: str, limit: int = 5) -> list[dict[str, Any]]:
        data = await self._get(
            f"/api/internal/tools/users/{user_id}/support-tickets",
            {"user_role": user_role, "limit": limit},
        )
        return data if isinstance(data, list) else []

    async def search_after_sale_policy(self, *, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        data = await self._get("/api/internal/tools/knowledge/policies/search", {"query": query, "top_k": top_k})
        return data if isinstance(data, list) else []
