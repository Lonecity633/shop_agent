from __future__ import annotations

import inspect
import json
import re
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.shared.config import settings
from app.shared.logging import get_logger

logger = get_logger(__name__)

MemorySummarizer = Callable[[str, list[dict[str, str]], dict[str, Any]], str | Awaitable[str]]


@dataclass
class MemoryState:
    summary: str = ""
    recent_messages: list[dict[str, str]] = field(default_factory=list)
    entities: dict[str, Any] = field(default_factory=dict)
    last_route: str | None = None
    last_tool_calls: list[dict[str, Any]] = field(default_factory=list)


class ContextManager:
    def __init__(
        self,
        *,
        recent_messages: int | None = None,
        summary_trigger_messages: int | None = None,
        summary_max_chars: int | None = None,
        max_messages: int | None = None,
        memory_store: Any | None = None,
    ) -> None:
        # max_messages is accepted for compatibility with older tests/callers.
        if recent_messages is None and max_messages is not None:
            recent_messages = max_messages
        self.recent_messages = max(1, int(recent_messages or settings.support_memory_recent_messages))
        self.summary_trigger_messages = max(
            self.recent_messages + 1,
            int(summary_trigger_messages or settings.support_memory_summary_trigger_messages),
        )
        self.summary_max_chars = max(100, int(summary_max_chars or settings.support_memory_summary_max_chars))
        self._store: dict[tuple[int, str], MemoryState] = defaultdict(MemoryState)
        self.memory_store = memory_store

    async def get_history(self, user_id: int, session_id: str) -> list[dict[str, str]]:
        state = await self._state(user_id, session_id)
        history: list[dict[str, str]] = []
        memory_message = self._memory_message(state)
        if memory_message is not None:
            history.append(memory_message)
        history.extend(list(state.recent_messages))
        logger.info(
            "context_memory_history_loaded user_id=%s session_id=%s has_memory=%s recent_count=%s summary_len=%s entity_keys=%s history_count=%s",
            user_id,
            session_id,
            memory_message is not None,
            len(state.recent_messages),
            len(state.summary),
            sorted(state.entities),
            len(history),
        )
        return history

    async def append(self, user_id: int, session_id: str, *, role: str, content: str) -> None:
        state = await self._state(user_id, session_id)
        state.recent_messages.append({"role": str(role), "content": str(content)})
        await self._persist(user_id, session_id, state)
        logger.info(
            "context_memory_message_appended user_id=%s session_id=%s role=%s content_len=%s recent_count=%s",
            user_id,
            session_id,
            role,
            len(content),
            len(state.recent_messages),
        )

    async def compact_if_needed(
        self,
        user_id: int,
        session_id: str,
        summarizer: MemorySummarizer,
        tool_calls: list[dict[str, Any]] | None = None,
        route: str | None = None,
    ) -> None:
        state = await self._state(user_id, session_id)
        self._update_entities_from_messages(state)
        self._update_entities_from_tool_calls(state, tool_calls or [])
        if route:
            state.entities["last_route"] = route
            state.last_route = route
        state.last_tool_calls = [
            {
                "name": item.get("name"),
                "arguments": item.get("arguments"),
                "step": item.get("step"),
                "routing_source": item.get("routing_source"),
                "error_type": item.get("error_type"),
            }
            for item in (tool_calls or [])[-3:]
            if isinstance(item, dict)
        ]

        if len(state.recent_messages) <= self.summary_trigger_messages:
            await self._persist(user_id, session_id, state)
            logger.info(
                "context_memory_compaction_skipped user_id=%s session_id=%s recent_count=%s trigger=%s entity_keys=%s",
                user_id,
                session_id,
                len(state.recent_messages),
                self.summary_trigger_messages,
                sorted(state.entities),
            )
            return

        messages_to_summarize = state.recent_messages[: -self.recent_messages]
        old_count = len(state.recent_messages)
        if messages_to_summarize:
            try:
                summary = summarizer(state.summary, messages_to_summarize, dict(state.entities))
                if inspect.isawaitable(summary):
                    summary = await summary
                if summary is not None and str(summary).strip():
                    state.summary = str(summary).strip()[: self.summary_max_chars]
            except Exception as exc:
                logger.exception(
                    "context_memory_summary_failed user_id=%s session_id=%s messages_count=%s error=%s",
                    user_id,
                    session_id,
                    len(messages_to_summarize),
                    exc.__class__.__name__,
                )

        state.recent_messages = state.recent_messages[-self.recent_messages :]
        await self._persist(user_id, session_id, state)
        logger.info(
            "context_memory_compaction_completed user_id=%s session_id=%s old_recent_count=%s summarized_count=%s kept_recent_count=%s summary_len=%s entity_keys=%s",
            user_id,
            session_id,
            old_count,
            len(messages_to_summarize),
            len(state.recent_messages),
            len(state.summary),
            sorted(state.entities),
        )

    def get_state(self, user_id: int, session_id: str) -> MemoryState:
        return self._store[self._key(user_id, session_id)]

    async def _state(self, user_id: int, session_id: str) -> MemoryState:
        key = self._key(user_id, session_id)
        if key in self._store:
            return self._store[key]
        if self.memory_store is not None:
            loaded = await self.memory_store.load(user_id, session_id)
            if loaded is not None:
                self._store[key] = loaded
                return loaded
        state = self._store[key]
        return state

    async def _persist(self, user_id: int, session_id: str, state: MemoryState) -> None:
        if self.memory_store is not None:
            await self.memory_store.save(user_id, session_id, state)

    @staticmethod
    def _key(user_id: int, session_id: str) -> tuple[int, str]:
        return int(user_id), str(session_id)

    @staticmethod
    def _memory_message(state: MemoryState) -> dict[str, str] | None:
        parts = []
        if state.summary:
            parts.append(f"会话摘要：{state.summary}")
        if state.entities:
            parts.append(f"关键实体：{_compact_json(state.entities)}")
        if not parts:
            return None
        return {"role": "memory", "content": "\n".join(parts)}

    @staticmethod
    def _update_entities_from_messages(state: MemoryState) -> None:
        for item in state.recent_messages:
            content = item.get("content", "")
            order_id = _extract_order_id(content)
            if order_id:
                state.entities["order_id"] = order_id
            refund_id = _extract_int_entity(content, r"(?:退款单|退款)\s*#?(\d{1,18})")
            if refund_id is not None:
                state.entities["refund_id"] = refund_id
            product_id = _extract_int_entity(content, r"(?:商品|product)\s*#?(\d{1,18})", flags=re.IGNORECASE)
            if product_id is not None:
                state.entities["product_id"] = product_id

    @staticmethod
    def _update_entities_from_tool_calls(state: MemoryState, tool_calls: list[dict[str, Any]]) -> None:
        for item in tool_calls:
            if not isinstance(item, dict):
                continue
            arguments = item.get("arguments")
            if not isinstance(arguments, dict):
                continue
            for key in ("order_id", "product_id", "refund_id"):
                value = arguments.get(key)
                if value not in (None, ""):
                    state.entities[key] = value


def _extract_order_id(text: str) -> str | None:
    match = re.search(r"\bSO\d{8,}\b", text, flags=re.IGNORECASE)
    if match:
        return match.group(0).upper()
    match = re.search(r"(?:订单|order)\s*#?(\d{1,18})", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _extract_int_entity(text: str, pattern: str, flags: int = 0) -> int | None:
    match = re.search(pattern, text, flags=flags)
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _compact_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        return "{}"
