from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import support_ticket as ticket_crud
from app.models.support import SupportTicket, SupportTicketAssignedRole, SupportTicketStatus
from app.models.user import User, UserRole
from app.schemas.support_ticket import (
    SupportTicketClose,
    SupportTicketCreate,
    SupportTicketEscalate,
    SupportTicketReject,
    SupportTicketResolve,
)
from app.services.common import ServiceError, ensure


async def create_ticket(db: AsyncSession, current_user: User, payload: SupportTicketCreate) -> SupportTicket:
    ensure(current_user.role in (UserRole.buyer, UserRole.seller), "ROLE_DENIED", "仅买家或卖家可创建人工工单", 403)
    try:
        return await ticket_crud.create_ticket(db, payload, current_user)
    except ValueError as exc:
        raise ServiceError("SUPPORT_TICKET_CREATE_FAILED", str(exc), 400) from exc


async def list_my_tickets(db: AsyncSession, current_user: User) -> list[SupportTicket]:
    ensure(current_user.role in (UserRole.buyer, UserRole.seller), "ROLE_DENIED", "仅买家或卖家可查看自己的工单", 403)
    return await ticket_crud.list_user_tickets(db, current_user.id)


async def get_ticket(db: AsyncSession, current_user: User, ticket_id: int) -> SupportTicket:
    ticket = await ticket_crud.get_ticket(db, ticket_id)
    ensure(ticket is not None, "SUPPORT_TICKET_NOT_FOUND", "人工工单不存在", 404)
    _ensure_ticket_access(current_user, ticket)
    return ticket


async def list_seller_tickets(db: AsyncSession, current_user: User) -> list[SupportTicket]:
    ensure(current_user.role == UserRole.seller, "ROLE_DENIED", "仅卖家可查看分配工单", 403)
    return await ticket_crud.list_seller_tickets(db, current_user.id)


async def seller_resolve_ticket(
    db: AsyncSession,
    current_user: User,
    ticket_id: int,
    payload: SupportTicketResolve,
) -> SupportTicket:
    ensure(current_user.role == UserRole.seller, "ROLE_DENIED", "仅卖家可处理分配工单", 403)
    ticket = await ticket_crud.get_ticket_for_update(db, ticket_id)
    ensure(ticket is not None, "SUPPORT_TICKET_NOT_FOUND", "人工工单不存在", 404)
    _ensure_seller_assignee(current_user, ticket)
    _ensure_mutable(ticket)
    return await ticket_crud.reply_ticket(db, ticket, current_user, payload.reply_content)


async def seller_escalate_ticket(
    db: AsyncSession,
    current_user: User,
    ticket_id: int,
    payload: SupportTicketEscalate,
) -> SupportTicket:
    ensure(current_user.role == UserRole.seller, "ROLE_DENIED", "仅卖家可升级分配工单", 403)
    ticket = await ticket_crud.get_ticket_for_update(db, ticket_id)
    ensure(ticket is not None, "SUPPORT_TICKET_NOT_FOUND", "人工工单不存在", 404)
    _ensure_seller_assignee(current_user, ticket)
    _ensure_mutable(ticket)
    return await ticket_crud.escalate_ticket(db, ticket, current_user, payload.reason)


async def list_admin_tickets(
    db: AsyncSession,
    current_user: User,
    *,
    status: str | None,
    assigned_role: str | None,
    category: str | None,
    keyword: str | None,
) -> list[SupportTicket]:
    ensure(current_user.role == UserRole.admin, "ROLE_DENIED", "仅管理员可查看人工工单池", 403)
    return await ticket_crud.list_admin_tickets(
        db,
        status=status,
        assigned_role=assigned_role,
        category=category,
        keyword=keyword,
    )


async def admin_resolve_ticket(
    db: AsyncSession,
    current_user: User,
    ticket_id: int,
    payload: SupportTicketResolve,
) -> SupportTicket:
    ensure(current_user.role == UserRole.admin, "ROLE_DENIED", "仅管理员可处理人工工单", 403)
    ticket = await _admin_ticket_for_update(db, ticket_id)
    _ensure_mutable(ticket)
    return await ticket_crud.reply_ticket(db, ticket, current_user, payload.reply_content)


async def admin_reject_ticket(
    db: AsyncSession,
    current_user: User,
    ticket_id: int,
    payload: SupportTicketReject,
) -> SupportTicket:
    ensure(current_user.role == UserRole.admin, "ROLE_DENIED", "仅管理员可驳回人工工单", 403)
    ticket = await _admin_ticket_for_update(db, ticket_id)
    _ensure_mutable(ticket)
    return await ticket_crud.cancel_ticket(db, ticket, current_user, payload.reply_content)


async def admin_close_ticket(
    db: AsyncSession,
    current_user: User,
    ticket_id: int,
    payload: SupportTicketClose,
) -> SupportTicket:
    ensure(current_user.role == UserRole.admin, "ROLE_DENIED", "仅管理员可关闭人工工单", 403)
    ticket = await _admin_ticket_for_update(db, ticket_id)
    return await ticket_crud.close_ticket(db, ticket, current_user, payload.reply_content or "管理员关闭工单")


def _ensure_ticket_access(current_user: User, ticket: SupportTicket) -> None:
    if current_user.role == UserRole.admin:
        return
    if ticket.buyer_id == current_user.id:
        return
    if (
        current_user.role == UserRole.seller
        and ticket.assigned_role == SupportTicketAssignedRole.seller
        and ticket.assigned_id == current_user.id
    ):
        return
    raise ServiceError("SUPPORT_TICKET_FORBIDDEN", "无权限访问该人工工单", 403)


def _ensure_seller_assignee(current_user: User, ticket: SupportTicket) -> None:
    ensure(
        ticket.assigned_role == SupportTicketAssignedRole.seller and ticket.assigned_id == current_user.id,
        "SUPPORT_TICKET_FORBIDDEN",
        "仅工单分配卖家可处理",
        403,
    )


def _ensure_mutable(ticket: SupportTicket) -> None:
    ensure(
        ticket.status not in {
            SupportTicketStatus.replied,
            SupportTicketStatus.cancelled,
            SupportTicketStatus.closed,
        },
        "SUPPORT_TICKET_CLOSED",
        "该工单已结束，不能继续处理",
        400,
    )


async def _admin_ticket_for_update(db: AsyncSession, ticket_id: int) -> SupportTicket:
    ticket = await ticket_crud.get_ticket_for_update(db, ticket_id)
    ensure(ticket is not None, "SUPPORT_TICKET_NOT_FOUND", "人工工单不存在", 404)
    return ticket
