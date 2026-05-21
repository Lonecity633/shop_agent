from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.shared.logging import get_logger

logger = get_logger(__name__)


def tool_success(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "error": None}


def tool_error(exc: Exception) -> dict[str, Any]:
    return {"success": False, "data": None, "error": exc.__class__.__name__}


async def run_tool(tool_name: str, call: Callable[[], Awaitable[Any]]) -> dict[str, Any]:
    started_at = time.perf_counter()
    try:
        data = await call()
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info("mcp_server_tool_completed tool=%s duration_ms=%s", tool_name, duration_ms)
        return tool_success(data)
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        logger.exception(
            "mcp_server_tool_failed tool=%s duration_ms=%s error=%s",
            tool_name,
            duration_ms,
            exc.__class__.__name__,
        )
        return tool_error(exc)
