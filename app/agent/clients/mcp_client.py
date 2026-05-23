from __future__ import annotations

import json
import asyncio
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
                logger.info("mcp_list_tools_initialized server_url=%s protocol=streamable-http", self.server_url)
                result = await session.list_tools()
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        tools = list(result.tools)
        logger.warning(
            "mcp_list_tools_completed server_url=%s source=mcp_server protocol=streamable-http count=%s tools=%s duration_ms=%s",
            self.server_url,
            len(tools),
            _tool_names(tools),
            duration_ms,
        )
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        attempts = max(1, int(settings.support_mcp_retry_attempts))
        last_result: dict[str, Any] | None = None
        for attempt in range(1, attempts + 1):
            result = await self._call_tool_once(name, arguments, attempt=attempt)
            if result.get("success") is not False or not _is_retryable_error(result.get("error")) or attempt >= attempts:
                return result
            last_result = result
            await asyncio.sleep(max(0.0, float(settings.support_mcp_retry_backoff_seconds)) * attempt)
        return last_result or {"success": False, "data": None, "error": "ToolFailed"}

    async def _call_tool_once(self, name: str, arguments: dict[str, Any], *, attempt: int) -> dict[str, Any]:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        started_at = time.perf_counter()
        logger.info(
            "mcp_tool_call_connecting tool=%s server_url=%s args_keys=%s attempt=%s",
            name,
            self.server_url,
            sorted(arguments.keys()),
            attempt,
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
                "mcp_tool_call_completed tool=%s success=%s error=%s duration_ms=%s attempt=%s",
                name,
                extracted.get("success"),
                extracted.get("error"),
                duration_ms,
                attempt,
            )
            return extracted
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.exception(
                "mcp_tool_call_failed tool=%s server_url=%s duration_ms=%s error=%s attempt=%s",
                name,
                self.server_url,
                duration_ms,
                exc.__class__.__name__,
                attempt,
            )
            return {"success": False, "data": None, "error": _classify_exception(exc)}

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


def _tool_names(tools: list[Any]) -> list[str]:
    names: list[str] = []
    for tool in tools:
        name = getattr(tool, "name", None)
        if isinstance(tool, dict):
            name = tool.get("name")
        if name:
            names.append(str(name))
    return sorted(names)


def _classify_exception(exc: Exception) -> str:
    name = exc.__class__.__name__
    if name in {"TimeoutError", "ReadTimeout", "ConnectTimeout", "PoolTimeout"}:
        return "Timeout"
    if name in {"ConnectError", "RemoteProtocolError", "NetworkError"}:
        return "TransportError"
    return name


def _is_retryable_error(error: Any) -> bool:
    return str(error or "") in {"Timeout", "TransportError", "ReadTimeout", "ConnectTimeout", "ConnectError", "RemoteProtocolError"}
