from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import refund as refund_crud
from app.models.user import User, UserRole
from app.schemas.refund import RefundCreate, RefundSellerReview
from app.services.common import ServiceError, ensure


async def list_refunds(db: AsyncSession, current_user: User):
    return await refund_crud.list_refunds_by_role(db, current_user)


async def get_refund(db: AsyncSession, current_user: User, refund_id: int):
    data = await refund_crud.get_refund(db, refund_id)
    ensure(data is not None, "REFUND_NOT_FOUND", "退款单不存在", 404)

    if current_user.role == UserRole.buyer:
        ensure(data.buyer_id == current_user.id, "REFUND_FORBIDDEN", "无权限查看该退款单", 403)
    if current_user.role == UserRole.seller:
        ensure(data.seller_id == current_user.id, "REFUND_FORBIDDEN", "无权限查看该退款单", 403)

    return data


async def create_refund(db: AsyncSession, current_user: User, payload: RefundCreate):
    ensure(current_user.role == UserRole.buyer, "ROLE_DENIED", "仅买家可申请退款", 403)
    try:
        return await refund_crud.create_refund(db, payload, current_user)
    except PermissionError as exc:
        raise ServiceError("REFUND_FORBIDDEN", str(exc), 403) from exc
    except ValueError as exc:
        raise ServiceError("REFUND_CREATE_FAILED", str(exc), 400) from exc


async def seller_review_refund(db: AsyncSession, current_user: User, refund_id: int, payload: RefundSellerReview):
    ensure(current_user.role == UserRole.seller, "ROLE_DENIED", "仅卖家可审核退款", 403)
    refund = await refund_crud.get_refund(db, refund_id)
    ensure(refund is not None, "REFUND_NOT_FOUND", "退款单不存在", 404)
    ensure(refund.seller_id == current_user.id, "REFUND_FORBIDDEN", "仅订单所属卖家可审核退款", 403)

    try:
        return await refund_crud.seller_review_refund(db, refund, current_user, payload.action, payload.seller_note)
    except ValueError as exc:
        raise ServiceError("REFUND_REVIEW_FAILED", str(exc), 400) from exc
