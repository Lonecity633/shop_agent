import asyncio

from app.agent.context_manager import ContextManager
from app.agent.service import AgentService


class FakeMcpClient:
    def __init__(self):
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append({"name": name, "arguments": arguments})
        if name == "get_order_detail":
            return {
                "success": True,
                "data": {
                    "found": True,
                    "order_id": arguments["order_id"],
                    "status": "shipped",
                    "pay_status": "paid",
                    "logistics_company": "顺丰",
                    "tracking_no": "SF123",
                    "product": {"name": "测试商品"},
                },
                "error": None,
            }
        if name == "search_products":
            return {"success": True, "data": [{"name": "测试商品", "price": 99, "stock": 8}], "error": None}
        if name == "search_after_sale_policy":
            return {"success": True, "data": [{"content": "七天无理由退货，特殊商品除外。"}], "error": None}
        return {"success": True, "data": None, "error": None}


def test_agent_order_question_calls_order_tool():
    mcp = FakeMcpClient()
    service = AgentService(mcp_client=mcp, context_manager=ContextManager())
    response = asyncio.run(service.handle_message(1, "s1", "我的订单 123 到哪了"))
    assert response.route == "order_query"
    assert mcp.calls[0]["name"] == "get_order_detail"
    assert "shipped" in response.answer


def test_agent_product_question_calls_product_tool():
    mcp = FakeMcpClient()
    service = AgentService(mcp_client=mcp, context_manager=ContextManager())
    response = asyncio.run(service.handle_message(1, "s1", "这个商品怎么样"))
    assert response.route == "product_inquiry"
    assert mcp.calls[0]["name"] == "search_products"
    assert "测试商品" in response.answer


def test_agent_policy_question_calls_policy_tool():
    mcp = FakeMcpClient()
    service = AgentService(mcp_client=mcp, context_manager=ContextManager())
    response = asyncio.run(service.handle_message(1, "s1", "退货政策是什么"))
    assert response.route == "policy_query"
    assert mcp.calls[0]["name"] == "search_after_sale_policy"
    assert "七天无理由" in response.answer


def test_agent_session_context_supports_followup_order_question():
    mcp = FakeMcpClient()
    context = ContextManager()
    service = AgentService(mcp_client=mcp, context_manager=context)
    asyncio.run(service.handle_message(1, "s1", "我的订单 123 到哪了"))
    response = asyncio.run(service.handle_message(1, "s1", "现在到哪了"))
    assert response.route == "order_query"
    assert mcp.calls[-1]["arguments"]["order_id"] == "123"
    assert len(response.context) >= 4

