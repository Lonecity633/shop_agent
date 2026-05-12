import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment
from app.models.order import Order, OrderStatusLog
from app.models.payment import PaymentTransaction
from app.models.refund import RefundTicket
from app.models.support import SupportMessage, SupportSession
from app.models.user import User
from app.schemas.support import SupportMessageCreate, SupportSessionCreate


async def get_user_overview(db: AsyncSession, user_id: int) -> dict:
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise ValueError("用户不存在")

    order_result = await db.execute(select(Order).where(Order.user_id == user_id).order_by(Order.id.desc()).limit(10))
    payment_result = await db.execute(
        select(PaymentTransaction)
        .where(PaymentTransaction.buyer_id == user_id)
        .order_by(PaymentTransaction.id.desc())
        .limit(10)
    )
    refund_result = await db.execute(select(RefundTicket).where(RefundTicket.buyer_id == user_id).order_by(RefundTicket.id.desc()).limit(10))
    comment_result = await db.execute(select(Comment).where(Comment.user_id == user_id).order_by(Comment.id.desc()).limit(10))

    return {
        "user_id": user.id,
        "email": user.email,
        "role": user.role.value,
        "recent_orders": [
            {
                "order_id": o.id,
                "status": o.status.value,
                "pay_status": o.pay_status.value,
                "total_price": str(o.total_price),
                "tracking_no": o.tracking_no,
                "logistics_company": o.logistics_company,
                "created_at": o.created_at,
            }
            for o in order_result.scalars().all()
        ],
        "recent_payments": [
            {
                "payment_no": p.payment_no,
                "order_id": p.order_id,
                "status": p.status.value,
                "channel": p.channel,
                "amount": str(p.amount),
                "failure_reason": p.failure_reason,
                "provider_trade_no": p.provider_trade_no,
                "created_at": p.created_at,
                "paid_at": p.paid_at,
            }
            for p in payment_result.scalars().all()
        ],
        "recent_refunds": [
            {
                "refund_id": r.id,
                "order_id": r.order_id,
                "status": r.status.value,
                "amount": str(r.amount),
                "reason": r.reason,
                "updated_at": r.updated_at,
            }
            for r in refund_result.scalars().all()
        ],
        "recent_comments": [
            {
                "comment_id": c.id,
                "order_id": c.order_id,
                "rating": c.rating,
                "content": c.content,
                "created_at": c.created_at,
            }
            for c in comment_result.scalars().all()
        ],
    }


async def get_order_timeline(db: AsyncSession, order_id: int) -> dict:
    order_result = await db.execute(select(Order).where(Order.id == order_id))
    order = order_result.scalar_one_or_none()
    if order is None:
        raise ValueError("订单不存在")

    status_result = await db.execute(
        select(OrderStatusLog).where(OrderStatusLog.order_id == order_id).order_by(OrderStatusLog.id.asc())
    )
    refund_result = await db.execute(
        select(RefundTicket).where(RefundTicket.order_id == order_id).order_by(RefundTicket.id.asc())
    )
    payment_result = await db.execute(
        select(PaymentTransaction).where(PaymentTransaction.order_id == order_id).order_by(PaymentTransaction.id.desc())
    )
    payments = payment_result.scalars().all()

    return {
        "order_id": order_id,
        "payment_event": {
            "pay_status": order.pay_status.value,
            "pay_amount": str(order.pay_amount),
            "pay_channel": order.pay_channel,
            "paid_at": order.paid_at,
            "close_reason": order.close_reason,
            "latest_transaction": (
                {
                    "payment_no": payments[0].payment_no,
                    "status": payments[0].status.value,
                    "channel": payments[0].channel,
                    "provider_trade_no": payments[0].provider_trade_no,
                    "failure_reason": payments[0].failure_reason,
                    "created_at": payments[0].created_at,
                    "paid_at": payments[0].paid_at,
                }
                if payments
                else None
            ),
        },
        "status_logs": [
            {
                "id": log.id,
                "from_status": log.from_status,
                "to_status": log.to_status,
                "actor_id": log.actor_id,
                "actor_role": log.actor_role,
                "reason": log.reason,
                "created_at": log.created_at,
            }
            for log in status_result.scalars().all()
        ],
        "refund_events": [
            {
                "refund_id": item.id,
                "status": item.status.value,
                "amount": str(item.amount),
                "reason": item.reason,
                "seller_note": item.seller_note,
                "admin_note": item.admin_note,
                "updated_at": item.updated_at,
            }
            for item in refund_result.scalars().all()
        ],
    }


async def create_support_session(db: AsyncSession, operator_id: int, payload: SupportSessionCreate) -> SupportSession:
    user_result = await db.execute(select(User).where(User.id == payload.user_id))
    if user_result.scalar_one_or_none() is None:
        raise ValueError("用户不存在")

    session = SupportSession(
        operator_id=operator_id,
        user_id=payload.user_id,
        question=payload.question,
        answer=payload.answer,
        queried_entities=json.dumps(payload.queried_entities, ensure_ascii=False),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def create_support_session_for_user(
    db: AsyncSession,
    *,
    user_id: int,
    question: str,
    queried_entities: list[dict],
) -> SupportSession:
    session = SupportSession(
        operator_id=user_id,
        user_id=user_id,
        question=question,
        answer="",
        queried_entities=json.dumps(queried_entities, ensure_ascii=False),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def _get_session_or_raise(db: AsyncSession, session_id: int) -> SupportSession:
    result = await db.execute(select(SupportSession).where(SupportSession.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise ValueError("会话不存在")
    return session


async def get_support_session(db: AsyncSession, session_id: int) -> SupportSession | None:
    result = await db.execute(select(SupportSession).where(SupportSession.id == session_id))
    return result.scalar_one_or_none()


async def get_latest_support_session_for_user(db: AsyncSession, user_id: int) -> SupportSession | None:
    result = await db.execute(
        select(SupportSession)
        .where(SupportSession.user_id == user_id)
        .order_by(SupportSession.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_support_message(db: AsyncSession, session_id: int, payload: SupportMessageCreate) -> dict:
    await _get_session_or_raise(db, session_id)

    message = SupportMessage(
        session_id=session_id,
        role=payload.role,
        content=payload.content,
        retrieval_query=payload.retrieval_query,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return {"message": message}


async def list_support_messages(db: AsyncSession, session_id: int) -> list[SupportMessage]:
    await _get_session_or_raise(db, session_id)
    visible_roles = ("system", "user", "assistant")
    result = await db.execute(
        select(SupportMessage)
        .where(
            SupportMessage.session_id == session_id,
            SupportMessage.role.in_(visible_roles),
        )
        .order_by(SupportMessage.id.asc())
    )
    return list(result.scalars().all())
