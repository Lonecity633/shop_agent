from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.agent.llm_client import LLMClient
from app.agent.prompt_assembler import PromptAssembler
from app.agent.tools.registry import TOOL_ALIASES, ToolRegistry
from app.shared.config import settings
from app.shared.logging import get_logger


logger = get_logger(__name__)


@dataclass
class RoutingDecision:
    route: str
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    answer: str = ""
    confidence: float = 0.0
    source: str = "llm"


class LLMRouter:
    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        tool_registry: ToolRegistry | None = None,
        prompt_assembler: PromptAssembler | None = None,
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.tool_registry = tool_registry
        self.prompt_assembler = prompt_assembler or PromptAssembler()

    async def route(
        self,
        *,
        user_id: int,
        message: str,
        history: list[dict[str, str]],
    ) -> RoutingDecision:
        prompt_history = select_prompt_history(history)
        logger.info(
            "llm_router_history_selected user_id=%s input_history_count=%s prompt_history_count=%s has_memory=%s roles=%s",
            user_id,
            len(history),
            len(prompt_history),
            any(item.get("role") == "memory" for item in prompt_history),
            [item.get("role", "") for item in prompt_history],
        )
        result = await self.llm_client.chat_messages(
            messages=[
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_prompt(message=message, history=prompt_history)},
            ]
        )
        payload = parse_json_object(result)
        decision = self._parse_payload(payload)
        sanitized_arguments = self._sanitize_arguments(
            user_id=user_id,
            route=decision.route,
            tool_name=decision.tool_name,
            arguments=decision.arguments,
            message=message,
        )
        if decision.tool_name is not None and not sanitized_arguments:
            decision.tool_name = None
            decision.arguments = {}
        else:
            decision.arguments = sanitized_arguments
        return decision

    def _parse_payload(self, payload: dict[str, Any]) -> RoutingDecision:
        route = str(payload.get("route") or payload.get("intent") or "chitchat").strip()
        if route not in {
            "order_query",
            "product_inquiry",
            "policy_query",
            "refund_query",
            "payment_query",
            "support_ticket",
            "chitchat",
        }:
            route = "chitchat"

        raw_tool = payload.get("tool_name") or payload.get("tool")
        tool_name = str(raw_tool).strip() if raw_tool else ""
        tool_name = self._resolve_tool_name(tool_name)

        raw_args = payload.get("arguments") or payload.get("tool_args") or {}
        arguments = raw_args if isinstance(raw_args, dict) else {}

        try:
            confidence = float(payload.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0

        return RoutingDecision(
            route=route,
            tool_name=tool_name,
            arguments=arguments,
            answer=str(payload.get("answer") or "").strip(),
            confidence=max(0.0, min(confidence, 1.0)),
        )

    def _resolve_tool_name(self, name: str | None) -> str | None:
        if self.tool_registry is not None:
            return self.tool_registry.resolve_tool_name(name)

        tool_name = str(name or "").strip()
        if not tool_name or tool_name.lower() in {"none", "null"}:
            return None
        tool_name = TOOL_ALIASES.get(tool_name, tool_name)
        return tool_name if tool_name in self._fallback_allowed_tool_names() else None

    @staticmethod
    def _fallback_allowed_tool_names() -> set[str]:
        return {
            "get_order_detail",
            "list_user_orders",
            "search_products",
            "get_product_detail",
            "search_after_sale_policy",
            "get_refund_status",
            "get_payment_status",
            "create_support_ticket",
            "list_support_tickets",
        }

    def _allowed_tool_names(self) -> set[str]:
        if self.tool_registry is not None:
            return self.tool_registry.allowed_tool_names()
        return self._fallback_allowed_tool_names()

    @staticmethod
    def _sanitize_arguments(
        *,
        user_id: int,
        route: str,
        tool_name: str | None,
        arguments: dict[str, Any],
        message: str,
    ) -> dict[str, Any]:
        if tool_name is None:
            return {}
        actual_tool_name = tool_name
        tool_name = TOOL_ALIASES.get(tool_name, tool_name)

        if tool_name == "get_order_detail":
            order_id = str(arguments.get("order_id") or arguments.get("order_no") or "").strip()
            if not order_id:
                return {}
            return {"user_id": user_id, "user_role": "buyer", "order_id": order_id}

        if tool_name == "list_user_orders":
            return {"user_id": user_id, "user_role": "buyer", "limit": _bounded_int(arguments.get("limit"), 5, 1, 10)}

        if tool_name == "get_refund_status":
            refund_id = _optional_int(arguments.get("refund_id"))
            if refund_id is None:
                return {}
            return {"user_id": user_id, "user_role": "buyer", "refund_id": refund_id}

        if tool_name == "get_payment_status":
            order_id = str(arguments.get("order_id") or arguments.get("order_no") or "").strip()
            payment_no = str(arguments.get("payment_no") or "").strip()
            if not order_id and not payment_no:
                order_id = _extract_order_id(message) or ""
                payment_no = _extract_payment_no(message) or ""
            if not order_id and not payment_no:
                return {}
            payload = {"user_id": user_id, "user_role": "buyer"}
            if order_id:
                payload["order_id"] = order_id
            if payment_no:
                payload["payment_no"] = payment_no
            return payload

        if tool_name == "search_products":
            keyword = str(arguments.get("keyword") or arguments.get("query") or message).strip()
            return {"keyword": keyword, "limit": _bounded_int(arguments.get("limit"), 5, 1, 10)}

        if tool_name == "get_product_detail":
            product_id = _optional_int(arguments.get("product_id"))
            if product_id is None:
                return {}
            return {"product_id": product_id}

        if tool_name == "search_after_sale_policy":
            query = str(arguments.get("query") or message).strip()
            if actual_tool_name == "query_policy_kb":
                return {
                    "question": query,
                    "top_k": _bounded_int(arguments.get("top_k"), settings.support_retrieval_top_k, 1, 10),
                }
            return {"query": query, "top_k": _bounded_int(arguments.get("top_k"), settings.support_retrieval_top_k, 1, 10)}

        if tool_name == "create_support_ticket":
            title = str(arguments.get("title") or message).strip()[:200]
            content = str(arguments.get("content") or message).strip()[:8000]
            category = str(arguments.get("category") or _default_ticket_category(route)).strip()
            priority = str(arguments.get("priority") or "normal").strip()
            payload = {
                "user_id": user_id,
                "user_role": "buyer",
                "title": title or "人工客服工单",
                "content": content or title or "需要人工处理",
                "category": category,
                "priority": priority,
                "source": "agent",
                "trigger_reason": str(arguments.get("trigger_reason") or message).strip()[:2000],
            }
            for key in ("order_id", "product_id", "refund_id", "ai_trace_id"):
                value = arguments.get(key)
                if value not in (None, ""):
                    payload[key] = value
            return payload

        if tool_name == "list_support_tickets":
            return {"user_id": user_id, "user_role": "buyer", "limit": _bounded_int(arguments.get("limit"), 5, 1, 20)}

        return {}

    def _system_prompt(self) -> str:
        tools_section = self.tool_registry.build_prompt_section() if self.tool_registry is not None else self._fallback_prompt_section()
        return self.prompt_assembler.route_system_prompt(tools_section=tools_section)

    @staticmethod
    def _fallback_prompt_section() -> str:
        return """- get_order_detail：查询一笔订单详情。arguments: {"order_id":"订单号"}
- list_user_orders：查询用户最近订单。arguments: {"limit":5}
- search_products：按关键词搜索商品。arguments: {"keyword":"关键词","limit":5}
- get_product_detail：查询商品详情。arguments: {"product_id":1}
- search_after_sale_policy：检索售后/发票/运费/平台规则。arguments: {"query":"问题","top_k":5}
- get_refund_status：查询退款单。arguments: {"refund_id":1}
- get_payment_status：查询支付状态。arguments: {"order_id":"订单号或payment_no"}
- create_support_ticket：创建人工工单。arguments: {"title":"标题","content":"问题描述","category":"other","priority":"normal"}
- list_support_tickets：查询用户人工工单。arguments: {"limit":5}"""

    @staticmethod
    def _user_prompt(*, message: str, history: list[dict[str, str]]) -> str:
        prompt_history = select_prompt_history(history)
        return PromptAssembler.route_user_prompt(message=message, history=prompt_history)


def select_prompt_history(history: list[dict[str, str]], *, recent_limit: int = 6) -> list[dict[str, str]]:
    memory_items = [item for item in history if item.get("role") == "memory"]
    non_memory_items = [item for item in history if item.get("role") != "memory"]
    return memory_items + non_memory_items[-recent_limit:]


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    parsed = _optional_int(value)
    if parsed is None:
        parsed = default
    return max(minimum, min(parsed, maximum))


def _extract_order_id(text: str) -> str | None:
    match = re.search(r"\bSO\d{8,}\b", text, flags=re.IGNORECASE)
    if match:
        return match.group(0).upper()
    match = re.search(r"(?:订单|order)\s*#?(\d{1,18})", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _extract_payment_no(text: str) -> str | None:
    match = re.search(r"(?:支付流水|payment)\s*#?([A-Za-z0-9_-]{4,64})", text, flags=re.IGNORECASE)
    return match.group(1) if match else None


def _default_ticket_category(route: str) -> str:
    return {
        "order_query": "logistics_issue",
        "refund_query": "refund_issue",
        "payment_query": "payment_issue",
        "policy_query": "platform_rule",
        "product_inquiry": "product_consultation",
    }.get(route, "other")


def parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if not text:
        return {}
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return {}
        try:
            payload = json.loads(match.group(0))
            return payload if isinstance(payload, dict) else {}
        except json.JSONDecodeError:
            return {}
