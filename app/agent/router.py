from __future__ import annotations

from app.agent.handlers.base import HandlerContext, HandlerResult, IntentHandler


class IntentRouter:
    def __init__(self) -> None:
        self._handlers: dict[str, IntentHandler] = {}

    def register(self, intent: str, handler: IntentHandler) -> None:
        self._handlers[intent] = handler

    async def dispatch(self, intent: str, ctx: HandlerContext) -> HandlerResult:
        handler = self._handlers.get(intent)
        if handler is None:
            raise ValueError(f"未注册的意图处理器: {intent}")
        return await handler.handle(ctx)
