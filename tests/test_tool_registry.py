import asyncio
import types

from app.agent.llm_router import LLMRouter
from app.agent.tools.registry import ToolRegistry


class FakeMcpClient:
    def __init__(self, tools=None, fail=False):
        self.tools = tools or []
        self.fail = fail
        self.list_calls = 0

    async def list_tools(self):
        self.list_calls += 1
        if self.fail:
            raise RuntimeError("boom")
        return self.tools


class FakeLLMClient:
    def __init__(self, content):
        self.content = content
        self.messages = []

    async def chat_messages(self, *, messages):
        self.messages.append(messages)
        return self.content


def test_tool_registry_loads_tools_and_builds_prompt_section():
    mcp = FakeMcpClient(
        tools=[
            {
                "name": "search_products",
                "description": "Search approved products",
                "inputSchema": {"type": "object", "properties": {"keyword": {"type": "string"}}},
            },
            types.SimpleNamespace(
                name="get_product_detail",
                description="Return one product",
                inputSchema={"type": "object", "properties": {"product_id": {"type": "integer"}}},
            ),
        ]
    )
    registry = ToolRegistry(mcp)

    tools = asyncio.run(registry.load_tools())

    assert {tool.name for tool in tools} == {"search_products", "get_product_detail"}
    assert registry.get_tool("search_products").description == "Search approved products"
    prompt = registry.build_prompt_section()
    assert "search_products" in prompt
    assert "keyword" in prompt


def test_tool_registry_uses_fallback_when_list_tools_fails():
    registry = ToolRegistry(FakeMcpClient(fail=True))

    tools = asyncio.run(registry.load_tools())

    assert "get_order_detail" in {tool.name for tool in tools}
    assert "search_after_sale_policy" in registry.allowed_tool_names()


def test_llm_router_validates_tools_from_registry():
    registry = ToolRegistry(
        FakeMcpClient(
            tools=[
                {
                    "name": "search_products",
                    "description": "Search products",
                    "inputSchema": {"type": "object", "properties": {"keyword": {"type": "string"}}},
                }
            ]
        )
    )
    asyncio.run(registry.load_tools())
    llm = FakeLLMClient(
        '{"route":"order_query","tool_name":"get_order_detail","arguments":{"order_id":"123"},"answer":"","confidence":0.9}'
    )
    router = LLMRouter(llm_client=llm, tool_registry=registry)

    decision = asyncio.run(router.route(user_id=1, message="订单 123", history=[]))

    assert decision.tool_name is None
    assert decision.arguments == {}
    assert "search_products" in llm.messages[0][0]["content"]
    assert "get_order_detail" not in registry.allowed_tool_names()


def test_llm_router_resolves_canonical_policy_tool_to_available_alias():
    registry = ToolRegistry(
        FakeMcpClient(
            tools=[
                {
                    "name": "query_policy_kb",
                    "description": "Search policy knowledge base",
                    "inputSchema": {"type": "object", "properties": {"question": {"type": "string"}}},
                }
            ]
        )
    )
    asyncio.run(registry.load_tools())
    llm = FakeLLMClient(
        '{"route":"policy_query","tool_name":"search_after_sale_policy","arguments":{"query":"退货政策"},"answer":"","confidence":0.9}'
    )
    router = LLMRouter(llm_client=llm, tool_registry=registry)

    decision = asyncio.run(router.route(user_id=1, message="退货政策", history=[]))

    assert decision.tool_name == "query_policy_kb"
    assert decision.arguments == {"question": "退货政策", "top_k": 5}
