from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import String, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.audit import append_audit
from app.models.order import Order
from app.models.product import Product
from app.models.refund import RefundTicket
from app.models.support import (
    SupportSession,
    SupportTicket,
    SupportTicketAssignedRole,
    SupportTicketCategory,
    SupportTicketPriority,
    SupportTicketSource,
    SupportTicketStatus,
)
from app.models.user import User, UserRole
from app.schemas.support_ticket import SupportTicketCreate

ADMIN_CATEGORIES = {
    SupportTicketCategory.payment_issue,
    SupportTicketCategory.platform_rule,
    SupportTicketCategory.complaint,
}


async def get_ticket(db: AsyncSession, ticket_id: int) -> SupportTicket | None:
    result = await db.execute(select(SupportTicket).where(SupportTicket.id == ticket_id))
    return result.scalar_one_or_none()


async def get_ticket_for_update(db: AsyncSession, ticket_id: int) -> SupportTicket | None:
    result = await db.execute(select(SupportTicket).where(SupportTicket.id == ticket_id).with_for_update())
    return result.scalar_one_or_none()


async def create_ticket(db: AsyncSession, payload: SupportTicketCreate, actor: User) -> SupportTicket:
    assigned_role, assigned_id, seller_id, admin_id, resolved_order_id, resolved_product_id, resolved_refund_id = await resolve_assignment(
        db,
        category=SupportTicketCategory(payload.category),
        order_id=payload.order_id,
        product_id=payload.product_id,
        refund_id=payload.refund_id,
    )
    if payload.source_session_id is not None:
        await _ensure_session_exists(db, payload.source_session_id)

    ticket = SupportTicket(
        source_session_id=payload.source_session_id,
        buyer_id=actor.id,
        seller_id=seller_id,
        admin_id=admin_id,
        assigned_role=assigned_role,
        assigned_id=assigned_id,
        status=SupportTicketStatus.pending,
        category=SupportTicketCategory(payload.category),
        priority=SupportTicketPriority(payload.priority),
        source=SupportTicketSource(payload.source),
        order_id=resolved_order_id,
        product_id=resolved_product_id,
        refund_id=resolved_refund_id,
        title=payload.title,
        content=payload.content,
        ai_summary=payload.ai_summary,
        ai_trace_id=payload.ai_trace_id,
        trigger_reason=payload.trigger_reason,
        guardrail_flags=json.dumps(payload.guardrail_flags, ensure_ascii=False),
    )
    db.add(ticket)
    await db.flush()
    await append_audit(
        db,
        entity_type="support_ticket",
        entity_id=ticket.id,
        action="support_ticket_created",
        actor_id=actor.id,
        actor_role=actor.role.value,
        before_state={},
        after_state=_ticket_audit_state(ticket),
        reason=payload.trigger_reason or payload.title,
    )
    await db.commit()
    await db.refresh(ticket)
    return ticket


async def create_ticket_from_tool(
    db: AsyncSession,
    *,
    actor: User,
    source_session_id: int | None,
    title: str,
    content: str,
    category: str,
    priority: str,
    source: str,
    order_id: str | None = None,
    product_id: int | None = None,
    refund_id: int | None = None,
    ai_summary: str = "",
    ai_trace_id: str | None = None,
    trigger_reason: str = "",
    guardrail_flags: list[str] | None = None,
) -> SupportTicket:
    resolved_order_id = await _resolve_order_id(db, actor, order_id)
    payload = SupportTicketCreate(
        source_session_id=source_session_id,
        order_id=resolved_order_id,
        product_id=product_id,
        refund_id=refund_id,
        category=_safe_category(category),
        priority=_safe_priority(priority),
        source=_safe_source(source),
        title=title[:200] or "人工客服工单",
        content=content[:8000] or title[:8000] or "需要人工处理",
        ai_summary=ai_summary[:4000],
        ai_trace_id=ai_trace_id[:120] if ai_trace_id else None,
        trigger_reason=trigger_reason[:2000],
        guardrail_flags=guardrail_flags or [],
    )
    return await create_ticket(db, payload, actor)


