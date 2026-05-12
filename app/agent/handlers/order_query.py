from __future__ import annotations

import json
from typing import Any

from app.agent.handlers.base import HandlerContext, HandlerResult, IntentHandler
from app.agent.handlers.utils import build_messages, fallback_order_answer, parse_json_object
from app.agent.mcp_client import McpToolClient
from app.agent.prompts import FALLBACKS, ORDER_QUERY
from app.agent.tools.shop_tools import GET_ORDER_DETAILS_TOOL, execute_get_order_details
from app.core.config import settings


class OrderQueryHandler(IntentHandler):
    def __init__(self):
        self.mcp_client = McpToolClient()

    async def handle(self, ctx: HandlerContext) -> HandlerResult:
        messages = build_messages(ORDER_QUERY, ctx.history, ctx.content, allowed_roles={"user", "assistant"})
        try:
            first_pass = await ctx.llm_client.chat_completion(
                messages=messages,
                tools=[GET_ORDER_DETAILS_TOOL],
                tool_choice="auto",
            )
        except TimeoutError:
            return HandlerResult(answer=FALLBACKS["order_timeout"])
        except Exception:
            return HandlerResult(answer=FALLBACKS["order_no_input"])

        if not first_pass.tool_calls:
            if first_pass.content:
                return HandlerResult(answer=first_pass.content)
            return HandlerResult(answer=FALLBACKS["order_no_input"])

        tool_call = next(
            (item for item in first_pass.tool_calls if item.name == "get_order_details"),
            first_pass.tool_calls[0],
        )
        args = parse_json_object(tool_call.arguments)
        raw_order_id = args.get("order_id")
        order_id = str(raw_order_id).strip() if raw_order_id is not None else ""

        tool_name = "get_order_details"
        try:
            mcp_result = await self.mcp_client.call_tool(
                ctx.db,
                current_user=ctx.current_user,
                session_id=ctx.session_id,
                tool_name=tool_name,
                arguments={"order_id": order_id},
            )
            tool_result = mcp_result.get("data") or {}
            tool_source = "mcp"
        except Exception:
            if not settings.mcp_fallback_enabled:
                return HandlerResult(answer=FALLBACKS["order_timeout"])
            tool_result = await execute_get_order_details(ctx.db, current_user=ctx.current_user, order_id=order_id)
            tool_source = "local_fallback"
        tool_payload = json.dumps(tool_result, ensure_ascii=False)
        evidences = [
            {
                "tool": tool_name,
                "source": tool_source,
                "args": {"order_id": order_id},
                "result": tool_result,
            }
        ]

        assistant_tool_message: dict[str, Any] = {
            "role": "assistant",
            "content": first_pass.content or "",
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": "get_order_details",
                        "arguments": tool_call.arguments,
                    },
                }
            ],
        }
        second_pass_messages = [
            *messages,
            assistant_tool_message,
            {"role": "tool", "tool_call_id": tool_call.id, "content": tool_payload},
        ]
        try:
            second_pass = await ctx.llm_client.chat_completion(
                messages=second_pass_messages,
                tools=[GET_ORDER_DETAILS_TOOL],
                tool_choice="none",
            )
            if second_pass.content:
                return HandlerResult(
                    answer=second_pass.content,
                    tool_records=[tool_payload],
                    evidences=evidences,
                )
        except TimeoutError:
            pass
        except Exception:
            pass

        fallback = fallback_order_answer(tool_result)
        return HandlerResult(
            answer=fallback,
            tool_records=[tool_payload],
            evidences=evidences,
        )
