from __future__ import annotations

import re
import time
import uuid
from typing import Any

from app.agent.clients.mcp_client import McpClient
from app.agent.context_manager import ContextManager
from app.agent.loop import SupportAgentLoop
from app.agent.llm_router import LLMRouter, RoutingDecision
from app.agent.memory_store import JsonFileMemoryStore
from app.agent.prompt_assembler import PromptAssembler
from app.agent.response_generator import ResponseGenerator
from app.agent.session_lane import SessionLaneManager
from app.agent.tools.registry import ToolRegistry
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
        tool_registry: ToolRegistry | None = None,
        support_loop: SupportAgentLoop | None = None,
        prompt_assembler: PromptAssembler | None = None,
        lane_manager: SessionLaneManager | None = None,
    ) -> None:
        self.prompt_assembler = prompt_assembler or PromptAssembler()
        self.mcp_client = mcp_client or McpClient()
        if context_manager is None and settings.support_memory_persist_path:
            context_manager = ContextManager(memory_store=JsonFileMemoryStore(settings.support_memory_persist_path))
        self.context_manager = context_manager or ContextManager()
        self.response_generator = response_generator or ResponseGenerator(prompt_assembler=self.prompt_assembler)
        self.tool_registry = tool_registry or ToolRegistry(self.mcp_client)
        self.llm_router = llm_router or LLMRouter(tool_registry=self.tool_registry, prompt_assembler=self.prompt_assembler)
        if getattr(self.llm_router, "tool_registry", None) is None:
            self.llm_router.tool_registry = self.tool_registry
        if getattr(self.llm_router, "prompt_assembler", None) is None:
            self.llm_router.prompt_assembler = self.prompt_assembler
        self.support_loop = support_loop or SupportAgentLoop(
            llm_router=self.llm_router,
            mcp_client=self.mcp_client,
            response_generator=self.response_generator,
            fallback_router=self._fallback_route_message,
        )
        self.lane_manager = lane_manager or SessionLaneManager()

    async def handle_message(self, user_id: int, session_id: str, message: str) -> AgentChatResponse:
        async with self.lane_manager.lane(user_id, session_id):
            return await self._handle_message_unlocked(user_id, session_id, message)

    async def _handle_message_unlocked(self, user_id: int, session_id: str, message: str) -> AgentChatResponse:
        started_at = time.perf_counter()
        trace_id = uuid.uuid4().hex
        history = await self.context_manager.get_history(user_id, session_id)
        logger.info(
            "agent_memory_before_route user_id=%s session_id=%s history_count=%s has_memory=%s roles=%s",
            user_id,
            session_id,
            len(history),
            any(item.get("role") == "memory" for item in history),
            [item.get("role", "") for item in history],
        )
        await self.tool_registry.load_tools()

        if settings.agent_loop_enabled:
            loop_result = await self.support_loop.run(user_id=user_id, session_id=session_id, message=message, history=history)
            route = loop_result.route
            tool_name = loop_result.tool_calls[-1]["name"] if loop_result.tool_calls else None
            arguments = loop_result.tool_calls[-1]["arguments"] if loop_result.tool_calls else {}
            tool_calls = loop_result.tool_calls
            answer = loop_result.answer
            routing_source = loop_result.tool_calls[-1]["routing_source"] if loop_result.tool_calls else "agent_loop"
            fallback_reason = _fallback_reason(tool_calls)
        else:
            decision = await self._route_message(user_id=user_id, message=message, history=history)
            route, tool_name, arguments = decision.route, decision.tool_name, decision.arguments
            routing_source = decision.source
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
            tool_calls = []
            tool_result: dict[str, Any] | None = None

            if tool_name is not None:
                tool_result = await self.mcp_client.call_tool(tool_name, arguments)
                tool_calls.append(
                    {
                        "name": tool_name,
                        "arguments": arguments,
                        "result": tool_result,
                        "step": 1,
                        "routing_source": decision.source,
                        "confidence": decision.confidence,
                        "error_type": _tool_error_type(tool_result),
                    }
                )

            if tool_name is None and decision.answer:
                answer = decision.answer
            else:
                answer = await self.response_generator.generate(
                    route=route,
                    message=message,
                    tool_result=tool_result,
                    history=history,
                    tool_calls=tool_calls,
                )
            fallback_reason = _fallback_reason(tool_calls)

        await self.context_manager.append(user_id, session_id, role="user", content=message)
        await self.context_manager.append(user_id, session_id, role="assistant", content=answer)
        await self.context_manager.compact_if_needed(
            user_id,
            session_id,
            self._summarize_memory,
            tool_calls=tool_calls,
            route=route,
        )
        final_history = await self.context_manager.get_history(user_id, session_id)
        logger.info(
            "agent_memory_after_compaction user_id=%s session_id=%s history_count=%s has_memory=%s roles=%s route=%s tool_calls_count=%s",
            user_id,
            session_id,
            len(final_history),
            any(item.get("role") == "memory" for item in final_history),
            [item.get("role", "") for item in final_history],
            route,
            len(tool_calls),
        )
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        ticket_id = _extract_ticket_id(tool_calls)
        for call in tool_calls:
            if isinstance(call, dict):
                call.setdefault("trace_id", trace_id)
        logger.info(
            "agent_message_completed trace_id=%s session_id=%s user_id=%s route=%s tool_name=%s routing_source=%s tool_args_keys=%s duration_ms=%s fallback_reason=%s ticket_id=%s",
            trace_id,
            session_id,
            user_id,
            route,
            tool_name or "",
            routing_source,
            sorted(arguments.keys()),
            duration_ms,
            fallback_reason,
            ticket_id,
        )
        return AgentChatResponse(
            answer=answer,
            session_id=session_id,
            route=route,
            tool_calls=tool_calls,
            context=final_history,
            trace_id=trace_id,
            routing_source=routing_source,
            latency_ms=duration_ms,
            fallback_reason=fallback_reason,
            ticket_id=ticket_id,
        )

    async def _summarize_memory(
        self,
        previous_summary: str,
        messages: list[dict[str, str]],
        entities: dict[str, Any],
    ) -> str:
        messages_text = "\n".join(f"{item.get('role', '')}: {item.get('content', '')}" for item in messages)
        entity_text = ", ".join(f"{key}={value}" for key, value in sorted(entities.items())) or "无"
        prompt = self.prompt_assembler.memory_summary_prompt(
            previous_summary=previous_summary,
            messages_text=messages_text,
            entity_text=entity_text,
        )
        return await self.response_generator.llm_client.chat_messages(
            messages=[
                {"role": "system", "content": "你是客服会话短期记忆压缩器，只输出摘要正文。"},
                {"role": "user", "content": prompt},
            ]
        )

    async def _fallback_route_message(self, user_id: int, message: str, history: list[dict[str, str]]) -> RoutingDecision:
        route, tool_name, arguments = self._select_tool(user_id=user_id, message=message, history=history)
        return RoutingDecision(route=route, tool_name=tool_name, arguments=arguments, source="fallback_rules")

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

        return await self._fallback_route_message(user_id, message, history)

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
        payment_no = self._extract_payment_no(text)
        user_args = {"user_id": user_id, "user_role": "buyer"}

        if refund_id is not None or any(keyword in text for keyword in ("退款进度", "退款单", "退款状态")):
            if refund_id is not None:
                return "refund_query", self._tool_name("get_refund_status"), {**user_args, "refund_id": refund_id}
            tool_name = self._tool_name("search_after_sale_policy")
            return "refund_query", tool_name, self._policy_arguments(tool_name, text)

        if any(keyword in text for keyword in ("支付", "付款", "扣款", "支付状态", "支付失败", "支付流水")):
            if order_id or payment_no:
                arguments = {**user_args}
                if order_id:
                    arguments["order_id"] = order_id
                if payment_no:
                    arguments["payment_no"] = payment_no
                return "payment_query", self._tool_name("get_payment_status"), arguments
            return "payment_query", None, {}

        if any(keyword in text for keyword in ("人工", "客服", "投诉", "升级处理", "工单")):
            if any(keyword in text for keyword in ("工单进度", "我的工单", "工单状态")):
                return "support_ticket", self._tool_name("list_support_tickets"), {**user_args, "limit": 5}
            return "support_ticket", self._tool_name("create_support_ticket"), {
                **user_args,
                "title": text[:80] or "人工客服工单",
                "content": text,
                "category": "complaint" if "投诉" in text else "other",
                "priority": "high" if "投诉" in text else "normal",
                "source": "agent",
                "trigger_reason": text[:200],
            }

        if order_id is not None or any(keyword in text for keyword in ("订单", "物流", "快递", "发货", "到哪")):
            if order_id is not None:
                return "order_query", self._tool_name("get_order_detail"), {**user_args, "order_id": order_id}
            return "order_query", self._tool_name("list_user_orders"), {**user_args, "limit": 5}

        if any(keyword in text for keyword in ("退货", "换货", "售后", "政策", "规则", "发票", "保修")):
            tool_name = self._tool_name("search_after_sale_policy")
            return "policy_query", tool_name, self._policy_arguments(tool_name, text)

        if product_id is not None:
            return "product_inquiry", self._tool_name("get_product_detail"), {"product_id": product_id}
        if any(keyword in text for keyword in ("商品", "价格", "库存", "怎么样", "推荐")):
            return "product_inquiry", self._tool_name("search_products"), {"keyword": text, "limit": 5}

        return "chitchat", None, {}

    def _tool_name(self, canonical_name: str) -> str | None:
        return self.tool_registry.resolve_tool_name(canonical_name)

    @staticmethod
    def _policy_arguments(tool_name: str | None, text: str) -> dict[str, Any]:
        if tool_name == "query_policy_kb":
            return {"question": text, "top_k": settings.support_retrieval_top_k}
        return {"query": text, "top_k": settings.support_retrieval_top_k}

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
    def _extract_payment_no(text: str) -> str | None:
        match = re.search(r"(?:支付流水|payment)\s*#?([A-Za-z0-9_-]{4,64})", text, flags=re.IGNORECASE)
        return match.group(1) if match else None

    @staticmethod
    def _extract_recent_entity(history: list[dict[str, str]], key: str) -> str | None:
        if key != "order_id":
            return None
        for item in reversed(history):
            content = item.get("content", "")
            if item.get("role") == "memory":
                value = AgentService._extract_memory_entity(content, key)
                if value:
                    return value
            value = AgentService._extract_order_id(content)
            if value:
                return value
        return None

    @staticmethod
    def _extract_memory_entity(content: str, key: str) -> str | None:
        match = re.search(rf'"{re.escape(key)}"\s*:\s*"?(?P<value>SO\d{{8,}}|\d{{1,18}})"?', content, flags=re.IGNORECASE)
        if match:
            value = match.group("value")
            return value.upper() if value.upper().startswith("SO") else value
        match = re.search(rf"{re.escape(key)}\s*=\s*(?P<value>SO\d{{8,}}|\d{{1,18}})", content, flags=re.IGNORECASE)
        if match:
            value = match.group("value")
            return value.upper() if value.upper().startswith("SO") else value
        return None


def _tool_error_type(tool_result: dict[str, Any] | None) -> str:
    if not isinstance(tool_result, dict) or tool_result.get("success", True):
        return ""
    return str(tool_result.get("error") or "ToolFailed")


def _fallback_reason(tool_calls: list[dict[str, Any]]) -> str:
    for item in reversed(tool_calls):
        error_type = item.get("error_type") or _tool_error_type(item.get("result"))
        if error_type:
            return str(error_type)
    return ""


def _extract_ticket_id(tool_calls: list[dict[str, Any]]) -> int | None:
    for item in reversed(tool_calls):
        result = item.get("result") if isinstance(item, dict) else None
        data = result.get("data") if isinstance(result, dict) else None
        if isinstance(data, dict):
            value = data.get("ticket_id") or data.get("id")
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    return None