async def list_user_tickets(db: AsyncSession, user_id: int) -> list[SupportTicket]:
    result = await db.execute(
        select(SupportTicket).where(SupportTicket.buyer_id == user_id).order_by(SupportTicket.id.desc())
    )
    return list(result.scalars().all())


async def list_seller_tickets(db: AsyncSession, seller_id: int) -> list[SupportTicket]:
    result = await db.execute(
        select(SupportTicket)
        .where(
            SupportTicket.assigned_role == SupportTicketAssignedRole.seller,
            SupportTicket.assigned_id == seller_id,
            SupportTicket.seller_id == seller_id,
        )
        .order_by(SupportTicket.id.desc())
    )
    return list(result.scalars().all())


async def list_admin_tickets(
    db: AsyncSession,
    *,
    status: str | None,
    assigned_role: str | None,
    category: str | None,
    keyword: str | None,
) -> list[SupportTicket]:
    stmt = select(SupportTicket)
    if status and status != "all":
        stmt = stmt.where(SupportTicket.status == _safe_status(status))
    if assigned_role and assigned_role != "all":
        stmt = stmt.where(SupportTicket.assigned_role == _safe_assigned_role(assigned_role))
    if category and category != "all":
        stmt = stmt.where(SupportTicket.category == SupportTicketCategory(_safe_category(category)))
    if keyword and keyword.strip():
        pattern = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                SupportTicket.title.like(pattern),
                SupportTicket.content.like(pattern),
                cast(SupportTicket.id, String).like(pattern),
                cast(SupportTicket.order_id, String).like(pattern),
            )
        )
    result = await db.execute(stmt.order_by(SupportTicket.id.desc()).limit(200))
    return list(result.scalars().all())


async def reply_ticket(db: AsyncSession, ticket: SupportTicket, actor: User, reply_content: str) -> SupportTicket:
    return await _transition_ticket(
        db,
        ticket,
        actor,
        status=SupportTicketStatus.replied,
        action="support_ticket_replied",
        reply_content=reply_content,
        mark_resolved=True,
    )


async def cancel_ticket(db: AsyncSession, ticket: SupportTicket, actor: User, reply_content: str) -> SupportTicket:
    return await _transition_ticket(
        db,
        ticket,
        actor,
        status=SupportTicketStatus.cancelled,
        action="support_ticket_cancelled",
        reply_content=reply_content,
        mark_resolved=True,
    )


async def close_ticket(db: AsyncSession, ticket: SupportTicket, actor: User, reply_content: str) -> SupportTicket:
    return await _transition_ticket(
        db,
        ticket,
        actor,
        status=SupportTicketStatus.closed,
        action="support_ticket_closed",
        reply_content=reply_content,
        mark_resolved=True,
    )


async def escalate_ticket(db: AsyncSession, ticket: SupportTicket, actor: User, reason: str) -> SupportTicket:
    before_state = _ticket_audit_state(ticket)
    ticket.assigned_role = SupportTicketAssignedRole.admin
    ticket.assigned_id = None
    ticket.admin_id = None
    ticket.status = SupportTicketStatus.escalated
    ticket.source = SupportTicketSource.seller_escalation
    ticket.trigger_reason = reason
    ticket.escalated_at = datetime.now(UTC)
    await append_audit(
        db,
        entity_type="support_ticket",
        entity_id=ticket.id,
        action="support_ticket_escalated",
        actor_id=actor.id,
        actor_role=actor.role.value,
        before_state=before_state,
        after_state=_ticket_audit_state(ticket),
        reason=reason,
    )
    await db.commit()
    await db.refresh(ticket)
    return ticket


