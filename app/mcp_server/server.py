from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.mcp_server.tools.knowledge_tools import search_after_sale_policy as search_after_sale_policy_tool
from app.mcp_server.tools.order_tools import get_order_detail as get_order_detail_tool
from app.mcp_server.tools.order_tools import list_user_orders as list_user_orders_tool
from app.mcp_server.tools.product_tools import get_product_detail as get_product_detail_tool
from app.mcp_server.tools.product_tools import search_products as search_products_tool
from app.mcp_server.tools.refund_tools import get_refund_status as get_refund_status_tool
from app.shared.config import settings

mcp = FastMCP(
    "Shop Support MCP",
    host=settings.mcp_server_host,
    port=settings.mcp_server_port,
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
async def get_order_detail(order_id: str, user_id: int, user_role: str = "buyer") -> dict:
    """Return one visible order as structured JSON."""
    return await get_order_detail_tool(user_id=user_id, user_role=user_role, order_id=order_id)


@mcp.tool()
async def get_order_details(order_id: str, user_id: int, user_role: str = "buyer") -> dict:
    """Backward-compatible alias for get_order_detail."""
    return await get_order_detail_tool(user_id=user_id, user_role=user_role, order_id=order_id)


@mcp.tool()
async def list_user_orders(user_id: int, user_role: str = "buyer", limit: int = 10) -> dict:
    """Return recent visible orders for a user."""
    return await list_user_orders_tool(user_id=user_id, user_role=user_role, limit=limit)


@mcp.tool()
async def search_products(keyword: str, limit: int = 5) -> dict:
    """Search approved products by keyword."""
    return await search_products_tool(keyword=keyword, limit=limit)


@mcp.tool()
async def get_product_detail(product_id: int) -> dict:
    """Return one product as structured JSON."""
    return await get_product_detail_tool(product_id=product_id)


@mcp.tool()
async def get_product_snapshot(product_id: int) -> dict:
    """Backward-compatible alias for get_product_detail."""
    return await get_product_detail_tool(product_id=product_id)


@mcp.tool()
async def get_refund_status(refund_id: int, user_id: int, user_role: str = "buyer") -> dict:
    """Return one visible refund ticket as structured JSON."""
    return await get_refund_status_tool(user_id=user_id, user_role=user_role, refund_id=refund_id)


@mcp.tool()
async def search_after_sale_policy(query: str, top_k: int = 5) -> dict:
    """Search after-sale, refund, shipping, invoice, and platform policy chunks."""
    return await search_after_sale_policy_tool(query=query, top_k=top_k)


@mcp.tool()
async def query_policy_kb(question: str, top_k: int = 5) -> dict:
    """Backward-compatible alias for search_after_sale_policy."""
    return await search_after_sale_policy_tool(query=question, top_k=top_k)


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()

