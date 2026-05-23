from __future__ import annotations

from typing import Any

from app.mcp_server.clients.backend_api_client import BackendAPIClient
from app.mcp_server.tools.common import run_tool


async def create_support_ticket(
    user_id: int,
    user_role: str,
    title: str,
    content: str,
    category: str = "other",
    priority: str = "normal",
    source: str = "agent",
    order_id: str | None = None,
    product_id: int | None = None,
    refund_id: int | None = None,
    ai_summary: str = "",
    ai_trace_id: str | None = None,
    trigger_reason: str = "",
    guardrail_flags: list[str] | None = None,
) -> dict:
    payload: dict[str, Any] = {
        "user_id": user_id,
        "user_role": user_role,
        "title": title,
        "content": content,
        "category": category,
        "priority": priority,
        "source": source,
        "ai_summary": ai_summary,
        "trigger_reason": trigger_reason,
        "guardrail_flags": guardrail_flags or [],
    }
    for key, value in {
        "order_id": order_id,
        "product_id": product_id,
        "refund_id": refund_id,
        "ai_trace_id": ai_trace_id,
    }.items():
        if value not in (None, ""):
            payload[key] = value
    return await run_tool("create_support_ticket", lambda: BackendAPIClient().create_support_ticket(**payload))


async def list_support_tickets(user_id: int, user_role: str = "buyer", limit: int = 5) -> dict:
    return await run_tool(
        "list_support_tickets",
        lambda: BackendAPIClient().list_support_tickets(user_id=user_id, user_role=user_role, limit=limit),
    )
