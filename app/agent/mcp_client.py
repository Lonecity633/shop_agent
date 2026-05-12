from __future__ import annotations

import json
import time
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud.audit import append_audit
from app.models.user import User


class McpToolError(RuntimeError):
    pass


class McpToolClient:
    def __init__(self, *, server_url: str | None = None):
        self.server_url = server_url or settings.mcp_server_url

    async def call_tool(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        session_id: int | None,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        started = time.perf_counter()
        payload = {
            **arguments,
            "user_id": current_user.id,
            "user_role": current_user.role.value,
            "internal_secret": settings.mcp_internal_secret,
        }
        ok = False
        error_code = ""
        result_summary: dict[str, Any] = {}
        try:
            async with streamablehttp_client(
                self.server_url,
                timeout=settings.mcp_tool_timeout_seconds,
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, payload)
            data = self._extract_result(result)
            ok = bool(data.get("success", True))
            error_code = str(data.get("error_code") or "")
            result_summary = self._summarize_result(data)
            if not ok:
                raise McpToolError(str(data.get("message") or error_code or "MCP 工具调用失败"))
            return data
        except Exception as exc:
            if not error_code:
                error_code = exc.__class__.__name__
            raise
        finally:
            latency_ms = int((time.perf_counter() - started) * 1000)
            await append_audit(
                db,
                entity_type="support_session",
                entity_id=session_id or 0,
                action="mcp_tool_called",
                actor_id=current_user.id,
                actor_role=current_user.role.value,
                before_state={
                    "tool_name": tool_name,
                    "args": self._summarize_args(arguments),
                },
                after_state={
                    "success": ok,
                    "error_code": error_code,
                    "latency_ms": latency_ms,
                    "result": result_summary,
                },
                reason=f"MCP tool {tool_name}",
            )

    @staticmethod
    def _extract_result(result: Any) -> dict[str, Any]:
        structured = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None)
        if isinstance(structured, dict):
            return structured

        content = getattr(result, "content", None) or []
        if content:
            text = getattr(content[0], "text", "")
            if text:
                parsed = json.loads(text)
                return parsed if isinstance(parsed, dict) else {"success": True, "data": parsed}
        return {"success": True, "data": None}

    @staticmethod
    def _summarize_args(arguments: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in arguments.items() if key not in {"internal_secret"}}

    @staticmethod
    def _summarize_result(data: dict[str, Any]) -> dict[str, Any]:
        payload = data.get("data")
        if isinstance(payload, list):
            return {"items": len(payload)}
        if isinstance(payload, dict):
            return {
                key: payload.get(key)
                for key in ("found", "order_id", "order_status", "pay_status", "product_id", "name")
                if key in payload
            }
        return {"has_data": payload is not None}
