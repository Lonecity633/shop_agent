from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.agent.retrieval import retrieve
from app.agent.tools.shop_tools import execute_get_order_details, fetch_product_snapshot, search_products_by_keyword
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.mcp.auth import build_context_user, tool_error, validate_internal_secret

mcp = FastMCP(
    "Shop Support MCP",
    host=settings.mcp_server_host,
    port=settings.mcp_server_port,
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
async def get_order_details(order_id: str, user_id: int, user_role: str, internal_secret: str) -> dict:
    """Query an order visible to the current user, including payment and refund summaries."""
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
    """Get one product snapshot by product id."""
    try:
        validate_internal_secret(internal_secret)
        async with AsyncSessionLocal() as db:
            data = await fetch_product_snapshot(db, product_id)
        return {"success": data is not None, "data": data, "message": "" if data else "未检索到商品"}
    except Exception as exc:
        return tool_error(exc)


@mcp.tool()
async def search_products(keyword: str, limit: int, user_id: int, user_role: str, internal_secret: str) -> dict:
    """Search approved products by keyword."""
    try:
        validate_internal_secret(internal_secret)
        async with AsyncSessionLocal() as db:
            data = await search_products_by_keyword(db, keyword, limit=limit)
        return {"success": True, "data": data}
    except Exception as exc:
        return tool_error(exc)


@mcp.tool()
async def query_policy_kb(question: str, top_k: int, user_id: int, user_role: str, internal_secret: str) -> dict:
    """Retrieve support policy knowledge base chunks for the question."""
    try:
        validate_internal_secret(internal_secret)
        async with AsyncSessionLocal() as db:
            chunks = await retrieve(db, question, top_k=top_k)
        return {"success": True, "data": chunks}
    except Exception as exc:
        return tool_error(exc)


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
