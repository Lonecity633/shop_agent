from __future__ import annotations

import json
from typing import Any

from app.agent.handlers.base import HandlerContext, HandlerResult
from app.agent.handlers.utils import build_messages, parse_json_object
from app.agent.llm_client import LLMToolCall
from app.agent.mcp_client import McpToolClient
from app.agent.mcp_tool_registry import McpToolRegistry
from app.agent.prompts import FALLBACKS, REACT_AGENT
from app.core.config import settings


class ReactSupportAgent:
    def __init__(
        self,
        *,
        mcp_client: McpToolClient | None = None,
        tool_registry: McpToolRegistry | None = None,
    ):
        self.mcp_client = mcp_client or McpToolClient()
        self.tool_registry = tool_registry or McpToolRegistry(client=self.mcp_client)

    async def handle(self, ctx: HandlerContext) -> HandlerResult:
        try:
            tools = await self.tool_registry.openai_tools()
        except Exception:
            return HandlerResult(answer=FALLBACKS["react_fallback"])

        if not tools:
            return HandlerResult(answer=FALLBACKS["react_fallback"])

        allowed_tools = {tool["function"]["name"] for tool in tools}
        messages: list[dict[str, Any]] = build_messages(
            REACT_AGENT,
            ctx.history,
            ctx.content,
            allowed_roles={"system", "user", "assistant"},
        )
        tool_records: list[str] = []
        evidences: list[dict] = []
        resolved_seller_id: int | None = None

        max_steps = max(1, int(settings.support_react_max_steps))
        for _ in range(max_steps):
            try:
                result = await ctx.llm_client.chat_completion(
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                )
            except TimeoutError:
                return HandlerResult(answer=FALLBACKS["react_timeout"], tool_records=tool_records, evidences=evidences)
            except Exception:
                return HandlerResult(answer=FALLBACKS["react_fallback"], tool_records=tool_records, evidences=evidences)

            if not result.tool_calls:
                if result.content:
                    return HandlerResult(
                        answer=result.content,
                        tool_records=tool_records,
                        evidences=evidences,
                        resolved_seller_id=resolved_seller_id,
                    )
                break

            messages.append(self._assistant_tool_call_message(result.content, result.tool_calls))
            for tool_call in result.tool_calls:
                args = parse_json_object(tool_call.arguments)
                observation, evidence = await self._run_tool(
                    ctx,
                    tool_call=tool_call,
                    arguments=args,
                    allowed_tools=allowed_tools,
                )
                resolved_seller_id = resolved_seller_id or self._extract_seller_id(observation)
                record = {
                    "tool": tool_call.name,
                    "args": self._summarize_args(args),
                    "observation": self._summarize_observation(observation),
                }
                tool_records.append(json.dumps(record, ensure_ascii=False))
                evidences.append(evidence)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(observation, ensure_ascii=False),
                    }
                )

        answer = await self._finalize_after_limit(ctx, messages)
        return HandlerResult(
            answer=answer,
            tool_records=tool_records,
            evidences=evidences,
            resolved_seller_id=resolved_seller_id,
        )

    async def _run_tool(
        self,
        ctx: HandlerContext,
        *,
        tool_call: LLMToolCall,
        arguments: dict[str, Any],
        allowed_tools: set[str],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if tool_call.name not in allowed_tools:
            observation = {
                "success": False,
                "error_code": "TOOL_NOT_ALLOWED",
                "message": "该工具不允许在当前客服场景中使用",
            }
            return observation, {"tool": tool_call.name, "source": "react_mcp", "success": False, "error_code": "TOOL_NOT_ALLOWED"}

        try:
            observation = await self.mcp_client.call_tool(
                ctx.db,
                current_user=ctx.current_user,
                session_id=ctx.session_id,
                tool_name=tool_call.name,
                arguments=arguments,
            )
            success = bool(observation.get("success", True))
            return observation, {
                "tool": tool_call.name,
                "source": "react_mcp",
                "success": success,
                "args": self._summarize_args(arguments),
                "result": self._summarize_observation(observation),
            }
        except Exception as exc:
            observation = {
                "success": False,
                "error_code": exc.__class__.__name__,
                "message": "工具调用暂时失败",
            }
            return observation, {
                "tool": tool_call.name,
                "source": "react_mcp",
                "success": False,
                "args": self._summarize_args(arguments),
                "error_code": exc.__class__.__name__,
            }

    async def _finalize_after_limit(self, ctx: HandlerContext, messages: list[dict[str, Any]]) -> str:
        messages = [
            *messages,
            {
                "role": "user",
                "content": "请基于已经获得的工具结果给出最终客服答复；如果信息仍不足，请明确追问缺失信息。",
            },
        ]
        try:
            result = await ctx.llm_client.chat_completion(messages=messages)
            return result.content or FALLBACKS["react_max_steps"]
        except TimeoutError:
            return FALLBACKS["react_timeout"]
        except Exception:
            return FALLBACKS["react_max_steps"]

    @staticmethod
    def _assistant_tool_call_message(content: str, tool_calls: list[LLMToolCall]) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": content or "",
            "tool_calls": [
                {
                    "id": item.id,
                    "type": "function",
                    "function": {
                        "name": item.name,
                        "arguments": item.arguments,
                    },
                }
                for item in tool_calls
            ],
        }

    @staticmethod
    def _summarize_args(arguments: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in arguments.items() if key not in {"internal_secret", "user_id", "user_role"}}

    @classmethod
    def _summarize_observation(cls, observation: dict[str, Any]) -> dict[str, Any]:
        payload = observation.get("data")
        summary: dict[str, Any] = {
            "success": bool(observation.get("success", True)),
        }
        if observation.get("error_code"):
            summary["error_code"] = observation.get("error_code")
        if isinstance(payload, list):
            summary["items"] = len(payload)
            if payload:
                summary["first_item"] = cls._compact_mapping(payload[0])
        elif isinstance(payload, dict):
            summary["data"] = cls._compact_mapping(payload)
        else:
            summary["has_data"] = payload is not None
        return summary

    @staticmethod
    def _compact_mapping(value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        keys = (
            "found",
            "order_id",
            "order_status",
            "pay_status",
            "product_id",
            "name",
            "price",
            "stock",
            "seller_id",
            "document_title",
            "score",
            "ticket_id",
            "assigned_role",
            "assigned_id",
            "category",
            "status",
        )
        return {key: value.get(key) for key in keys if key in value}

    @classmethod
    def _extract_seller_id(cls, observation: dict[str, Any]) -> int | None:
        payload = observation.get("data")
        if isinstance(payload, dict):
            value = payload.get("seller_id")
            return int(value) if isinstance(value, int) else None
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and isinstance(item.get("seller_id"), int):
                    return int(item["seller_id"])
        return None
