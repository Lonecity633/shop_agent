import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment
from app.models.order import Order, OrderStatusLog
from app.models.refund import RefundTicket
from app.models.support import SupportSession
from app.models.user import User
from app.schemas.support import SupportSessionCreate


async def get_user_overview(db: AsyncSession, user_id: int) -> dict:
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise ValueError("用户不存在")

    order_result = await db.execute(select(Order).where(Order.user_id == user_id).order_by(Order.id.desc()).limit(10))
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

    return {
        "order_id": order_id,
        "payment_event": {
            "pay_status": order.pay_status.value,
            "pay_amount": str(order.pay_amount),
            "pay_channel": order.pay_channel,
            "paid_at": order.paid_at,
            "close_reason": order.close_reason,
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