async def resolve_assignment(
    db: AsyncSession,
    *,
    category: SupportTicketCategory,
    order_id: int | None,
    product_id: int | None,
    refund_id: int | None,
) -> tuple[SupportTicketAssignedRole, int | None, int | None, int | None, int | None, int | None, int | None]:
    if category in ADMIN_CATEGORIES:
        return SupportTicketAssignedRole.admin, None, None, None, order_id, product_id, refund_id

    if refund_id is not None:
        refund = await db.get(RefundTicket, refund_id)
        if refund is not None:
            return SupportTicketAssignedRole.seller, refund.seller_id, refund.seller_id, None, refund.order_id, product_id, refund.id

    if order_id is not None:
        row = (
            await db.execute(
                select(Order.id, Order.product_id, Product.seller_id)
                .join(Product, Product.id == Order.product_id)
                .where(Order.id == order_id)
            )
        ).first()
        if row is not None:
            seller_id = int(row[2])
            return SupportTicketAssignedRole.seller, seller_id, seller_id, None, int(row[0]), int(row[1]), refund_id

    if product_id is not None:
        product = await db.get(Product, product_id)
        if product is not None:
            return SupportTicketAssignedRole.seller, product.seller_id, product.seller_id, None, order_id, product.id, refund_id

    return SupportTicketAssignedRole.admin, None, None, None, order_id, product_id, refund_id


async def _transition_ticket(
    db: AsyncSession,
    ticket: SupportTicket,
    actor: User,
    *,
    status: SupportTicketStatus,
    action: str,
    reply_content: str,
    mark_resolved: bool,
) -> SupportTicket:
    before_state = _ticket_audit_state(ticket)
    ticket.status = status
    ticket.reply_content = reply_content
    if mark_resolved:
        ticket.resolved_at = datetime.now(UTC)
    await append_audit(
        db,
        entity_type="support_ticket",
        entity_id=ticket.id,
        action=action,
        actor_id=actor.id,
        actor_role=actor.role.value,
        before_state=before_state,
        after_state=_ticket_audit_state(ticket),
        reason=reply_content,
    )
    await db.commit()
    await db.refresh(ticket)
    return ticket


async def _ensure_session_exists(db: AsyncSession, session_id: int) -> None:
    if await db.get(SupportSession, session_id) is None:
        raise ValueError("客服会话不存在")


async def _resolve_order_id(db: AsyncSession, actor: User, raw_order_id: str | None) -> int | None:
    text = str(raw_order_id or "").strip()
    if not text:
        return None
    stmt = select(Order.id).join(Product, Product.id == Order.product_id)
    if actor.role == UserRole.buyer:
        stmt = stmt.where(Order.user_id == actor.id)
    elif actor.role == UserRole.seller:
        stmt = stmt.where(Product.seller_id == actor.id)
    if text.isdigit():
        stmt = stmt.where(or_(Order.id == int(text), Order.order_no == text))
    else:
        stmt = stmt.where(Order.order_no == text)
    return (await db.execute(stmt.limit(1))).scalar_one_or_none()


def _ticket_audit_state(ticket: SupportTicket) -> dict:
    return {
        "status": ticket.status.value,
        "assigned_role": ticket.assigned_role.value,
        "assigned_id": ticket.assigned_id,
        "seller_id": ticket.seller_id,
        "admin_id": ticket.admin_id,
        "category": ticket.category.value,
        "priority": ticket.priority.value,
    }


def _safe_category(value: str) -> str:
    aliases = {
        "order": "logistics_issue",
        "refund": "refund_issue",
        "product": "product_consultation",
        "logistics": "logistics_issue",
        "quality": "quality_issue",
        "payment": "payment_issue",
        "policy": "platform_rule",
        "security": "platform_rule",
    }
    value = aliases.get(value, value)
    try:
        return SupportTicketCategory(value).value
    except ValueError:
        return SupportTicketCategory.other.value


def _safe_priority(value: str) -> str:
    try:
        return SupportTicketPriority(value).value
    except ValueError:
        return SupportTicketPriority.normal.value


def _safe_source(value: str) -> str:
    try:
        return SupportTicketSource(value).value
    except ValueError:
        return SupportTicketSource.agent.value


def _safe_status(value: str) -> SupportTicketStatus:
    aliases = {
        "open": "pending",
        "in_progress": "processing",
        "resolved": "replied",
        "rejected": "closed",
    }
    value = aliases.get(value, value)
    try:
        return SupportTicketStatus(value)
    except ValueError:
        return SupportTicketStatus.pending


def _safe_assigned_role(value: str) -> SupportTicketAssignedRole:
    try:
        return SupportTicketAssignedRole(value)
    except ValueError:
        return SupportTicketAssignedRole.admin
