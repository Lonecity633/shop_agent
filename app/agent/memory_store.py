from __future__ import annotations

import json
import asyncio
from pathlib import Path
from typing import Protocol

from app.agent.context_manager import MemoryState


class MemoryStore(Protocol):
    async def load(self, user_id: int, session_id: str) -> MemoryState | None:
        ...

    async def save(self, user_id: int, session_id: str, state: MemoryState) -> None:
        ...


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self._store: dict[tuple[int, str], MemoryState] = {}

    async def load(self, user_id: int, session_id: str) -> MemoryState | None:
        state = self._store.get((int(user_id), str(session_id)))
        return _copy_state(state) if state is not None else None

    async def save(self, user_id: int, session_id: str, state: MemoryState) -> None:
        self._store[(int(user_id), str(session_id))] = _copy_state(state)


class JsonFileMemoryStore:
    """Small durable store for the standalone agent service.

    Deployments that already have Redis/MySQL can replace this via the MemoryStore protocol.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = asyncio.Lock()

    async def load(self, user_id: int, session_id: str) -> MemoryState | None:
        data = self._read_all()
        payload = data.get(_key(user_id, session_id))
        if not isinstance(payload, dict):
            return None
        return MemoryState(
            summary=str(payload.get("summary") or ""),
            recent_messages=[
                {"role": str(item.get("role", "")), "content": str(item.get("content", ""))}
                for item in payload.get("recent_messages", [])
                if isinstance(item, dict)
            ],
            entities=payload.get("entities") if isinstance(payload.get("entities"), dict) else {},
            last_route=str(payload.get("last_route") or "") or None,
            last_tool_calls=payload.get("last_tool_calls") if isinstance(payload.get("last_tool_calls"), list) else [],
        )

    async def save(self, user_id: int, session_id: str, state: MemoryState) -> None:
        async with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = self._read_all()
            data[_key(user_id, session_id)] = {
                "summary": state.summary,
                "recent_messages": state.recent_messages,
                "entities": state.entities,
                "last_route": state.last_route,
                "last_tool_calls": state.last_tool_calls[-3:],
            }
            self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_all(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}


def _key(user_id: int, session_id: str) -> str:
    return f"{int(user_id)}:{session_id}"


def _copy_state(state: MemoryState | None) -> MemoryState:
    if state is None:
        return MemoryState()
    return MemoryState(
        summary=state.summary,
        recent_messages=[dict(item) for item in state.recent_messages],
        entities=dict(state.entities),
        last_route=state.last_route,
        last_tool_calls=[dict(item) for item in state.last_tool_calls],
    )
