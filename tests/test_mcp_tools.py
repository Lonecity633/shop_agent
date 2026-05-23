import asyncio

from app.mcp_server.clients.backend_api_client import BackendAPIClient
from app.mcp_server.tools.knowledge_tools import search_after_sale_policy
from app.mcp_server.tools.order_tools import get_order_detail
from app.mcp_server.tools.payment_tools import get_payment_status
from app.mcp_server.tools.product_tools import search_products
from app.mcp_server.tools.support_tools import create_support_ticket, list_support_tickets


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


def test_get_payment_status_uses_backend_http_client(monkeypatch):
    async def fake_get_payment_status(self, *, user_id, user_role, order_id=None, payment_no=None):
        return [{"order_id": order_id, "payment_no": payment_no, "status": "succeeded"}]

    monkeypatch.setattr(BackendAPIClient, "get_payment_status", fake_get_payment_status)
    result = asyncio.run(get_payment_status(user_id=1, user_role="buyer", order_id="SO12345678"))
    assert result["success"] is True
    assert result["data"][0]["status"] == "succeeded"


def test_support_ticket_tools_use_backend_http_client(monkeypatch):
    async def fake_create_support_ticket(self, **payload):
        return {"ticket_id": 7, "title": payload["title"]}

    async def fake_list_support_tickets(self, *, user_id, user_role, limit):
        return [{"ticket_id": 7, "status": "pending"}]

    monkeypatch.setattr(BackendAPIClient, "create_support_ticket", fake_create_support_ticket)
    monkeypatch.setattr(BackendAPIClient, "list_support_tickets", fake_list_support_tickets)

    created = asyncio.run(create_support_ticket(user_id=1, user_role="buyer", title="需要人工", content="请处理"))
    listed = asyncio.run(list_support_tickets(user_id=1, user_role="buyer", limit=5))

    assert created["data"]["ticket_id"] == 7
    assert listed["data"][0]["status"] == "pending"
