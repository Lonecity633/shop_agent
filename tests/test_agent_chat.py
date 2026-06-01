import asyncio

from app.agent.context_manager import ContextManager
from app.agent.service import AgentService
from app.shared.config import settings


def run_without_llm_routing(coro):
    old_value = settings.support_llm_routing_enabled
    settings.support_llm_routing_enabled = False
    try:
        return asyncio.run(coro)
    finally:
        settings.support_llm_routing_enabled = old_value


class FakeMcpClient:
    def __init__(self):
        self.calls = []

    async def list_tools(self):
        raise RuntimeError("list_tools unavailable")

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
        if name == "get_payment_status":
            return {"success": True, "data": [{"payment_no": "P1", "status": "succeeded"}], "error": None}
        if name == "create_support_ticket":
            return {"success": True, "data": {"ticket_id": 9, "status": "pending"}, "error": None}
        return {"success": True, "data": None, "error": None}


class FailingOrderMcpClient(FakeMcpClient):
    async def call_tool(self, name, arguments):
        self.calls.append({"name": name, "arguments": arguments})
        if name == "get_order_detail":
            return {"success": False, "data": None, "error": "ORDER_SERVICE_DOWN"}
        if name == "create_support_ticket":
            return {
                "success": True,
                "data": {
                    "ticket_id": 19,
                    "status": "pending",
                    "category": arguments["category"],
                    "priority": arguments["priority"],
                    "assigned_role": "seller",
                    "title": arguments["title"],
                    "trigger_reason": arguments["trigger_reason"],
                },
                "error": None,
            }
        return await super().call_tool(name, arguments)


class FakeResponseGenerator:
    def __init__(self):
        self.calls = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        route = kwargs["route"]
        if route == "order_query":
            return "LLM 生成的订单回复"
        if route == "product_inquiry":
            return "LLM 生成的商品回复"
        if route == "policy_query":
            return "LLM 生成的政策回复"
        if route == "payment_query":
            return "LLM 生成的支付回复"
        if route == "support_ticket":
            return "LLM 生成的工单回复"
        return "LLM 生成的客服回复"


def test_agent_order_question_calls_order_tool():
    mcp = FakeMcpClient()
    response_generator = FakeResponseGenerator()
    service = AgentService(mcp_client=mcp, context_manager=ContextManager(), response_generator=response_generator)
    response = run_without_llm_routing(service.handle_message(1, "s1", "我的订单 123 到哪了"))
    assert response.route == "order_query"
    assert mcp.calls[0]["name"] == "get_order_detail"
    assert response.answer == "LLM 生成的订单回复"
    assert response_generator.calls[0]["tool_result"]["data"]["status"] == "shipped"


def test_agent_product_question_calls_product_tool():
    mcp = FakeMcpClient()
    service = AgentService(mcp_client=mcp, context_manager=ContextManager(), response_generator=FakeResponseGenerator())
    response = run_without_llm_routing(service.handle_message(1, "s1", "这个商品怎么样"))
    assert response.route == "product_inquiry"
    assert mcp.calls[0]["name"] == "search_products"
    assert response.answer == "LLM 生成的商品回复"


def test_agent_policy_question_calls_policy_tool():
    mcp = FakeMcpClient()
    service = AgentService(mcp_client=mcp, context_manager=ContextManager(), response_generator=FakeResponseGenerator())
    response = run_without_llm_routing(service.handle_message(1, "s1", "退货政策是什么"))
    assert response.route == "policy_query"
    assert mcp.calls[0]["name"] == "search_after_sale_policy"
    assert response.answer == "LLM 生成的政策回复"


def test_agent_payment_question_calls_payment_tool():
    mcp = FakeMcpClient()
    service = AgentService(mcp_client=mcp, context_manager=ContextManager(), response_generator=FakeResponseGenerator())
    response = run_without_llm_routing(service.handle_message(1, "s1", "订单 123 支付状态怎么样"))
    assert response.route == "payment_query"
    assert mcp.calls[0]["name"] == "get_payment_status"
    assert response.answer == "LLM 生成的支付回复"


