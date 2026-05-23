from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from app.agent.clients.mcp_client import McpClient
from app.shared.config import settings
from app.shared.logging import get_logger

logger = get_logger(__name__)

TOOL_ALIASES = {
    "get_order_details": "get_order_detail",
    "query_policy_kb": "search_after_sale_policy",
    "get_product_snapshot": "get_product_detail",
    "open_support_ticket": "create_support_ticket",
    "get_user_support_tickets": "list_support_tickets",
}

TOOL_CANDIDATES = {
    "get_order_detail": ("get_order_detail", "get_order_details"),
    "list_user_orders": ("list_user_orders",),
    "search_products": ("search_products",),
    "get_product_detail": ("get_product_detail", "get_product_snapshot"),
    "search_after_sale_policy": ("search_after_sale_policy", "query_policy_kb"),
    "get_refund_status": ("get_refund_status",),
    "get_payment_status": ("get_payment_status",),
    "create_support_ticket": ("create_support_ticket", "open_support_ticket"),
    "list_support_tickets": ("list_support_tickets", "get_user_support_tickets"),
}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    def __init__(self, mcp_client: McpClient) -> None:
        self.mcp_client = mcp_client
        self._tools: dict[str, ToolSpec] = {}
        self._loaded_at = 0.0

    async def load_tools(self, *, force: bool = False) -> list[ToolSpec]:
        now = time.time()
        ttl = max(0, int(settings.agent_loop_tool_cache_seconds))
        if not force and self._tools and ttl > 0 and now - self._loaded_at < ttl:
            logger.warning(
                "tool_registry_tools_selected source=cache count=%s ttl=%s age_seconds=%.2f tools=%s",
                len(self._tools),
                ttl,
                now - self._loaded_at,
                sorted(self._tools),
            )
            return list(self._tools.values())

        try:
            logger.info(
                "tool_registry_load_start source=mcp_server server_url=%s force=%s ttl=%s existing_count=%s",
                getattr(self.mcp_client, "server_url", ""),
                force,
                ttl,
                len(self._tools),
            )
            raw_tools = await self.mcp_client.list_tools()
            tools = [tool for tool in (_normalize_tool(item) for item in raw_tools) if tool is not None]
            if not tools:
                raise RuntimeError("MCP list_tools returned no usable tools")
            self._tools = {tool.name: tool for tool in tools}
            self._loaded_at = now
            logger.warning(
                "tool_registry_tools_selected source=mcp_server count=%s tools=%s",
                len(self._tools),
                sorted(self._tools),
            )
        except Exception as exc:
            logger.exception(
                "tool_registry_load_failed existing_count=%s error=%s",
                len(self._tools),
                exc.__class__.__name__,
            )
            if self._tools:
                logger.warning(
                    "tool_registry_tools_selected source=stale_cache_after_mcp_failure count=%s tools=%s",
                    len(self._tools),
                    sorted(self._tools),
                )
            if not self._tools:
                self._tools = {tool.name: tool for tool in _fallback_tools()}
                self._loaded_at = now
                logger.warning(
                    "tool_registry_tools_selected source=fallback_static count=%s tools=%s",
                    len(self._tools),
                    sorted(self._tools),
                )

        return list(self._tools.values())

    def get_tool(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def allowed_tool_names(self) -> set[str]:
        if self._tools:
            return set(self._tools)
        return {tool.name for tool in _fallback_tools()}

    def canonical_tool_name(self, name: str | None) -> str | None:
        if not name:
            return None
        tool_name = str(name).strip()
        if not tool_name or tool_name.lower() in {"none", "null"}:
            return None
        return TOOL_ALIASES.get(tool_name, tool_name)

    def resolve_tool_name(self, name: str | None) -> str | None:
        canonical_name = self.canonical_tool_name(name)
        if canonical_name is None:
            return None

        available = self.allowed_tool_names()
        candidates = TOOL_CANDIDATES.get(canonical_name, (canonical_name,))
        for candidate in candidates:
            if candidate in available:
                return candidate
        return None

    def build_prompt_section(self) -> str:
        tools = list(self._tools.values()) if self._tools else _fallback_tools()
        lines = []
        for tool in sorted(tools, key=lambda item: item.name):
            schema = _compact_json(tool.input_schema)
            description = tool.description or "无描述"
            if schema:
                lines.append(f"- {tool.name}：{description}。input_schema: {schema}")
            else:
                lines.append(f"- {tool.name}：{description}。")
        return "\n".join(lines)


def _normalize_tool(raw_tool: Any) -> ToolSpec | None:
    if isinstance(raw_tool, dict):
        name = _string_value(raw_tool.get("name"))
        description = _string_value(raw_tool.get("description"))
        input_schema = raw_tool.get("input_schema") or raw_tool.get("inputSchema") or {}
    else:
        name = _string_value(getattr(raw_tool, "name", ""))
        description = _string_value(getattr(raw_tool, "description", ""))
        input_schema = (
            getattr(raw_tool, "input_schema", None)
            or getattr(raw_tool, "inputSchema", None)
            or getattr(raw_tool, "inputSchema_", None)
            or {}
        )
    if not name:
        return None
    return ToolSpec(name=name, description=description, input_schema=_schema_to_dict(input_schema))


def _schema_to_dict(schema: Any) -> dict[str, Any]:
    if isinstance(schema, dict):
        return schema
    model_dump = getattr(schema, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return dumped if isinstance(dumped, dict) else {}
    dict_method = getattr(schema, "dict", None)
    if callable(dict_method):
        dumped = dict_method()
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _string_value(value: Any) -> str:
    return str(value or "").strip()


def _compact_json(value: dict[str, Any]) -> str:
    if not value:
        return ""
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return ""


def _fallback_tools() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="get_order_detail",
            description="查询一笔订单详情",
            input_schema={"type": "object", "properties": {"order_id": {"type": "string"}}},
        ),
        ToolSpec(
            name="list_user_orders",
            description="查询用户最近订单",
            input_schema={"type": "object", "properties": {"limit": {"type": "integer", "default": 5}}},
        ),
        ToolSpec(
            name="search_products",
            description="按关键词搜索商品",
            input_schema={
                "type": "object",
                "properties": {"keyword": {"type": "string"}, "limit": {"type": "integer", "default": 5}},
            },
        ),
        ToolSpec(
            name="get_product_detail",
            description="查询商品详情",
            input_schema={"type": "object", "properties": {"product_id": {"type": "integer"}}},
        ),
        ToolSpec(
            name="search_after_sale_policy",
            description="检索售后、发票、运费和平台规则",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}, "top_k": {"type": "integer", "default": 5}},
            },
        ),
        ToolSpec(
            name="get_refund_status",
            description="查询退款单状态",
            input_schema={"type": "object", "properties": {"refund_id": {"type": "integer"}}},
        ),
        ToolSpec(
            name="get_payment_status",
            description="查询订单或支付流水的支付状态",
            input_schema={
                "type": "object",
                "properties": {"order_id": {"type": "string"}, "payment_no": {"type": "string"}},
            },
        ),
        ToolSpec(
            name="create_support_ticket",
            description="创建人工客服工单",
            input_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "category": {"type": "string"},
                    "priority": {"type": "string", "default": "normal"},
                },
            },
        ),
        ToolSpec(
            name="list_support_tickets",
            description="查询用户最近人工客服工单",
            input_schema={"type": "object", "properties": {"limit": {"type": "integer", "default": 5}}},
        ),
    ]
