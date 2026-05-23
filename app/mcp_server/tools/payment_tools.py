from __future__ import annotations

from app.mcp_server.clients.backend_api_client import BackendAPIClient
from app.mcp_server.tools.common import run_tool


async def get_payment_status(
    user_id: int,
    user_role: str,
    order_id: str | None = None,
    payment_no: str | None = None,
) -> dict:
    return await run_tool(
        "get_payment_status",
        lambda: BackendAPIClient().get_payment_status(
            user_id=user_id,
            user_role=user_role,
            order_id=order_id,
            payment_no=payment_no,
        ),
    )
