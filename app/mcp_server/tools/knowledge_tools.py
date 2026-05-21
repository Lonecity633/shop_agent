from __future__ import annotations

from app.mcp_server.clients.backend_api_client import BackendAPIClient
from app.mcp_server.tools.common import run_tool


async def search_after_sale_policy(query: str, top_k: int = 5) -> dict:
    return await run_tool(
        "search_after_sale_policy",
        lambda: BackendAPIClient().search_after_sale_policy(query=query, top_k=top_k),
    )
