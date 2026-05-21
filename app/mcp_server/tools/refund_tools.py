from __future__ import annotations

from app.mcp_server.clients.backend_api_client import BackendAPIClient
from app.mcp_server.tools.common import run_tool


async def get_refund_status(user_id: int, user_role: str, refund_id: int) -> dict:
    return await run_tool(
        "get_refund_status",
        lambda: BackendAPIClient().get_refund_status(user_id=user_id, user_role=user_role, refund_id=refund_id),
    )
