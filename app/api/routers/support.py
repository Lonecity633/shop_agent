from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user
from app.core.errors import raise_error
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.kb import KBDocumentCreate, KBDocumentOut
from app.schemas.support import (
    SupportMessageCreate,
    SupportMessageOut,
    SupportMessageRecordOut,
    SupportOverviewOut,
    SupportRetrievalLogOut,
    SupportSessionCreate,
    SupportSessionOut,
    SupportTimelineOut,
)
from app.services import support as support_service
from app.services.common import ServiceError

router = APIRouter(prefix="/support", tags=["Support"])


def _handle_error(exc: ServiceError):
    raise_error(exc.code, exc.message, status_code=exc.status_code)


@router.get("/users/{user_id}/overview", response_model=APIResponse[SupportOverviewOut])
async def get_user_overview(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await support_service.get_user_overview(db, current_user, user_id)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "用户概览获取成功", "data": data}


@router.get("/orders/{order_id}/timeline", response_model=APIResponse[SupportTimelineOut])
async def get_order_timeline(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await support_service.get_order_timeline(db, current_user, order_id)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "订单时间线获取成功", "data": data}


@router.post("/sessions", response_model=APIResponse[SupportSessionOut])
async def create_support_session(
    payload: SupportSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await support_service.create_support_session(db, current_user, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "客服会话记录成功", "data": data}


@router.post("/sessions/{session_id}/messages", response_model=APIResponse[SupportMessageRecordOut])
async def create_support_message(
    session_id: int,
    payload: SupportMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await support_service.create_support_message(db, current_user, session_id, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "会话消息记录成功", "data": data}


@router.get("/sessions/{session_id}/messages", response_model=APIResponse[list[SupportMessageOut]])
async def get_support_messages(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await support_service.get_support_messages(db, current_user, session_id)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "会话消息获取成功", "data": data}


@router.get("/sessions/{session_id}/evidence", response_model=APIResponse[list[SupportRetrievalLogOut]])
async def get_support_evidence(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await support_service.get_support_evidence(db, current_user, session_id)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "检索证据获取成功", "data": data}


@router.post("/kb/documents", response_model=APIResponse[KBDocumentOut])
async def create_kb_document(
    payload: KBDocumentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await support_service.create_kb_document(db, current_user, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "知识库文档创建成功", "data": data}


@router.get("/kb/documents", response_model=APIResponse[list[KBDocumentOut]])
async def get_kb_documents(
    status: str | None = Query(default=None, description="文档状态过滤"),
    keyword: str | None = Query(default=None, description="标题关键词"),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await support_service.get_kb_documents(
            db,
            current_user,
            status=status,
            keyword=keyword,
            limit=limit,
        )
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "知识库文档列表获取成功", "data": data}
