import json
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment
from app.models.kb import KBChunk, KBDocument
from app.models.order import Order, OrderStatusLog
from app.models.refund import RefundTicket
from app.models.support import SupportMessage, SupportRetrievalLog, SupportSession
from app.models.user import User
from app.schemas.support import SupportMessageCreate, SupportSessionCreate


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


async def _get_session_or_raise(db: AsyncSession, session_id: int) -> SupportSession:
    result = await db.execute(select(SupportSession).where(SupportSession.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise ValueError("会话不存在")
    return session


def _parse_payload(value: str) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _to_float(value: Decimal | float | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _to_evidence_out(log: SupportRetrievalLog) -> dict:
    return {
        "id": log.id,
        "session_id": log.session_id,
        "message_id": log.message_id,
        "document_id": log.document_id,
        "chunk_id": log.chunk_id,
        "score": _to_float(log.score),
        "is_cited": log.is_cited,
        "payload": _parse_payload(log.payload_json),
        "created_at": log.created_at,
    }


async def create_support_message(db: AsyncSession, session_id: int, payload: SupportMessageCreate) -> dict:
    await _get_session_or_raise(db, session_id)

    message = SupportMessage(
        session_id=session_id,
        role=payload.role,
        content=payload.content,
        retrieval_query=payload.retrieval_query,
    )
    db.add(message)
    await db.flush()

    logs: list[SupportRetrievalLog] = []
    for evidence in payload.evidences:
        if evidence.document_id is not None:
            doc = (
                await db.execute(select(KBDocument.id).where(KBDocument.id == evidence.document_id))
            ).scalar_one_or_none()
            if doc is None:
                raise ValueError("知识库文档不存在")

        chunk_doc_id = None
        if evidence.chunk_id is not None:
            chunk_doc_id = (
                await db.execute(select(KBChunk.document_id).where(KBChunk.id == evidence.chunk_id))
            ).scalar_one_or_none()
            if chunk_doc_id is None:
                raise ValueError("知识库切片不存在")

        if evidence.document_id is not None and chunk_doc_id is not None and evidence.document_id != chunk_doc_id:
            raise ValueError("证据文档与切片不匹配")

        log = SupportRetrievalLog(
            session_id=session_id,
            message_id=message.id,
            document_id=evidence.document_id or chunk_doc_id,
            chunk_id=evidence.chunk_id,
            score=evidence.score,
            is_cited=evidence.is_cited,
            payload_json=json.dumps(evidence.payload, ensure_ascii=False),
        )
        db.add(log)
        logs.append(log)

    await db.commit()
    await db.refresh(message)
    for log in logs:
        await db.refresh(log)

    return {
        "message": message,
        "evidences": [_to_evidence_out(log) for log in logs],
    }


async def list_support_messages(db: AsyncSession, session_id: int) -> list[SupportMessage]:
    await _get_session_or_raise(db, session_id)
    result = await db.execute(
        select(SupportMessage).where(SupportMessage.session_id == session_id).order_by(SupportMessage.id.asc())
    )
    return list(result.scalars().all())


async def list_support_evidence(db: AsyncSession, session_id: int) -> list[dict]:
    await _get_session_or_raise(db, session_id)
    result = await db.execute(
        select(SupportRetrievalLog)
        .where(SupportRetrievalLog.session_id == session_id)
        .order_by(SupportRetrievalLog.id.asc())
    )
    logs = result.scalars().all()
    return [_to_evidence_out(log) for log in logs]
