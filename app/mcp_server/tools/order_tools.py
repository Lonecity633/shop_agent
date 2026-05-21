from __future__ import annotations

from app.mcp_server.clients.backend_api_client import BackendAPIClient
from app.mcp_server.tools.common import run_tool


async def get_order_detail(user_id: int, user_role: str, order_id: str) -> dict:
    return await run_tool(
        "get_order_detail",
        lambda: BackendAPIClient().get_order_detail(user_id=user_id, user_role=user_role, order_id=order_id),
    )


async def list_user_orders(user_id: int, user_role: str, limit: int = 10) -> dict:
    return await run_tool(
        "list_user_orders",
        lambda: BackendAPIClient().list_user_orders(user_id=user_id, user_role=user_role, limit=limit),
    )
