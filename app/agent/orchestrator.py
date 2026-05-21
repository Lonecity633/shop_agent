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
from app.agent.handlers.utils import history_to_text, parse_intent_classification
from app.agent.llm_client import LLMClient
from app.agent.memory import ConversationMemory
from app.agent.prompts import CLASSIFIER, FALLBACKS, SENSITIVE_PATTERNS
from app.agent.react_agent import ReactSupportAgent
from app.agent.router import IntentRouter
from app.crud.support_ticket import create_ticket_from_tool
from app.core.config import settings
from app.models.support import SupportMessage, SupportSession
from app.models.user import User, UserRole

INTENT_LABELS = {"order_query", "policy_query", "product_inquiry", "chitchat"}


@dataclass
class AgentReplyResult:
    answer: str
    route: str
    resolved_seller_id: int | None
    evidences: list[dict]
    support_ticket: dict | None = None


@dataclass
class IntentClassification:
    intent: str
    confidence: float
    reason: str = ""


class SupportAgentOrchestrator:
    def __init__(self):
        self.llm_client = LLMClient()
        self.memory = ConversationMemory(self.llm_client)
        self.react_agent = ReactSupportAgent()
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
        persisted_user_content = content

        blocked_answer = self._guardrail_answer(content)
        if blocked_answer is not None:
            persisted_user_content = "用户输入命中安全保护规则，原文已脱敏不入库。"
            support_ticket = await self._create_handoff_ticket(
                db,
                current_user=current_user,
                session_id=session_id,
                content="用户输入命中安全保护规则，原文已脱敏不入工单。",
                title="安全保护触发的人工审核工单",
                category="platform_rule",
                priority="high",
                source="guardrail",
                trigger_reason="guardrail_blocked",
                ai_summary="用户输入命中敏感信息保护规则，已转管理员人工审核。",
                ai_trace_id=f"guardrail:{session_id}",
                order_id=order_id,
                product_id=product_id,
                guardrail_flags=["sensitive_content"],
            )
            answer = f"{blocked_answer}\n\n已为你创建人工审核工单 #{support_ticket['ticket_id']}，将由管理员处理。"
            route = "guardrail_blocked"
            tool_records: list[str] = []
            evidences: list[dict] = []
            resolved_seller_id: int | None = None
        else:
            history = await self.memory.get_history(db, session_id=session_id)
            classification = await self._classify_intent(content=content, history=history)

            ctx = HandlerContext(
                db=db,
                current_user=current_user,
                content=content,
                history=history,
                session_id=session_id,
                order_id=order_id,
                product_id=product_id,
                llm_client=self.llm_client,
            )
            support_ticket = None
            if self._should_create_direct_ticket(content=content, classification=classification):
                low_confidence_handoff = self._is_low_confidence_handoff(content=content, classification=classification)
                support_ticket = await self._create_handoff_ticket(
                    db,
                    current_user=current_user,
                    session_id=session_id,
                    content=content,
                    title=self._ticket_title(content),
                    category=self._ticket_category(content, classification.intent),
                    priority=self._ticket_priority(content),
                    source="agent",
                    trigger_reason="low_confidence_handoff" if low_confidence_handoff else "manual_handoff",
                    ai_summary="AI 客服触发转人工。",
                    ai_trace_id=f"handoff:{session_id}",
                    order_id=order_id,
                    product_id=product_id,
                    guardrail_flags=[],
                )
                route = "human_handoff"
                answer = self._ticket_answer(support_ticket)
                tool_records = []
                evidences = [{"tool": "create_support_ticket", "source": "orchestrator", "result": support_ticket}]
                resolved_seller_id = support_ticket.get("assigned_id") if support_ticket.get("assigned_role") == "seller" else None
            elif self._should_use_react(content=content, order_id=order_id, product_id=product_id, classification=classification):
                route = "react_agent"
                result = await self.react_agent.handle(ctx)
                support_ticket = self._extract_ticket_from_evidences(result.evidences)
            else:
                route = classification.intent
                result = await self.router.dispatch(route, ctx)

            if route != "human_handoff":
                answer = result.answer
                tool_records = result.tool_records
                evidences = result.evidences
                resolved_seller_id = result.resolved_seller_id
                if support_ticket is None and self._answer_requests_handoff(answer):
                    support_ticket = await self._create_handoff_ticket(
                        db,
                        current_user=current_user,
                        session_id=session_id,
                        content=content,
                        title=self._ticket_title(content),
                        category=self._ticket_category(content, classification.intent),
                        priority=self._ticket_priority(content),
                        source="agent",
                        trigger_reason="agent_fallback_handoff",
                        ai_summary="AI 回复建议联系人工客服，系统兜底创建工单。",
                        ai_trace_id=f"fallback:{session_id}",
                        order_id=order_id,
                        product_id=product_id,
                        guardrail_flags=[],
                    )
                    answer = f"{answer}\n\n已为你创建人工客服工单 #{support_ticket['ticket_id']}，当前处理方：{self._assigned_role_label(support_ticket)}。"
                    evidences = [*evidences, {"tool": "create_support_ticket", "source": "orchestrator", "result": support_ticket}]

        user_msg = SupportMessage(
            session_id=session_id,
            role="user",
            content=persisted_user_content,
            retrieval_query=persisted_user_content,
        )
        db.add(user_msg)
        for item in tool_records:
            db.add(SupportMessage(session_id=session_id, role="tool", content=item, retrieval_query=""))
        assistant_msg = SupportMessage(session_id=session_id, role="assistant", content=answer, retrieval_query=content)
        db.add(assistant_msg)

        await db.commit()
        return AgentReplyResult(
            answer=answer,
            route=route,
            resolved_seller_id=resolved_seller_id,
            evidences=evidences,
            support_ticket=support_ticket,
        )

    @staticmethod
    def _guardrail_answer(content: str) -> str | None:
        text = content.lower()
        if any(re.search(pattern, text) for pattern in SENSITIVE_PATTERNS):
            return FALLBACKS["guardrail_block"]
        return None

    async def _classify_intent(self, *, content: str, history: list[dict]) -> IntentClassification:
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
            return IntentClassification(intent="chitchat", confidence=0.0, reason="classifier_failed")

        payload = parse_intent_classification(raw)
        intent = str(payload.get("intent", "")).strip()
        if intent not in INTENT_LABELS:
            intent = "chitchat"
        try:
            confidence = float(payload.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(confidence, 1.0))
        reason = str(payload.get("reason") or "")
        return IntentClassification(intent=intent, confidence=confidence, reason=reason)

    @staticmethod
    def _should_use_react(
        *,
        content: str,
        order_id: int | None,
        product_id: int | None,
        classification: IntentClassification,
    ) -> bool:
        if not settings.support_react_enabled:
            return False
        domains = SupportAgentOrchestrator._domain_hits(content, order_id=order_id, product_id=product_id)
        if classification.confidence < settings.support_react_trigger_confidence and domains:
            return True
        return len(domains) >= 2

    @staticmethod
    def _domain_hits(content: str, *, order_id: int | None, product_id: int | None) -> set[str]:
        text = content.lower()
        domains: set[str] = set()
        if product_id is not None or any(
            keyword in text
            for keyword in ("商品", "库存", "价格", "多少钱", "对比", "比较", "另一个", "推荐", "规格")
        ):
            domains.add("product")
        if order_id is not None or re.search(r"\bso\d{8,}\b", text) or any(
            keyword in text
            for keyword in ("订单", "物流", "快递", "支付", "发货", "收货", "签收")
        ):
            domains.add("order")
        if any(
            keyword in text
            for keyword in ("政策", "规则", "退换货", "退货", "换货", "退款", "售后", "发票", "运费", "保修")
        ):
            domains.add("policy")
        return domains

    @staticmethod
    def _should_create_direct_ticket(*, content: str, classification: IntentClassification) -> bool:
        if SupportAgentOrchestrator._has_manual_handoff_keyword(content):
            return True
        if SupportAgentOrchestrator._has_risk_keyword(content):
            return True
        return SupportAgentOrchestrator._is_low_confidence_handoff(content=content, classification=classification)

    @staticmethod
    def _is_low_confidence_handoff(*, content: str, classification: IntentClassification) -> bool:
        text = content.lower()
        return classification.confidence < settings.support_react_trigger_confidence and any(
            keyword in text for keyword in ("退款", "订单", "物流", "质量", "售后", "投诉")
        )

    @staticmethod
    def _has_manual_handoff_keyword(content: str) -> bool:
        text = content.lower()
        return any(keyword in text for keyword in ("人工", "转人工", "人工客服", "投诉", "申诉", "纠纷", "卖家处理不了", "客服工单"))

    @staticmethod
    def _has_risk_keyword(content: str) -> bool:
        text = content.lower()
        return any(keyword in text for keyword in ("越权", "敏感", "支付异常", "扣款", "盗刷", "规则争议"))

    @staticmethod
    def _answer_requests_handoff(answer: str) -> bool:
        return any(keyword in answer for keyword in ("联系人工客服", "人工客服", "人工处理"))

    @staticmethod
    def _ticket_category(content: str, intent: str) -> str:
        text = content.lower()
        if any(keyword in text for keyword in ("投诉", "纠纷", "申诉")):
            return "complaint"
        if any(keyword in text for keyword in ("支付", "扣款", "付款", "盗刷")):
            return "payment_issue"
        if any(keyword in text for keyword in ("越权", "敏感", "身份证", "银行卡", "密码", "cvv")):
            return "platform_rule"
        if any(keyword in text for keyword in ("平台规则", "规则", "政策")) or intent == "policy_query":
            return "platform_rule"
        if any(keyword in text for keyword in ("物流", "快递", "发货", "签收")):
            return "logistics_issue"
        if any(keyword in text for keyword in ("质量", "破损", "坏了", "瑕疵")):
            return "quality_issue"
        if any(keyword in text for keyword in ("退款", "退货", "售后")):
            return "refund_issue"
        if any(keyword in text for keyword in ("商品", "库存", "价格")) or intent == "product_inquiry":
            return "product_consultation"
        if any(keyword in text for keyword in ("订单", "order")) or intent == "order_query":
            return "logistics_issue"
        return "other"

    @staticmethod
    def _ticket_priority(content: str) -> str:
        text = content.lower()
        if any(keyword in text for keyword in ("投诉", "纠纷", "盗刷", "越权", "敏感")):
            return "high"
        return "normal"

    @staticmethod
    def _ticket_title(content: str) -> str:
        text = content.strip().replace("\n", " ")
        return (text[:60] or "人工客服工单")

    async def _create_handoff_ticket(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        session_id: int,
        content: str,
        title: str,
        category: str,
        priority: str,
        source: str,
        trigger_reason: str,
        ai_summary: str,
        ai_trace_id: str,
        order_id: int | None,
        product_id: int | None,
        guardrail_flags: list[str],
    ) -> dict:
        ticket = await create_ticket_from_tool(
            db,
            actor=current_user,
            source_session_id=session_id,
            title=title,
            content=content,
            category=category,
            priority=priority,
            source=source,
            order_id=str(order_id) if order_id is not None else self._extract_order_no(content),
            product_id=product_id,
            refund_id=None,
            ai_summary=ai_summary,
            ai_trace_id=ai_trace_id,
            trigger_reason=trigger_reason,
            guardrail_flags=guardrail_flags,
        )
        return {
            "ticket_id": ticket.id,
            "status": ticket.status.value,
            "assigned_role": ticket.assigned_role.value,
            "assigned_id": ticket.assigned_id,
            "seller_id": ticket.seller_id,
            "admin_id": ticket.admin_id,
            "category": ticket.category.value,
        }

    @staticmethod
    def _extract_ticket_from_evidences(evidences: list[dict]) -> dict | None:
        for evidence in evidences:
            if evidence.get("tool") != "create_support_ticket":
                continue
            result = evidence.get("result") or {}
            data = result.get("data") if isinstance(result, dict) else None
            if isinstance(data, dict) and data.get("ticket_id"):
                return data
        return None

    @staticmethod
    def _ticket_answer(ticket: dict) -> str:
        return f"已为你创建人工客服工单 #{ticket['ticket_id']}，当前处理方：{SupportAgentOrchestrator._assigned_role_label(ticket)}。"

    @staticmethod
    def _assigned_role_label(ticket: dict) -> str:
        return "卖家" if ticket.get("assigned_role") == "seller" else "管理员"

    @staticmethod
    def _extract_order_no(content: str) -> str | None:
        match = re.search(r"\bSO\d{8,}\b", content, flags=re.IGNORECASE)
        return match.group(0).upper() if match else None

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
