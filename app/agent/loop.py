from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.agent.clients.mcp_client import McpClient
from app.agent.llm_router import LLMRouter, RoutingDecision
from app.agent.response_generator import ResponseGenerator
from app.shared.config import settings
from app.shared.logging import get_logger

logger = get_logger(__name__)

FallbackRouter = Callable[[int, str, list[dict[str, str]]], Awaitable[RoutingDecision]]


@dataclass
class AgentLoopResult:
    answer: str
    route: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class SupportAgentLoop:
    def __init__(
        self,
        *,
        llm_router: LLMRouter,
        mcp_client: McpClient,
        response_generator: ResponseGenerator,
        fallback_router: FallbackRouter | None = None,
    ) -> None:
        self.llm_router = llm_router
        self.mcp_client = mcp_client
        self.response_generator = response_generator
        self.fallback_router = fallback_router

    async def run(
        self,
        *,
        user_id: int,
        session_id: str,
        message: str,
        history: list[dict[str, str]],
    ) -> AgentLoopResult:
        max_steps = max(1, int(settings.agent_loop_max_steps))
        working_history = list(history)
        tool_calls: list[dict[str, Any]] = []
        last_decision: RoutingDecision | None = None
        last_tool_result: dict[str, Any] | None = None

        for step in range(1, max_steps + 1):
            decision = await self._route(
                user_id=user_id,
                message=message,
                history=working_history,
            )
            last_decision = decision
            logger.info(
                "support_agent_loop_step session_id=%s user_id=%s step=%s route=%s tool_name=%s routing_source=%s confidence=%s",
                session_id,
                user_id,
                step,
                decision.route,
                decision.tool_name or "",
                decision.source,
                decision.confidence,
            )

            if decision.tool_name is None:
                if decision.answer and last_tool_result is None:
                    answer = decision.answer
                else:
                    answer = await self.response_generator.generate(
                        route=decision.route,
                        message=message,
                        tool_result=last_tool_result,
                        history=working_history,
                        tool_calls=tool_calls,
                    )
                return AgentLoopResult(answer=answer, route=decision.route, tool_calls=tool_calls)

            tool_result = await self._call_tool(decision.tool_name, decision.arguments)
            last_tool_result = tool_result
            tool_calls.append(
                {
                    "name": decision.tool_name,
                    "arguments": decision.arguments,
                    "result": tool_result,
                    "step": step,
                    "confidence": decision.confidence,
                    "routing_source": decision.source,
                    "error_type": self._tool_error_type(tool_result),
                }
            )
            working_history.append(
                {
                    "role": "tool",
                    "content": self._tool_history_message(
                        step=step,
                        tool_name=decision.tool_name,
                        arguments=decision.arguments,
                        result=tool_result,
                    ),
                }
            )
            if decision.source == "fallback_rules":
                answer = await self.response_generator.generate(
                    route=decision.route,
                    message=message,
                    tool_result=tool_result,
                    history=working_history,
                    tool_calls=tool_calls,
                )
                return AgentLoopResult(answer=answer, route=decision.route, tool_calls=tool_calls)

        if last_tool_result is not None and last_decision is not None:
            answer = await self.response_generator.generate(
                route=last_decision.route,
                message=message,
                tool_result=last_tool_result,
                history=working_history,
                tool_calls=tool_calls,
            )
            return AgentLoopResult(answer=answer, route=last_decision.route, tool_calls=tool_calls)

        logger.warning("support_agent_loop_exhausted_without_result session_id=%s user_id=%s max_steps=%s", session_id, user_id, max_steps)
        return AgentLoopResult(
            answer="我暂时无法确认这个问题的准确信息，建议转人工客服继续处理。",
            route=last_decision.route if last_decision is not None else "chitchat",
            tool_calls=tool_calls,
        )

    async def _route(self, *, user_id: int, message: str, history: list[dict[str, str]]) -> RoutingDecision:
        if not settings.support_llm_routing_enabled and self.fallback_router is not None:
            return await self.fallback_router(user_id, message, history)
        try:
            return await self.llm_router.route(user_id=user_id, message=message, history=history)
        except Exception as exc:
            logger.exception(
                "support_agent_loop_llm_route_failed user_id=%s message_len=%s error=%s",
                user_id,
                len(message),
                exc.__class__.__name__,
            )
            if self.fallback_router is not None:
                return await self.fallback_router(user_id, message, history)
            return RoutingDecision(route="chitchat", source="fallback_error")

    async def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await self.mcp_client.call_tool(tool_name, arguments)
            if isinstance(result, dict):
                return result
            return {"success": True, "data": result, "error": None}
        except Exception as exc:
            logger.exception("support_agent_loop_tool_call_failed tool=%s error=%s", tool_name, exc.__class__.__name__)
            return {"success": False, "data": None, "error": exc.__class__.__name__}

    @staticmethod
    def _tool_error_type(tool_result: dict[str, Any] | None) -> str:
        if not isinstance(tool_result, dict) or tool_result.get("success", True):
            return ""
        return str(tool_result.get("error") or "ToolFailed")

    @staticmethod
    def _tool_history_message(*, step: int, tool_name: str, arguments: dict[str, Any], result: dict[str, Any]) -> str:
        payload = {
            "step": step,
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
        }
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return text[:4000]