def test_agent_human_request_creates_support_ticket():
    mcp = FakeMcpClient()
    service = AgentService(mcp_client=mcp, context_manager=ContextManager(), response_generator=FakeResponseGenerator())
    response = run_without_llm_routing(service.handle_message(1, "s1", "我要投诉并转人工客服"))
    assert response.route == "support_ticket"
    assert mcp.calls[0]["name"] == "create_support_ticket"
    assert response.ticket_id == 9
    assert response.trace_id


def test_agent_complaint_creates_high_priority_complaint_ticket():
    mcp = FakeMcpClient()
    service = AgentService(mcp_client=mcp, context_manager=ContextManager(), response_generator=FakeResponseGenerator())
    response = run_without_llm_routing(service.handle_message(1, "s1", "我要投诉商家服务太差了"))

    assert response.route == "support_ticket"
    assert mcp.calls[0]["name"] == "create_support_ticket"
    assert mcp.calls[0]["arguments"]["category"] == "complaint"
    assert mcp.calls[0]["arguments"]["priority"] == "high"
    assert "complaint" in mcp.calls[0]["arguments"]["trigger_reason"]


def test_agent_dispute_creates_platform_rule_ticket():
    mcp = FakeMcpClient()
    service = AgentService(mcp_client=mcp, context_manager=ContextManager(), response_generator=FakeResponseGenerator())
    response = run_without_llm_routing(service.handle_message(1, "s1", "商家拒绝退款，我要求平台介入仲裁"))

    assert response.route == "support_ticket"
    assert mcp.calls[0]["arguments"]["category"] == "platform_rule"
    assert mcp.calls[0]["arguments"]["priority"] == "high"
    assert "dispute" in mcp.calls[0]["arguments"]["trigger_reason"]


def test_agent_timeout_creates_high_priority_business_ticket():
    mcp = FakeMcpClient()
    service = AgentService(mcp_client=mcp, context_manager=ContextManager(), response_generator=FakeResponseGenerator())
    response = run_without_llm_routing(service.handle_message(1, "s1", "我的订单 123 超时还没发货"))

    assert response.route == "support_ticket"
    assert mcp.calls[0]["arguments"]["category"] == "logistics_issue"
    assert mcp.calls[0]["arguments"]["priority"] == "high"
    assert mcp.calls[0]["arguments"]["order_id"] == "123"
    assert "timeout" in mcp.calls[0]["arguments"]["trigger_reason"]


def test_agent_auto_processing_failure_creates_support_ticket():
    mcp = FailingOrderMcpClient()
    service = AgentService(mcp_client=mcp, context_manager=ContextManager(), response_generator=FakeResponseGenerator())
    response = run_without_llm_routing(service.handle_message(1, "s1", "我的订单 123 到哪了"))

    assert [call["name"] for call in mcp.calls] == ["get_order_detail", "create_support_ticket"]
    assert response.route == "support_ticket"
    assert response.ticket_id == 19
    assert response.support_ticket["ticket_id"] == 19
    assert mcp.calls[-1]["arguments"]["category"] == "logistics_issue"
    assert "auto_processing_failed" in mcp.calls[-1]["arguments"]["trigger_reason"]


def test_agent_ticket_status_query_does_not_create_ticket():
    mcp = FakeMcpClient()
    service = AgentService(mcp_client=mcp, context_manager=ContextManager(), response_generator=FakeResponseGenerator())
    response = run_without_llm_routing(service.handle_message(1, "s1", "我的工单状态怎么样"))

    assert response.route == "support_ticket"
    assert mcp.calls[0]["name"] == "list_support_tickets"


