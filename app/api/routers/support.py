from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user
from app.core.errors import raise_error
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.support import (
    SupportAutoReplyOut,
    SupportAutoReplyRequest,
    SupportMessageCreate,
    SupportMessageOut,
    SupportMessageRecordOut,
    SupportMySessionCreate,
    SupportOverviewOut,
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


@router.post("/me/sessions", response_model=APIResponse[SupportSessionOut])
async def create_my_support_session(
    payload: SupportMySessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await support_service.create_my_support_session(db, current_user, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "客服会话创建成功", "data": data}


@router.get("/me/sessions/latest", response_model=APIResponse[SupportSessionOut])
async def get_my_latest_support_session(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await support_service.get_my_latest_support_session(db, current_user)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "最近客服会话获取成功", "data": data}


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


@router.post("/sessions/{session_id}/reply", response_model=APIResponse[SupportAutoReplyOut])
async def auto_reply(
    session_id: int,
    payload: SupportAutoReplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await support_service.auto_reply(db, current_user, session_id, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "智能客服回复成功", "data": data}
