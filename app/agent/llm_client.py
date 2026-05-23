from __future__ import annotations

import time
from typing import Any

import httpx

from app.shared.config import settings
from app.shared.logging import get_logger


logger = get_logger(__name__)


class LLMClient:
    async def chat_completion(self, *, messages: list[dict[str, Any]]) -> str:
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
        timeout = max(5, int(settings.llm_timeout_seconds))
        started_at = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout, trust_env=settings.llm_trust_env) as client:
                response = await client.post(url, headers=headers, json=payload)
                duration_ms = int((time.perf_counter() - started_at) * 1000)
                logger.info(
                    "llm_chat_completion_completed base_url=%s model=%s status_code=%s duration_ms=%s messages_count=%s",
                    base_url,
                    settings.llm_model,
                    response.status_code,
                    duration_ms,
                    len(messages),
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.exception(
                "llm_chat_completion_timeout base_url=%s model=%s duration_ms=%s",
                base_url,
                settings.llm_model,
                duration_ms,
            )
            raise TimeoutError("LLM 请求超时") from exc
        except httpx.HTTPStatusError as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.exception(
                "llm_chat_completion_status_error base_url=%s model=%s status_code=%s duration_ms=%s",
                base_url,
                settings.llm_model,
                exc.response.status_code,
                duration_ms,
            )
            raise
        except httpx.HTTPError:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.exception(
                "llm_chat_completion_failed base_url=%s model=%s duration_ms=%s",
                base_url,
                settings.llm_model,
                duration_ms,
            )
            raise

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("LLM 返回为空")
        message = choices[0].get("message") or {}
        text = self._extract_message_content(message.get("content"))
        if not text:
            raise RuntimeError("LLM 返回内容缺失")
        return text

    async def chat_messages(self, *, messages: list[dict[str, str]]) -> str:
        return await self.chat_completion(messages=messages)

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
