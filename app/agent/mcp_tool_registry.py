from __future__ import annotations

import time
from copy import deepcopy
from typing import Any

from app.agent.mcp_client import McpToolClient
from app.core.config import settings

INTERNAL_TOOL_ARGS = {"user_id", "user_role", "internal_secret"}


class McpToolRegistry:
    def __init__(self, *, client: McpToolClient | None = None):
        self._client = client or McpToolClient()
        self._cached_at = 0.0
        self._cached_tools: list[dict[str, Any]] = []

    async def openai_tools(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        ttl = max(0, int(settings.support_react_tool_cache_seconds))
        if self._cached_tools and ttl > 0 and now - self._cached_at < ttl:
            return deepcopy(self._cached_tools)

        allowed = self._allowed_tool_names()
        tools = []
        for tool in await self._client.list_tools():
            if allowed and tool.name not in allowed:
                continue
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or tool.title or tool.name,
                        "parameters": self._public_input_schema(tool.inputSchema),
                    },
                }
            )

        self._cached_tools = tools
        self._cached_at = now
        return deepcopy(tools)

    @staticmethod
    def _allowed_tool_names() -> set[str]:
        raw = settings.support_react_allowed_tools
        return {item.strip() for item in raw.split(",") if item.strip()}

    @staticmethod
    def _public_input_schema(input_schema: dict[str, Any]) -> dict[str, Any]:
        schema = deepcopy(input_schema) if isinstance(input_schema, dict) else {"type": "object"}
        schema.setdefault("type", "object")

        properties = schema.get("properties")
        if isinstance(properties, dict):
            for key in INTERNAL_TOOL_ARGS:
                properties.pop(key, None)

        required = schema.get("required")
        if isinstance(required, list):
            schema["required"] = [item for item in required if item not in INTERNAL_TOOL_ARGS]

        schema["additionalProperties"] = False
        return schema
