from __future__ import annotations

import json
import time
from typing import Any

from app.shared.config import settings
from app.shared.logging import get_logger

logger = get_logger(__name__)


class McpClient:
    def __init__(self, *, server_url: str | None = None) -> None:
        self.server_url = server_url or settings.mcp_server_url

    async def list_tools(self) -> list[Any]:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        started_at = time.perf_counter()
        logger.info("mcp_list_tools_connecting server_url=%s", self.server_url)
        async with streamablehttp_client(
            self.server_url,
            timeout=settings.mcp_tool_timeout_seconds,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.list_tools()
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info("mcp_list_tools_completed server_url=%s count=%s duration_ms=%s", self.server_url, len(result.tools), duration_ms)
        return list(result.tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        started_at = time.perf_counter()
        logger.info(
            "mcp_tool_call_connecting tool=%s server_url=%s args_keys=%s",
            name,
            self.server_url,
            sorted(arguments.keys()),
        )
        try:
            async with streamablehttp_client(
                self.server_url,
                timeout=settings.mcp_tool_timeout_seconds,
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    logger.info("mcp_tool_call_initialized tool=%s server_url=%s", name, self.server_url)
                    result = await session.call_tool(name, arguments)
            extracted = self._extract_result(result)
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.info(
                "mcp_tool_call_completed tool=%s success=%s error=%s duration_ms=%s",
                name,
                extracted.get("success"),
                extracted.get("error"),
                duration_ms,
            )
            return extracted
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.exception(
                "mcp_tool_call_failed tool=%s server_url=%s duration_ms=%s error=%s",
                name,
                self.server_url,
                duration_ms,
                exc.__class__.__name__,
            )
            return {"success": False, "data": None, "error": exc.__class__.__name__}

    @staticmethod
    def _extract_result(result: Any) -> dict[str, Any]:
        structured = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None)
        if isinstance(structured, dict):
            return structured
        content = getattr(result, "content", None) or []
        if content:
            text = getattr(content[0], "text", "")
            if text:
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    logger.exception("mcp_tool_result_invalid_json text_len=%s", len(text))
                    return {"success": False, "data": None, "error": "InvalidToolResult"}
                return parsed if isinstance(parsed, dict) else {"success": True, "data": parsed, "error": None}
        return {"success": True, "data": None, "error": None}
