import asyncio

from app.agent.loop import SupportAgentLoop
from app.agent.llm_router import RoutingDecision
from app.agent.response_generator import ResponseGenerator


class FakeRouter:
    def __init__(self):
        self.calls = 0

    async def route(self, *, user_id, message, history):
        self.calls += 1
        if self.calls == 1:
            return RoutingDecision(
                route="product_inquiry",
                tool_name="search_products",
                arguments={"keyword": "耳机", "limit": 2},
                confidence=0.88,
                source="llm",
            )
        return RoutingDecision(route="product_inquiry", answer="路由器直接回答不应作为工具后的最终回复", confidence=0.92, source="llm")


class FakeMcpClient:
    def __init__(self):
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append({"name": name, "arguments": arguments})
        return {"success": True, "data": [{"name": "测试耳机", "price": 99, "stock": 3}], "error": None}


class FakeResponseGenerator:
    def __init__(self):
        self.calls = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        return "LLM 生成的耳机推荐回复"


def test_support_agent_loop_calls_tool_and_returns_tool_calls():
    mcp = FakeMcpClient()
    response_generator = FakeResponseGenerator()
    loop = SupportAgentLoop(llm_router=FakeRouter(), mcp_client=mcp, response_generator=response_generator)

    result = asyncio.run(loop.run(user_id=1, session_id="s1", message="推荐耳机", history=[]))

    assert result.route == "product_inquiry"
    assert result.answer == "LLM 生成的耳机推荐回复"
    assert response_generator.calls[0]["tool_result"]["data"][0]["name"] == "测试耳机"
    assert mcp.calls[0]["name"] == "search_products"
    assert result.tool_calls[0]["name"] == "search_products"
    assert result.tool_calls[0]["step"] == 1
    assert result.tool_calls[0]["confidence"] == 0.88
    assert result.tool_calls[0]["routing_source"] == "llm"


class FailingLLMClient:
    async def chat_messages(self, *, messages):
        raise RuntimeError("boom")


def test_response_generator_falls_back_when_llm_fails():
    generator = ResponseGenerator(llm_client=FailingLLMClient())

    answer = asyncio.run(
        generator.generate(
            route="product_inquiry",
            message="推荐耳机",
            tool_result={"success": True, "data": [{"name": "测试耳机"}], "error": None},
        )
    )

    assert "智能客服回复生成暂时不可用" in answer
