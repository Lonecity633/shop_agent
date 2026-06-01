from __future__ import annotations

import re
import time
import uuid
from typing import Any

from app.agent.clients.mcp_client import McpClient
from app.agent.context_manager import ContextManager
from app.agent.handoff_policy import SupportHandoffPolicy
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
        handoff_policy: SupportHandoffPolicy | None = None,
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
        self.handoff_policy = handoff_policy or SupportHandoffPolicy()

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

        preemptive_handoff = self._select_handoff_tool(user_id=user_id, message=message, history=history)
        if preemptive_handoff is not None:
            route, tool_name, arguments = preemptive_handoff
            routing_source = "handoff_policy"
            logger.info(
                "agent_message_handoff_preempted session_id=%s user_id=%s route=%s tool_name=%s message_len=%s",
                session_id,
                user_id,
                route,
                tool_name or "",
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
                        "routing_source": routing_source,
                        "confidence": 1.0,
                        "error_type": _tool_error_type(tool_result),
                    }
                )
            answer = await self.response_generator.generate(
                route=route,
                message=message,
                tool_result=tool_result,
                history=history,
                tool_calls=tool_calls,
            )
            fallback_reason = _fallback_reason(tool_calls)
        elif settings.agent_loop_enabled:
            loop_result = await self.support_loop.run(user_id=user_id, session_id=session_id, message=message, history=history)
            route = loop_result.route
            tool_name = loop_result.tool_calls[-1]["name"] if loop_result.tool_calls else None
            arguments = loop_result.tool_calls[-1]["arguments"] if loop_result.tool_calls else {}
            tool_calls = loop_result.tool_calls
            answer = loop_result.answer
            routing_source = loop_result.tool_calls[-1]["routing_source"] if loop_result.tool_calls else "agent_loop"
            fallback_reason = _fallback_reason(tool_calls)
            handoff_call = await self._maybe_create_auto_handoff(
                user_id=user_id,
                message=message,
                route=route,
                history=history,
                tool_calls=tool_calls,
                trace_id=trace_id,
            )
            if handoff_call is not None:
                tool_calls.append(handoff_call)
                route = "support_ticket"
                tool_name = handoff_call["name"]
                arguments = handoff_call["arguments"]
                routing_source = handoff_call["routing_source"]
                fallback_reason = handoff_call["arguments"].get("trigger_reason", fallback_reason)
                answer = await self.response_generator.generate(
                    route=route,
                    message=message,
                    tool_result=handoff_call.get("result"),
                    history=history,
                    tool_calls=tool_calls,
                )
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
            handoff_call = await self._maybe_create_auto_handoff(
                user_id=user_id,
                message=message,
                route=route,
                history=history,
                tool_calls=tool_calls,
                trace_id=trace_id,
            )
            if handoff_call is not None:
                tool_calls.append(handoff_call)
                route = "support_ticket"
                tool_name = handoff_call["name"]
                arguments = handoff_call["arguments"]
                routing_source = handoff_call["routing_source"]
                fallback_reason = handoff_call["arguments"].get("trigger_reason", fallback_reason)
                answer = await self.response_generator.generate(
                    route=route,
                    message=message,
                    tool_result=handoff_call.get("result"),
                    history=history,
                    tool_calls=tool_calls,
                )

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
        support_ticket = _extract_support_ticket(tool_calls)
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
            support_ticket=support_ticket,
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

    async def _maybe_create_auto_handoff(
        self,
        *,
        user_id: int,
        message: str,
        route: str,
        history: list[dict[str, str]],
        tool_calls: list[dict[str, Any]],
        trace_id: str,
    ) -> dict[str, Any] | None:
        decision = self.handoff_policy.classify_auto_failure(route=route, message=message, tool_calls=tool_calls)
        if decision is None:
            return None
        tool_name = self._tool_name("create_support_ticket")
        if tool_name is None:
            return None
        arguments = self.handoff_policy.build_ticket_arguments(
            user_id=user_id,
            message=message,
            decision=decision,
            order_id=self._extract_order_id(message) or self._extract_recent_entity(history, "order_id"),
            product_id=self._extract_product_id(message),
            refund_id=self._extract_refund_id(message),
            trace_id=trace_id,
        )
        result = await self.mcp_client.call_tool(tool_name, arguments)
        return {
            "name": tool_name,
            "arguments": arguments,
            "result": result,
            "step": len(tool_calls) + 1,
            "routing_source": "handoff_policy",
            "confidence": 1.0,
            "error_type": _tool_error_type(result),
        }

    async def _route_message(
        self,
        *,
        user_id: int,
        message: str,
        history: list[dict[str, str]],
    ) -> RoutingDecision:
        handoff_route = self._select_handoff_tool(user_id=user_id, message=message, history=history)
        if handoff_route is not None:
            route, tool_name, arguments = handoff_route
            return RoutingDecision(route=route, tool_name=tool_name, arguments=arguments, confidence=1.0, source="handoff_policy")

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
        handoff_route = self._select_handoff_tool(user_id=user_id, message=message, history=history)
        if handoff_route is not None:
            return handoff_route

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

    def _select_handoff_tool(
        self,
        *,
        user_id: int,
        message: str,
        history: list[dict[str, str]],
    ) -> tuple[str, str | None, dict[str, Any]] | None:
        text = message.strip()
        user_args = {"user_id": user_id, "user_role": "buyer"}
        order_id = self._extract_order_id(text) or self._extract_recent_entity(history, "order_id")
        refund_id = self._extract_refund_id(text)
        product_id = self._extract_product_id(text)
        entities = {
            key: value
            for key, value in {"order_id": order_id, "product_id": product_id, "refund_id": refund_id}.items()
            if value not in (None, "")
        }
        if self.handoff_policy.is_ticket_query(text):
            return "support_ticket", self._tool_name("list_support_tickets"), {**user_args, "limit": 5}

        handoff = self.handoff_policy.classify_initial(message=text, entities=entities)
        if handoff is None:
            return None
        return "support_ticket", self._tool_name("create_support_ticket"), self.handoff_policy.build_ticket_arguments(
            user_id=user_id,
            message=text,
            decision=handoff,
            order_id=order_id,
            product_id=product_id,
            refund_id=refund_id,
        )

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
    ticket = _extract_support_ticket(tool_calls)
    if ticket is None:
        return None
    value = ticket.get("ticket_id")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_support_ticket(tool_calls: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in reversed(tool_calls):
        if not isinstance(item, dict) or item.get("name") != "create_support_ticket":
            continue
        result = item.get("result")
        data = result.get("data") if isinstance(result, dict) else None
        if not isinstance(data, dict):
            continue
        ticket_id = data.get("ticket_id") or data.get("id")
        if ticket_id in (None, ""):
            continue
        arguments = item.get("arguments") if isinstance(item.get("arguments"), dict) else {}
        return {
            "ticket_id": ticket_id,
            "status": data.get("status") or "pending",
            "category": data.get("category") or arguments.get("category") or "",
            "priority": data.get("priority") or arguments.get("priority") or "",
            "assigned_role": data.get("assigned_role") or "",
            "order_id": data.get("order_id") or arguments.get("order_id"),
            "product_id": data.get("product_id") or arguments.get("product_id"),
            "refund_id": data.get("refund_id") or arguments.get("refund_id"),
            "title": data.get("title") or arguments.get("title") or "",
            "trigger_reason": data.get("trigger_reason") or arguments.get("trigger_reason") or "",
        }
    return None
