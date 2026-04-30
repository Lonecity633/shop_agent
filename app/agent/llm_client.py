from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings


@dataclass
class LLMToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class LLMChatResult:
    content: str
    tool_calls: list[LLMToolCall]


class LLMClient:
    async def chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMChatResult:
        if not settings.llm_api_key.strip():
            raise RuntimeError("LLM_API_KEY 未配置")
        if not messages:
            raise RuntimeError("LLM messages 不能为空")

        base_url = settings.llm_base_url.rstrip("/")
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.llm_model,
            "temperature": settings.llm_temperature,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        timeout = max(5, int(settings.llm_timeout_seconds))
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise TimeoutError("LLM 请求超时") from exc

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("LLM 返回为空")
        message = choices[0].get("message") or {}
        text = self._extract_message_content(message.get("content"))

        raw_tool_calls = message.get("tool_calls") or []
        tool_calls: list[LLMToolCall] = []
        if isinstance(raw_tool_calls, list):
            for item in raw_tool_calls:
                if not isinstance(item, dict):
                    continue
                fn = item.get("function") or {}
                if not isinstance(fn, dict):
                    continue
                name = str(fn.get("name") or "").strip()
                call_id = str(item.get("id") or "").strip()
                arguments = fn.get("arguments")
                if isinstance(arguments, dict):
                    arguments = json.dumps(arguments, ensure_ascii=False)
                if not isinstance(arguments, str):
                    arguments = "{}"
                if name and call_id:
                    tool_calls.append(LLMToolCall(id=call_id, name=name, arguments=arguments))

        if not text and not tool_calls:
            raise RuntimeError("LLM 返回内容缺失")
        return LLMChatResult(content=text, tool_calls=tool_calls)

    async def chat_messages(self, *, messages: list[dict[str, str]]) -> str:
        result = await self.chat_completion(messages=messages)
        if result.content:
            return result.content
        raise RuntimeError("LLM 返回内容缺失")

    async def chat(self, *, system_prompt: str, user_prompt: str) -> str:
        return await self.chat_messages(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )

    @staticmethod
    def _extract_message_content(content: Any) -> str:
        if isinstance(content, list):
            parts = [item.get("text", "") for item in content if isinstance(item, dict)]
            return "".join(parts).strip()
        if isinstance(content, str):
            return content.strip()
        return ""
