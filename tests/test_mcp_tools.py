import asyncio

from app.mcp_server.clients.backend_api_client import BackendAPIClient
from app.mcp_server.tools.knowledge_tools import search_after_sale_policy
from app.mcp_server.tools.order_tools import get_order_detail
from app.mcp_server.tools.product_tools import search_products


def test_get_order_detail_uses_backend_http_client(monkeypatch):
    async def fake_get_order_detail(self, *, user_id, user_role, order_id):
        return {"order_id": order_id, "status": "shipped", "user_id": user_id, "user_role": user_role}

    monkeypatch.setattr(BackendAPIClient, "get_order_detail", fake_get_order_detail)
    result = asyncio.run(get_order_detail(user_id=1, user_role="buyer", order_id="123"))
    assert result["success"] is True
    assert result["data"]["status"] == "shipped"


def test_search_products_uses_backend_http_client(monkeypatch):
    async def fake_search_products(self, *, keyword, limit):
        return [{"product_id": 1, "name": keyword, "stock": limit}]

    monkeypatch.setattr(BackendAPIClient, "search_products", fake_search_products)
    result = asyncio.run(search_products(keyword="手机", limit=3))
    assert result["success"] is True
    assert result["data"][0]["name"] == "手机"


def test_search_after_sale_policy_uses_backend_http_client(monkeypatch):
    async def fake_policy(self, *, query, top_k):
        return [{"chunk_id": 1, "content": query, "score": 0.8}]

    monkeypatch.setattr(BackendAPIClient, "search_after_sale_policy", fake_policy)
    result = asyncio.run(search_after_sale_policy(query="退货政策是什么", top_k=2))
    assert result["success"] is True
    assert result["data"][0]["content"] == "退货政策是什么"

