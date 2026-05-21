from __future__ import annotations

from collections import defaultdict, deque
from typing import Deque


class ContextManager:
    def __init__(self, *, max_messages: int = 12) -> None:
        self.max_messages = max_messages
        self._store: dict[str, Deque[dict[str, str]]] = defaultdict(lambda: deque(maxlen=max_messages))

    async def get_history(self, session_id: str) -> list[dict[str, str]]:
        return list(self._store[session_id])

    async def append(self, session_id: str, *, role: str, content: str) -> None:
        self._store[session_id].append({"role": role, "content": content})

