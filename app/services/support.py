from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import kb as kb_crud
from app.crud import support as support_crud
from app.models.user import User, UserRole
from app.schemas.kb import KBDocumentCreate
from app.schemas.support import SupportMessageCreate, SupportSessionCreate
from app.services.common import ServiceError, ensure


def ensure_support_or_admin(current_user: User) -> None:
    ensure(current_user.role == UserRole.admin, "ROLE_DENIED", "仅管理员可访问客服聚合接口", 403)


async def get_user_overview(db: AsyncSession, current_user: User, user_id: int):
    ensure_support_or_admin(current_user)
    try:
        return await support_crud.get_user_overview(db, user_id)
    except ValueError as exc:
        raise ServiceError("USER_NOT_FOUND", str(exc), 404) from exc


async def get_order_timeline(db: AsyncSession, current_user: User, order_id: int):
    ensure_support_or_admin(current_user)
    try:
        return await support_crud.get_order_timeline(db, order_id)
    except ValueError as exc:
        raise ServiceError("ORDER_NOT_FOUND", str(exc), 404) from exc


async def create_support_session(db: AsyncSession, current_user: User, payload: SupportSessionCreate):
    ensure_support_or_admin(current_user)
    try:
        return await support_crud.create_support_session(db, current_user.id, payload)
    except ValueError as exc:
        raise ServiceError("USER_NOT_FOUND", str(exc), 404) from exc


async def create_support_message(db: AsyncSession, current_user: User, session_id: int, payload: SupportMessageCreate):
    ensure_support_or_admin(current_user)
    try:
        return await support_crud.create_support_message(db, session_id, payload)
    except ValueError as exc:
        status_code = 404 if "会话不存在" in str(exc) else 400
        raise ServiceError("SUPPORT_MESSAGE_CREATE_FAILED", str(exc), status_code) from exc


async def get_support_messages(db: AsyncSession, current_user: User, session_id: int):
    ensure_support_or_admin(current_user)
    try:
        return await support_crud.list_support_messages(db, session_id)
    except ValueError as exc:
        raise ServiceError("SUPPORT_SESSION_NOT_FOUND", str(exc), 404) from exc


async def get_support_evidence(db: AsyncSession, current_user: User, session_id: int):
    ensure_support_or_admin(current_user)
    try:
        return await support_crud.list_support_evidence(db, session_id)
    except ValueError as exc:
        raise ServiceError("SUPPORT_SESSION_NOT_FOUND", str(exc), 404) from exc


async def create_kb_document(db: AsyncSession, current_user: User, payload: KBDocumentCreate):
    ensure_support_or_admin(current_user)
    return await kb_crud.create_document(db, payload)


async def get_kb_documents(
    db: AsyncSession,
    current_user: User,
    *,
    status: str | None,
    keyword: str | None,
    limit: int,
):
    ensure_support_or_admin(current_user)
    return await kb_crud.list_documents(db, status=status, keyword=keyword, limit=limit)
