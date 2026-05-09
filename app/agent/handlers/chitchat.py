from __future__ import annotations

from app.agent.handlers.base import HandlerContext, HandlerResult, IntentHandler
from app.agent.handlers.utils import build_messages
from app.agent.prompts import CHITCHAT, FALLBACKS


class ChitchatHandler(IntentHandler):
    async def handle(self, ctx: HandlerContext) -> HandlerResult:
        messages = build_messages(CHITCHAT, ctx.history, ctx.content)
        try:
            answer = await ctx.llm_client.chat_messages(messages=messages)
        except TimeoutError:
            answer = FALLBACKS["chitchat_timeout"]
        except Exception:
            answer = FALLBACKS["chitchat_fallback"]
        return HandlerResult(answer=answer)
