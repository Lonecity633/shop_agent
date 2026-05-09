from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm_client import LLMClient
from app.agent.prompts import SUMMARY
from app.models.support import SupportMessage, SupportSession

logger = logging.getLogger(__name__)

RECENT_LIMIT = 10
SUMMARY_THRESHOLD = 15


class ConversationMemory:
    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client

    async def get_history(self, db: AsyncSession, session_id: int) -> list[dict]:
        session = await db.get(SupportSession, session_id)
        existing_summary = (session.summary or "").strip() if session else ""

        stmt = (
            select(SupportMessage)
            .where(SupportMessage.session_id == session_id)
            .where(SupportMessage.role.in_(("system", "user", "assistant")))
            .order_by(SupportMessage.created_at.asc(), SupportMessage.id.asc())
        )
        rows = list((await db.execute(stmt)).scalars().all())

        if len(rows) <= SUMMARY_THRESHOLD:
            result = [{"role": r.role, "content": r.content} for r in rows]
            if existing_summary:
                return [{"role": "system", "content": f"之前的对话摘要：{existing_summary}"}] + result
            return result

        old_rows = rows[:-RECENT_LIMIT]
        recent_rows = rows[-RECENT_LIMIT:]
        recent = [{"role": r.role, "content": r.content} for r in recent_rows]

        new_summary = await self._summarize(old_rows, existing_summary)
        if new_summary and session:
            session.summary = new_summary
            await db.flush()

        return [{"role": "system", "content": f"之前的对话摘要：{new_summary}"}] + recent

    async def _summarize(self, old_rows: list, existing_summary: str) -> str:
        history_text = "\n".join(f"{r.role}: {r.content}" for r in old_rows)
        prompt = f"已有摘要：{existing_summary or '（无）'}\n\n{history_text}"
        user_msg = SUMMARY.replace("{history}", prompt)
        try:
            return await self._llm.chat_messages(
                messages=[{"role": "user", "content": user_msg}]
            )
        except Exception:
            logger.exception("对话摘要生成失败")
            return existing_summary
