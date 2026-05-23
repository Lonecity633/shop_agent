from __future__ import annotations

import json
import time
from typing import Any

from app.agent.llm_client import LLMClient
from app.agent.llm_router import select_prompt_history
from app.agent.prompt_assembler import PromptAssembler
from app.shared.logging import get_logger

logger = get_logger(__name__)


class ResponseGenerator:
    def __init__(self, *, llm_client: LLMClient | None = None, prompt_assembler: PromptAssembler | None = None) -> None:
        self.llm_client = llm_client or LLMClient()
        self.prompt_assembler = prompt_assembler or PromptAssembler()

    async def generate(
        self,
        *,
        route: str,
        message: str,
        tool_result: dict[str, Any] | None,
        history: list[dict[str, str]] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> str:
        started_at = time.perf_counter()
        prompt_history = select_prompt_history(history or [])
        logger.info(
            "agent_response_llm_generate_started route=%s has_tool_result=%s tool_calls_count=%s message_len=%s input_history_count=%s prompt_history_count=%s has_memory=%s",
            route,
            tool_result is not None,
            len(tool_calls or []),
            len(message),
            len(history or []),
            len(prompt_history),
            any(item.get("role") == "memory" for item in prompt_history),
        )
        try:
            answer = await self.llm_client.chat_messages(
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {
                        "role": "user",
                        "content": self._user_prompt(
                            route=route,
                            message=message,
                            tool_result=tool_result,
                            history=prompt_history,
                            tool_calls=tool_calls or [],
                        ),
                    },
                ]
            )
            if not answer.strip():
                raise RuntimeError("LLM final answer is empty")
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.info(
                "agent_response_llm_generate_completed route=%s has_tool_result=%s duration_ms=%s answer_len=%s",
                route,
                tool_result is not None,
                duration_ms,
                len(answer),
            )
            return answer.strip()
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.exception(
                "agent_response_llm_generate_failed route=%s has_tool_result=%s duration_ms=%s error=%s",
                route,
                tool_result is not None,
                duration_ms,
                exc.__class__.__name__,
            )
            return self._fallback_answer(route=route, tool_result=tool_result)

    def _system_prompt(self) -> str:
        return self.prompt_assembler.response_system_prompt()

    @staticmethod
    def _user_prompt(
        *,
        route: str,
        message: str,
        tool_result: dict[str, Any] | None,
        history: list[dict[str, str]],
        tool_calls: list[dict[str, Any]],
    ) -> str:
        prompt_history = select_prompt_history(history)
        return PromptAssembler.response_user_prompt(
            route=route,
            message=message,
            tool_result=tool_result,
            history=prompt_history,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _fallback_answer(*, route: str, tool_result: dict[str, Any] | None) -> str:
        if tool_result is not None and tool_result.get("success") is False:
            return "查询服务暂时不可用，请稍后再试，或转人工客服继续处理。"

        data = (tool_result or {}).get("data")
        if route == "order_query":
            if isinstance(data, list):
                if not data:
                    return "暂时没有查到你的订单记录。"
                return "我已查到你的订单记录，但智能客服回复生成暂时不可用，请稍后再试或转人工确认详情。"
            if isinstance(data, dict) and data.get("found", True):
                return "我已查到这笔订单，但智能客服回复生成暂时不可用，请稍后再试或转人工确认详情。"
            return "暂时没有查到这笔订单，请确认订单号是否正确。"

        if route == "product_inquiry":
            items = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
            if not items:
                return "暂时没有找到匹配商品，可以换个关键词再问我。"
            return "我已查到相关商品，但智能客服回复生成暂时不可用，请稍后再试或转人工确认详情。"

        if route == "policy_query":
            if not data:
                return "暂时没有检索到相关售后政策，我建议联系人工客服进一步确认。"
            return "我已检索到相关政策，但智能客服回复生成暂时不可用，请稍后再试或转人工确认详情。"

        if route == "refund_query":
            if not isinstance(data, dict):
                return "暂时没有查到这条退款记录，请确认退款单号是否正确。"
            return "我已查到退款记录，但智能客服回复生成暂时不可用，请稍后再试或转人工确认详情。"

        if route == "payment_query":
            if not isinstance(data, (dict, list)):
                return "暂时没有查到支付记录，请确认订单号或支付流水号是否正确。"
            return "我已查到支付记录，但智能客服回复生成暂时不可用，请稍后再试或转人工确认详情。"

        if route == "support_ticket":
            if isinstance(data, dict) and data.get("ticket_id"):
                return f"已为你创建人工客服工单，工单号 {data.get('ticket_id')}，客服会尽快处理。"
            return "我建议转人工客服继续处理这个问题。"

        return "我可以帮你查询订单、商品、退款和售后政策。请把订单号、商品关键词或问题发给我。"


def _compact_json(value: Any) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        return "{}"
    return text[:6000]
