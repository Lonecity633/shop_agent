from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.handlers.base import HandlerContext
from app.agent.handlers.chitchat import ChitchatHandler
from app.agent.handlers.order_query import OrderQueryHandler
from app.agent.handlers.policy import PolicyHandler
from app.agent.handlers.product_inquiry import ProductInquiryHandler
from app.agent.handlers.utils import history_to_text, parse_intent_output
from app.agent.llm_client import LLMClient
from app.agent.memory import ConversationMemory
from app.agent.prompts import CLASSIFIER, FALLBACKS, SENSITIVE_PATTERNS
from app.agent.router import IntentRouter
from app.models.support import SupportMessage, SupportSession
from app.models.user import User, UserRole

INTENT_LABELS = {"order_query", "policy_query", "product_inquiry", "chitchat"}


@dataclass
class AgentReplyResult:
    answer: str
    route: str
    resolved_seller_id: int | None
    evidences: list[dict]


class SupportAgentOrchestrator:
    def __init__(self):
        self.llm_client = LLMClient()
        self.memory = ConversationMemory(self.llm_client)
        self.router = IntentRouter()
        self.router.register("order_query", OrderQueryHandler())
        self.router.register("policy_query", PolicyHandler())
        self.router.register("product_inquiry", ProductInquiryHandler())
        self.router.register("chitchat", ChitchatHandler())

    async def reply(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        session_id: int,
        content: str,
        order_id: int | None,
        product_id: int | None,
    ) -> AgentReplyResult:
        session = await self._get_session(db, session_id)
        self._ensure_session_access(current_user, session)

        blocked_answer = self._guardrail_answer(content)
        if blocked_answer is not None:
            answer = blocked_answer
            route = "guardrail_blocked"
            tool_records: list[str] = []
            evidences: list[dict] = []
            resolved_seller_id: int | None = None
        else:
            history = await self.memory.get_history(db, session_id=session_id)
            route = await self._classify_intent(content=content, history=history)

            ctx = HandlerContext(
                db=db,
                current_user=current_user,
                content=content,
                history=history,
                order_id=order_id,
                product_id=product_id,
                llm_client=self.llm_client,
            )
            result = await self.router.dispatch(route, ctx)

            answer = result.answer
            tool_records = result.tool_records
            evidences = result.evidences
            resolved_seller_id = result.resolved_seller_id

        user_msg = SupportMessage(session_id=session_id, role="user", content=content, retrieval_query=content)
        db.add(user_msg)
        for item in tool_records:
            db.add(SupportMessage(session_id=session_id, role="tool", content=item, retrieval_query=""))
        assistant_msg = SupportMessage(session_id=session_id, role="assistant", content=answer, retrieval_query=content)
        db.add(assistant_msg)

        await db.commit()
        return AgentReplyResult(answer=answer, route=route, resolved_seller_id=resolved_seller_id, evidences=evidences)

    @staticmethod
    def _guardrail_answer(content: str) -> str | None:
        text = content.lower()
        if any(re.search(pattern, text) for pattern in SENSITIVE_PATTERNS):
            return FALLBACKS["guardrail_block"]
        return None

    async def _classify_intent(self, *, content: str, history: list[dict]) -> str:
        user_prompt = (
            f"历史对话（最近5轮）：\n{history_to_text(history)}\n\n"
            f"用户当前输入：{content}\n\n"
            "请输出 JSON。"
        )
        messages = [
            {"role": "system", "content": CLASSIFIER},
            {"role": "user", "content": user_prompt},
        ]
        try:
            raw = await self.llm_client.chat_messages(messages=messages)
        except Exception:
            return "chitchat"

        intent = parse_intent_output(raw)
        return intent if intent in INTENT_LABELS else "chitchat"

    @staticmethod
    async def _get_recent_history(db: AsyncSession, *, session_id: int, limit: int = 10) -> list[dict]:
        stmt = (
            select(SupportMessage)
            .where(SupportMessage.session_id == session_id)
            .order_by(SupportMessage.created_at.desc(), SupportMessage.id.desc())
            .limit(limit)
        )
        rows = list((await db.execute(stmt)).scalars().all())
        rows.reverse()
        allowed_roles = {"system", "user", "assistant"}
        return [{"role": item.role, "content": item.content} for item in rows if item.role in allowed_roles]

    @staticmethod
    async def _get_session(db: AsyncSession, session_id: int) -> SupportSession:
        result = await db.execute(select(SupportSession).where(SupportSession.id == session_id))
        session = result.scalar_one_or_none()
        if session is None:
            raise ValueError("会话不存在")
        return session

    @staticmethod
    def _ensure_session_access(current_user: User, session: SupportSession) -> None:
        if current_user.role == UserRole.admin:
            return
        if current_user.role in (UserRole.buyer, UserRole.seller) and session.user_id == current_user.id:
            return
        raise PermissionError("当前用户无权访问该会话")
