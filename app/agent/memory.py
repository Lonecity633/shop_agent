from __future__ import annotations

from app.agent.context_manager import ContextManager


class ConversationMemory:
    def __init__(self, *_, **__) -> None:
        self._context = ContextManager()

    async def get_history(self, session_id: str, *_, **__) -> list[dict]:
        return await self._context.get_history(str(session_id))

