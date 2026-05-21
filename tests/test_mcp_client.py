import asyncio
import sys
import types

from app.agent.clients.mcp_client import McpClient


class FakeStream:
    async def __aenter__(self):
        return "read", "write", None

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeSession:
    response_text = '{"success": true, "data": {"ok": true}, "error": null}'

    def __init__(self, read_stream, write_stream):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def initialize(self):
        return None

    async def call_tool(self, name, arguments):
        text_content = types.SimpleNamespace(text=self.response_text)
        return types.SimpleNamespace(content=[text_content])


def install_fake_mcp(monkeypatch, *, stream_factory=None):
    mcp_module = types.ModuleType("mcp")
    mcp_module.ClientSession = FakeSession
    client_module = types.ModuleType("mcp.client")
    stream_module = types.ModuleType("mcp.client.streamable_http")
    stream_module.streamablehttp_client = stream_factory or (lambda *args, **kwargs: FakeStream())
    monkeypatch.setitem(sys.modules, "mcp", mcp_module)
    monkeypatch.setitem(sys.modules, "mcp.client", client_module)
    monkeypatch.setitem(sys.modules, "mcp.client.streamable_http", stream_module)


def test_call_tool_returns_structured_json(monkeypatch):
    install_fake_mcp(monkeypatch)
    FakeSession.response_text = '{"success": true, "data": {"ok": true}, "error": null}'

    result = asyncio.run(McpClient(server_url="http://mcp.test/mcp").call_tool("demo", {"x": 1}))

    assert result == {"success": True, "data": {"ok": True}, "error": None}


def test_call_tool_returns_safe_error_on_transport_failure(monkeypatch):
    def failing_stream(*args, **kwargs):
        raise RuntimeError("boom")

    install_fake_mcp(monkeypatch, stream_factory=failing_stream)

    result = asyncio.run(McpClient(server_url="http://mcp.test/mcp").call_tool("demo", {"x": 1}))

    assert result == {"success": False, "data": None, "error": "RuntimeError"}


def test_call_tool_returns_safe_error_for_non_json_content(monkeypatch):
    install_fake_mcp(monkeypatch)
    FakeSession.response_text = "not json"

    result = asyncio.run(McpClient(server_url="http://mcp.test/mcp").call_tool("demo", {"x": 1}))

    assert result == {"success": False, "data": None, "error": "InvalidToolResult"}
