from __future__ import annotations

from app.mcp_server.clients.backend_api_client import BackendAPIClient
from app.mcp_server.tools.common import run_tool


async def search_products(keyword: str, limit: int = 5) -> dict:
    return await run_tool(
        "search_products",
        lambda: BackendAPIClient().search_products(keyword=keyword, limit=limit),
    )


async def get_product_detail(product_id: int) -> dict:
    return await run_tool("get_product_detail", lambda: BackendAPIClient().get_product_detail(product_id=product_id))
