from __future__ import annotations

import time
from typing import Any

import httpx

from app.backend.core.config import settings
from app.shared.logging import get_logger

logger = get_logger(__name__)


class AgentAPIClientError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class AgentAPIClient:
    def __init__(self, *, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.agent_base_url).rstrip("/")

    async def chat(self, *, user_id: int, session_id: str, message: str) -> dict[str, Any]:
        started_at = time.perf_counter()
        url = f"{self.base_url}/agent/chat"
        payload = {"user_id": user_id, "session_id": session_id, "message": message}
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(url, json=payload)
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.info(
                "agent_chat_http_completed user_id=%s session_id=%s status_code=%s duration_ms=%s",
                user_id,
                session_id,
                response.status_code,
                duration_ms,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.exception(
                "agent_chat_http_status_error user_id=%s session_id=%s status_code=%s duration_ms=%s",
                user_id,
                session_id,
                exc.response.status_code,
                duration_ms,
            )
            raise AgentAPIClientError("智能客服服务返回异常", status_code=exc.response.status_code) from exc
        except (httpx.HTTPError, ValueError) as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.exception(
                "agent_chat_http_failed user_id=%s session_id=%s duration_ms=%s error=%s",
                user_id,
                session_id,
                duration_ms,
                exc.__class__.__name__,
            )
            raise AgentAPIClientError("智能客服服务暂不可用") from exc
        if not isinstance(data, dict):
            raise AgentAPIClientError("智能客服服务返回格式异常")
        return data