def test_agent_session_context_supports_followup_order_question():
    mcp = FakeMcpClient()
    context = ContextManager()
    service = AgentService(mcp_client=mcp, context_manager=context, response_generator=FakeResponseGenerator())
    run_without_llm_routing(service.handle_message(1, "s1", "我的订单 123 到哪了"))
    response = run_without_llm_routing(service.handle_message(1, "s1", "现在到哪了"))
    assert response.route == "order_query"
    assert mcp.calls[-1]["arguments"]["order_id"] == "123"
    assert len(response.context) >= 4


def test_agent_context_is_isolated_by_user_and_session():
    context = ContextManager()
    service_one = AgentService(mcp_client=FakeMcpClient(), context_manager=context, response_generator=FakeResponseGenerator())
    service_two = AgentService(mcp_client=FakeMcpClient(), context_manager=context, response_generator=FakeResponseGenerator())

    run_without_llm_routing(service_one.handle_message(1, "shared", "我的订单 123 到哪了"))
    response = run_without_llm_routing(service_two.handle_message(2, "shared", "现在到哪了"))

    assert response.route == "order_query"
    assert service_two.mcp_client.calls[-1]["name"] == "list_user_orders"
    assert "order_id" not in service_two.mcp_client.calls[-1]["arguments"]


def test_agent_followup_uses_order_entity_after_memory_compaction():
    mcp = FakeMcpClient()
    context = ContextManager(recent_messages=2, summary_trigger_messages=4)
    service = AgentService(mcp_client=mcp, context_manager=context, response_generator=FakeResponseGenerator())

    async def fake_summary(previous_summary, messages, entities):
        return f"用户之前咨询过订单 {entities.get('order_id')} 的物流。"

    service._summarize_memory = fake_summary

    run_without_llm_routing(service.handle_message(1, "s1", "我的订单 123 到哪了"))
    run_without_llm_routing(service.handle_message(1, "s1", "谢谢"))
    compressed = run_without_llm_routing(service.handle_message(1, "s1", "我稍后再看"))

    assert compressed.context[0]["role"] == "memory"
    assert "order_id" in compressed.context[0]["content"]

    response = run_without_llm_routing(service.handle_message(1, "s1", "现在到哪了"))

    assert response.route == "order_query"
    assert mcp.calls[-1]["name"] == "get_order_detail"
    assert mcp.calls[-1]["arguments"]["order_id"] == "123"


def test_agent_service_uses_fallback_tools_when_list_tools_fails():
    mcp = FakeMcpClient()
    service = AgentService(mcp_client=mcp, context_manager=ContextManager(), response_generator=FakeResponseGenerator())

    response = run_without_llm_routing(service.handle_message(1, "s1", "退货政策是什么"))

    assert response.route == "policy_query"
    assert response.tool_calls[0]["name"] == "search_after_sale_policy"
    assert response.tool_calls[0]["step"] == 1
    assert response.answer == "LLM 生成的政策回复"


def test_agent_service_can_disable_agent_loop_with_new_setting():
    mcp = FakeMcpClient()
    service = AgentService(mcp_client=mcp, context_manager=ContextManager(), response_generator=FakeResponseGenerator())
    old_loop_value = settings.support_agent_loop_enabled
    old_llm_value = settings.support_llm_routing_enabled
    settings.support_agent_loop_enabled = False
    settings.support_llm_routing_enabled = False
    try:
        response = asyncio.run(service.handle_message(1, "s1", "这个商品怎么样"))
    finally:
        settings.support_agent_loop_enabled = old_loop_value
        settings.support_llm_routing_enabled = old_llm_value

    assert response.route == "product_inquiry"
    assert response.tool_calls[0]["name"] == "search_products"
    assert response.tool_calls[0]["routing_source"] == "fallback_rules"


def test_agent_loop_enabled_uses_legacy_react_setting_when_new_setting_absent():
    old_loop_value = settings.support_agent_loop_enabled
    old_react_value = settings.support_react_enabled
    settings.support_agent_loop_enabled = None
    settings.support_react_enabled = False
    try:
        assert settings.agent_loop_enabled is False
    finally:
        settings.support_agent_loop_enabled = old_loop_value
        settings.support_react_enabled = old_react_value
