from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user
from app.core.errors import raise_error
from app.crud import support as support_crud
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.common import APIResponse
from app.schemas.support import (
    SupportOverviewOut,
    SupportSessionCreate,
    SupportSessionOut,
    SupportTimelineOut,
)

router = APIRouter(prefix="/support", tags=["Support"])


def ensure_support_or_admin(current_user: User) -> None:
    if current_user.role != UserRole.admin:
        raise_error("ROLE_DENIED", "仅管理员可访问客服聚合接口", status_code=403)


@router.get("/users/{user_id}/overview", response_model=APIResponse[SupportOverviewOut])
async def get_user_overview(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_support_or_admin(current_user)
    try:
        data = await support_crud.get_user_overview(db, user_id)
    except ValueError as exc:
        raise_error("USER_NOT_FOUND", str(exc), status_code=404)
    return {"code": "OK", "message": "用户概览获取成功", "data": data}


@router.get("/orders/{order_id}/timeline", response_model=APIResponse[SupportTimelineOut])
async def get_order_timeline(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_support_or_admin(current_user)
    try:
        data = await support_crud.get_order_timeline(db, order_id)
    except ValueError as exc:
        raise_error("ORDER_NOT_FOUND", str(exc), status_code=404)
    return {"code": "OK", "message": "订单时间线获取成功", "data": data}


@router.post("/sessions", response_model=APIResponse[SupportSessionOut])
async def create_support_session(
    payload: SupportSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_support_or_admin(current_user)
    try:
        data = await support_crud.create_support_session(db, current_user.id, payload)
    except ValueError as exc:
        raise_error("USER_NOT_FOUND", str(exc), status_code=404)
    return {"code": "OK", "message": "客服会话记录成功", "data": data}
