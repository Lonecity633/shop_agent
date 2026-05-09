from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.retrieval import delete_document, ingest_document
from app.crud import knowledge as kb_crud
from app.models.user import User, UserRole
from app.services.common import ServiceError, ensure


def _ensure_admin(current_user: User) -> None:
    ensure(current_user.role == UserRole.admin, "ROLE_DENIED", "仅管理员可访问知识库管理", 403)


async def upload_document(db: AsyncSession, current_user: User, title: str, content: str) -> dict:
    _ensure_admin(current_user)
    result = await ingest_document(db, title, content)
    doc = await kb_crud.get_document(db, result["document_id"])
    if doc is None:
        raise ServiceError("KB_DOCUMENT_NOT_FOUND", "文档创建失败", 500)
    return doc


async def list_documents(db: AsyncSession, current_user: User, page: int = 1, page_size: int = 20) -> dict:
    _ensure_admin(current_user)
    return await kb_crud.list_documents(db, page=page, page_size=page_size)


async def delete_document_by_id(db: AsyncSession, current_user: User, document_id: int) -> None:
    _ensure_admin(current_user)
    doc = await kb_crud.get_document(db, document_id)
    if doc is None:
        raise ServiceError("KB_DOCUMENT_NOT_FOUND", "文档不存在", 404)
    await delete_document(db, document_id)
