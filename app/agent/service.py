from __future__ import annotations

import re
import time
from typing import Any

from app.agent.clients.mcp_client import McpClient
from app.agent.context_manager import ContextManager
from app.agent.llm_router import LLMRouter, RoutingDecision
from app.agent.response_generator import ResponseGenerator
from app.shared.config import settings
from app.shared.logging import get_logger
from app.shared.schemas.agent import AgentChatResponse

logger = get_logger(__name__)


class AgentService:
    def __init__(
        self,
        *,
        mcp_client: McpClient | None = None,
        context_manager: ContextManager | None = None,
        response_generator: ResponseGenerator | None = None,
        llm_router: LLMRouter | None = None,
    ) -> None:
        self.mcp_client = mcp_client or McpClient()
        self.context_manager = context_manager or ContextManager()
        self.response_generator = response_generator or ResponseGenerator()
        self.llm_router = llm_router or LLMRouter()

    async def handle_message(self, user_id: int, session_id: str, message: str) -> AgentChatResponse:
        started_at = time.perf_counter()
        history = await self.context_manager.get_history(session_id)
        decision = await self._route_message(user_id=user_id, message=message, history=history)
        route, tool_name, arguments = decision.route, decision.tool_name, decision.arguments
        logger.info(
            "agent_message_routed session_id=%s user_id=%s route=%s tool_name=%s routing_source=%s confidence=%s message_len=%s",
            session_id,
            user_id,
            route,
            tool_name or "",
            decision.source,
            decision.confidence,
            len(message),
        )
        tool_calls: list[dict[str, Any]] = []
        tool_result: dict[str, Any] | None = None

        if tool_name is not None:
            tool_result = await self.mcp_client.call_tool(tool_name, arguments)
            tool_calls.append(
                {
                    "name": tool_name,
                    "arguments": arguments,
                    "result": tool_result,
                    "routing_source": decision.source,
                    "confidence": decision.confidence,
                }
            )

        if tool_name is None and decision.answer:
            answer = decision.answer
        else:
            answer = self.response_generator.generate(route=route, message=message, tool_result=tool_result)
        await self.context_manager.append(session_id, role="user", content=message)
        await self.context_manager.append(session_id, role="assistant", content=answer)
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            "agent_message_completed session_id=%s user_id=%s route=%s tool_name=%s routing_source=%s tool_args_keys=%s duration_ms=%s",
            session_id,
            user_id,
            route,
            tool_name or "",
            decision.source,
            sorted(arguments.keys()),
            duration_ms,
        )
        return AgentChatResponse(
            answer=answer,
            session_id=session_id,
            route=route,
            tool_calls=tool_calls,
            context=await self.context_manager.get_history(session_id),
        )

    async def _route_message(
        self,
        *,
        user_id: int,
        message: str,
        history: list[dict[str, str]],
    ) -> RoutingDecision:
        if settings.support_llm_routing_enabled:
            try:
                decision = await self.llm_router.route(user_id=user_id, message=message, history=history)
                if decision.tool_name is not None and not decision.arguments:
                    raise ValueError(f"LLM 工具参数无效: {decision.tool_name}")
                return decision
            except Exception as exc:
                logger.exception(
                    "agent_llm_routing_failed user_id=%s message_len=%s error=%s",
                    user_id,
                    len(message),
                    exc.__class__.__name__,
                )

        route, tool_name, arguments = self._select_tool(user_id=user_id, message=message, history=history)
        return RoutingDecision(route=route, tool_name=tool_name, arguments=arguments, source="fallback_rules")

    def _select_tool(
        self,
        *,
        user_id: int,
        message: str,
        history: list[dict[str, str]],
    ) -> tuple[str, str | None, dict[str, Any]]:
        text = message.strip()
        order_id = self._extract_order_id(text) or self._extract_recent_entity(history, "order_id")
        refund_id = self._extract_refund_id(text)
        product_id = self._extract_product_id(text)
        user_args = {"user_id": user_id, "user_role": "buyer"}

        if refund_id is not None or any(keyword in text for keyword in ("退款进度", "退款单", "退款状态")):
            if refund_id is not None:
                return "refund_query", "get_refund_status", {**user_args, "refund_id": refund_id}
            return "refund_query", "search_after_sale_policy", {"query": text, "top_k": settings.support_retrieval_top_k}

        if order_id is not None or any(keyword in text for keyword in ("订单", "物流", "快递", "发货", "到哪")):
            if order_id is not None:
                return "order_query", "get_order_detail", {**user_args, "order_id": order_id}
            return "order_query", "list_user_orders", {**user_args, "limit": 5}

        if any(keyword in text for keyword in ("退货", "换货", "售后", "政策", "规则", "发票", "保修")):
            return "policy_query", "search_after_sale_policy", {"query": text, "top_k": settings.support_retrieval_top_k}

        if product_id is not None:
            return "product_inquiry", "get_product_detail", {"product_id": product_id}
        if any(keyword in text for keyword in ("商品", "价格", "库存", "怎么样", "推荐")):
            return "product_inquiry", "search_products", {"keyword": text, "limit": 5}

        return "chitchat", None, {}

    @staticmethod
    def _extract_order_id(text: str) -> str | None:
        match = re.search(r"\bSO\d{8,}\b", text, flags=re.IGNORECASE)
        if match:
            return match.group(0).upper()
        match = re.search(r"(?:订单|order)\s*#?(\d{1,18})", text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _extract_refund_id(text: str) -> int | None:
        match = re.search(r"(?:退款单|退款)\s*#?(\d{1,18})", text)
        return int(match.group(1)) if match else None

    @staticmethod
    def _extract_product_id(text: str) -> int | None:
        match = re.search(r"(?:商品|product)\s*#?(\d{1,18})", text, flags=re.IGNORECASE)
        return int(match.group(1)) if match else None

    @staticmethod
    def _extract_recent_entity(history: list[dict[str, str]], key: str) -> str | None:
        if key != "order_id":
            return None
        for item in reversed(history):
            value = AgentService._extract_order_id(item.get("content", ""))
            if value:
                return value
        return None
