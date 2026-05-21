from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.agent.retrieval import retrieve
from app.agent.tools.shop_tools import execute_get_order_details, fetch_product_snapshot, search_products_by_keyword
from app.crud.support_ticket import create_ticket_from_tool
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.mcp.auth import build_context_user, tool_error, validate_internal_secret
from app.schemas.support_ticket import SupportTicketEscalate
from app.services import support_ticket as ticket_service

mcp = FastMCP(
    "Shop Support MCP",
    host=settings.mcp_server_host,
    port=settings.mcp_server_port,
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
async def get_order_details(order_id: str, user_id: int, user_role: str, internal_secret: str) -> dict:
    """Query one visible order by order number or numeric id, including payment, logistics, and refund summaries."""
    try:
        validate_internal_secret(internal_secret)
        current_user = build_context_user(user_id=user_id, user_role=user_role)
        async with AsyncSessionLocal() as db:
            data = await execute_get_order_details(db, current_user=current_user, order_id=order_id)
        return {"success": bool(data.get("found")), "data": data}
    except Exception as exc:
        return tool_error(exc)


@mcp.tool()
async def get_product_snapshot(product_id: int, user_id: int, user_role: str, internal_secret: str) -> dict:
    """Get one product snapshot by product id, including name, price, stock, seller, and approval status."""
    try:
        validate_internal_secret(internal_secret)
        async with AsyncSessionLocal() as db:
            data = await fetch_product_snapshot(db, product_id)
        return {"success": data is not None, "data": data, "message": "" if data else "未检索到商品"}
    except Exception as exc:
        return tool_error(exc)


@mcp.tool()
async def search_products(keyword: str, limit: int, user_id: int, user_role: str, internal_secret: str) -> dict:
    """Search approved products by keyword in product name or description."""
    try:
        validate_internal_secret(internal_secret)
        async with AsyncSessionLocal() as db:
            data = await search_products_by_keyword(db, keyword, limit=limit)
        return {"success": True, "data": data}
    except Exception as exc:
        return tool_error(exc)


@mcp.tool()
async def query_policy_kb(question: str, top_k: int, user_id: int, user_role: str, internal_secret: str) -> dict:
    """Retrieve support policy knowledge base chunks for platform rules, after-sales, refund, invoice, and shipping questions."""
    try:
        validate_internal_secret(internal_secret)
        async with AsyncSessionLocal() as db:
            chunks = await retrieve(db, question, top_k=top_k)
        return {"success": True, "data": chunks}
    except Exception as exc:
        return tool_error(exc)


@mcp.tool()
async def create_support_ticket(
    title: str,
    content: str,
    user_id: int,
    user_role: str,
    internal_secret: str,
    category: str = "other",
    priority: str = "normal",
    trigger_reason: str = "",
    source_session_id: int | None = None,
    order_id: str | None = None,
    product_id: int | None = None,
    refund_id: int | None = None,
    ai_summary: str = "",
    ai_trace_id: str | None = None,
) -> dict:
    """Create a human support ticket and assign it to seller or admin by issue type and entity context."""
    try:
        validate_internal_secret(internal_secret)
        current_user = build_context_user(user_id=user_id, user_role=user_role)
        async with AsyncSessionLocal() as db:
            ticket = await create_ticket_from_tool(
                db,
                actor=current_user,
                source_session_id=source_session_id,
                title=title,
                content=content,
                category=category,
                priority=priority,
                source="agent",
                order_id=order_id,
                product_id=product_id,
                refund_id=refund_id,
                ai_summary=ai_summary,
                ai_trace_id=ai_trace_id,
                trigger_reason=trigger_reason,
            )
        return {
            "success": True,
            "data": {
                "ticket_id": ticket.id,
                "status": ticket.status.value,
                "assigned_role": ticket.assigned_role.value,
                "assigned_id": ticket.assigned_id,
                "seller_id": ticket.seller_id,
                "admin_id": ticket.admin_id,
                "category": ticket.category.value,
            },
        }
    except Exception as exc:
        return tool_error(exc)


@mcp.tool()
async def escalate_ticket_to_admin(
    ticket_id: int,
    reason: str,
    user_id: int,
    user_role: str,
    internal_secret: str,
) -> dict:
    """Escalate a seller-assigned human support ticket to the admin ticket pool."""
    try:
        validate_internal_secret(internal_secret)
        current_user = build_context_user(user_id=user_id, user_role=user_role)
        async with AsyncSessionLocal() as db:
            ticket = await ticket_service.seller_escalate_ticket(
                db,
                current_user,
                ticket_id,
                SupportTicketEscalate(reason=reason),
            )
        return {
            "success": True,
            "data": {
                "ticket_id": ticket.id,
                "status": ticket.status.value,
                "assigned_role": ticket.assigned_role.value,
                "assigned_id": ticket.assigned_id,
            },
        }
    except Exception as exc:
        return tool_error(exc)


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
