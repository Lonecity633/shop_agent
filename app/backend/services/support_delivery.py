from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.models.support import MessageOutbox, MessageOutboxStatus, SupportFollowup, SupportFollowupStatus


MAX_OUTBOX_ATTEMPTS = 5


def delivery_backoff(attempts: int) -> timedelta:
    seconds = min(3600, 2 ** max(0, attempts) * 30)
    return timedelta(seconds=seconds)


async def enqueue_message(
    db: AsyncSession,
    *,
    idempotency_key: str,
    recipient_user_id: int | None,
    payload: dict[str, Any],
    channel: str = "in_app",
    session_id: str = "",
    message_type: str = "support_reply",
) -> MessageOutbox:
    existing = await _get_outbox_by_key(db, idempotency_key)
    if existing is not None:
        return existing
    item = MessageOutbox(
        idempotency_key=idempotency_key,
        recipient_user_id=recipient_user_id,
        channel=channel,
        session_id=session_id,
        message_type=message_type,
        payload_json=_json(payload),
        status=MessageOutboxStatus.pending,
        next_attempt_at=datetime.now(UTC),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def mark_message_sent(db: AsyncSession, item: MessageOutbox) -> MessageOutbox:
    item.status = MessageOutboxStatus.sent
    item.last_error = ""
    await db.commit()
    await db.refresh(item)
    return item


async def mark_message_failed(db: AsyncSession, item: MessageOutbox, error: str) -> MessageOutbox:
    item.attempts += 1
    item.last_error = error[:2000]
    if item.attempts >= MAX_OUTBOX_ATTEMPTS:
        item.status = MessageOutboxStatus.dead
        item.next_attempt_at = None
    else:
        item.status = MessageOutboxStatus.pending
        item.next_attempt_at = datetime.now(UTC) + delivery_backoff(item.attempts)
    await db.commit()
    await db.refresh(item)
    return item


async def list_due_messages(db: AsyncSession, *, limit: int = 50) -> list[MessageOutbox]:
    now = datetime.now(UTC)
    result = await db.execute(
        select(MessageOutbox)
        .where(
            MessageOutbox.status == MessageOutboxStatus.pending,
            MessageOutbox.next_attempt_at <= now,
        )
        .order_by(MessageOutbox.id.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def schedule_followup(
    db: AsyncSession,
    *,
    user_id: int,
    idempotency_key: str,
    due_at: datetime,
    business_type: str,
    payload: dict[str, Any],
    session_id: str = "",
    business_id: str = "",
) -> SupportFollowup:
    existing = await _get_followup_by_key(db, idempotency_key)
    if existing is not None:
        return existing
    item = SupportFollowup(
        user_id=user_id,
        session_id=session_id,
        business_type=business_type,
        business_id=business_id,
        idempotency_key=idempotency_key,
        due_at=due_at,
        status=SupportFollowupStatus.pending,
        payload_json=_json(payload),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def mark_followup_completed(db: AsyncSession, item: SupportFollowup) -> SupportFollowup:
    item.status = SupportFollowupStatus.completed
    item.last_error = ""
    await db.commit()
    await db.refresh(item)
    return item


async def mark_followup_failed(db: AsyncSession, item: SupportFollowup, error: str) -> SupportFollowup:
    item.attempts += 1
    item.status = SupportFollowupStatus.failed
    item.last_error = error[:2000]
    await db.commit()
    await db.refresh(item)
    return item


async def list_due_followups(db: AsyncSession, *, limit: int = 50) -> list[SupportFollowup]:
    now = datetime.now(UTC)
    result = await db.execute(
        select(SupportFollowup)
        .where(SupportFollowup.status == SupportFollowupStatus.pending, SupportFollowup.due_at <= now)
        .order_by(SupportFollowup.due_at.asc(), SupportFollowup.id.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def _get_outbox_by_key(db: AsyncSession, idempotency_key: str) -> MessageOutbox | None:
    result = await db.execute(select(MessageOutbox).where(MessageOutbox.idempotency_key == idempotency_key))
    return result.scalar_one_or_none()


async def _get_followup_by_key(db: AsyncSession, idempotency_key: str) -> SupportFollowup | None:
    result = await db.execute(select(SupportFollowup).where(SupportFollowup.idempotency_key == idempotency_key))
    return result.scalar_one_or_none()


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
