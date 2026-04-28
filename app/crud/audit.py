import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operation_audit import OperationAudit


async def append_audit(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: int,
    action: str,
    actor_id: int,
    actor_role: str,
    before_state: dict | None = None,
    after_state: dict | None = None,
    reason: str = "",
) -> None:
    audit = OperationAudit(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        actor_role=actor_role,
        before_state=json.dumps(before_state or {}, ensure_ascii=False),
        after_state=json.dumps(after_state or {}, ensure_ascii=False),
        reason=reason or "",
    )
    db.add(audit)


async def list_timeline(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: int,
    limit: int = 200,
) -> list[OperationAudit]:
    stmt = (
        select(OperationAudit)
        .where(OperationAudit.entity_type == entity_type, OperationAudit.entity_id == entity_id)
        .order_by(OperationAudit.id.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

