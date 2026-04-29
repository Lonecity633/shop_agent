from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user
from app.core.errors import raise_error
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.refund import RefundCreate, RefundOut, RefundSellerReview
from app.services import refund as refund_service
from app.services.common import ServiceError

router = APIRouter(prefix="/refunds", tags=["Refunds"])


def _handle_error(exc: ServiceError):
    raise_error(exc.code, exc.message, status_code=exc.status_code)


@router.get("", response_model=APIResponse[list[RefundOut]])
async def list_refunds(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await refund_service.list_refunds(db, current_user)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "退款单列表获取成功", "data": data}


@router.get("/{refund_id}", response_model=APIResponse[RefundOut])
async def get_refund(
    refund_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await refund_service.get_refund(db, current_user, refund_id)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "退款单获取成功", "data": data}


@router.post("", response_model=APIResponse[RefundOut])
async def create_refund(
    payload: RefundCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await refund_service.create_refund(db, current_user, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "退款申请提交成功", "data": data}


@router.patch("/{refund_id}/seller-review", response_model=APIResponse[RefundOut])
async def seller_review_refund(
    refund_id: int,
    payload: RefundSellerReview,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await refund_service.seller_review_refund(db, current_user, refund_id, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "退款审核完成", "data": data}
