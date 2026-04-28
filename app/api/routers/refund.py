from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user
from app.core.errors import raise_error
from app.crud import refund as refund_crud
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.common import APIResponse
from app.schemas.refund import RefundCreate, RefundOut, RefundSellerReview

router = APIRouter(prefix="/refunds", tags=["Refunds"])


@router.get("", response_model=APIResponse[list[RefundOut]])
async def list_refunds(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await refund_crud.list_refunds_by_role(db, current_user)
    return {"code": "OK", "message": "退款单列表获取成功", "data": data}


@router.get("/{refund_id}", response_model=APIResponse[RefundOut])
async def get_refund(
    refund_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await refund_crud.get_refund(db, refund_id)
    if not data:
        raise_error("REFUND_NOT_FOUND", "退款单不存在", status_code=404)

    if current_user.role == UserRole.buyer and data.buyer_id != current_user.id:
        raise_error("REFUND_FORBIDDEN", "无权限查看该退款单", status_code=403)
    if current_user.role == UserRole.seller and data.seller_id != current_user.id:
        raise_error("REFUND_FORBIDDEN", "无权限查看该退款单", status_code=403)

    return {"code": "OK", "message": "退款单获取成功", "data": data}


@router.post("", response_model=APIResponse[RefundOut])
async def create_refund(
    payload: RefundCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.buyer:
        raise_error("ROLE_DENIED", "仅买家可申请退款", status_code=403)

    try:
        data = await refund_crud.create_refund(db, payload, current_user)
    except PermissionError as exc:
        raise_error("REFUND_FORBIDDEN", str(exc), status_code=403)
    except ValueError as exc:
        raise_error("REFUND_CREATE_FAILED", str(exc), status_code=400)
    return {"code": "OK", "message": "退款申请提交成功", "data": data}


@router.patch("/{refund_id}/seller-review", response_model=APIResponse[RefundOut])
async def seller_review_refund(
    refund_id: int,
    payload: RefundSellerReview,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.seller:
        raise_error("ROLE_DENIED", "仅卖家可审核退款", status_code=403)

    refund = await refund_crud.get_refund(db, refund_id)
    if not refund:
        raise_error("REFUND_NOT_FOUND", "退款单不存在", status_code=404)
    if refund.seller_id != current_user.id:
        raise_error("REFUND_FORBIDDEN", "仅订单所属卖家可审核退款", status_code=403)

    try:
        data = await refund_crud.seller_review_refund(db, refund, current_user, payload.action, payload.seller_note)
    except ValueError as exc:
        raise_error("REFUND_REVIEW_FAILED", str(exc), status_code=400)
    return {"code": "OK", "message": "退款审核完成", "data": data}
