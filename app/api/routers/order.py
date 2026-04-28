from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user
from app.core.config import settings
from app.core.errors import raise_error
from app.core.rate_limit import is_rate_limited
from app.crud import order as order_crud
from app.crud import product as product_crud
from app.db.session import get_db
from app.models.order import OrderStatus
from app.models.user import User, UserRole
from app.schemas.common import APIResponse
from app.schemas.order import (
    OrderClosePayload,
    OrderCommentCreate,
    OrderCommentOut,
    OrderCreate,
    OrderOut,
    OrderPayPayload,
    OrderStatusLogOut,
    OrderStatusOut,
    OrderStatusUpdate,
    ReceiveOrderPayload,
    ShipOrderPayload,
)

router = APIRouter(prefix="/orders", tags=["Orders"])


async def _ensure_order_access(db: AsyncSession, current_user: User, order):
    if current_user.role == UserRole.admin:
        return
    if current_user.role == UserRole.buyer and order.user_id == current_user.id:
        return
    if current_user.role == UserRole.seller:
        product = await product_crud.get_product(db, order.product_id)
        if product and product.seller_id == current_user.id:
            return
    raise_error("ORDER_FORBIDDEN", "无权限访问该订单", status_code=status.HTTP_403_FORBIDDEN)


@router.post("", response_model=APIResponse[OrderOut], summary="创建订单（买家）")
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.buyer:
        raise_error("ROLE_DENIED", "仅买家可下单", status_code=status.HTTP_403_FORBIDDEN)

    limited = await is_rate_limited(
        key=f"order:{current_user.id}",
        limit=settings.order_rate_limit_count,
        window_seconds=settings.order_rate_limit_window_seconds,
    )
    if limited:
        raise_error("ORDER_RATE_LIMITED", "下单频率过高，请稍后重试", status_code=429)

    try:
        order = await order_crud.create_order(db, payload, buyer_id=current_user.id)
    except ValueError as exc:
        raise_error("ORDER_CREATE_FAILED", str(exc), status_code=400)
    return {"code": "OK", "message": "订单创建成功", "data": order}


@router.post("/{order_id}/pay", response_model=APIResponse[OrderOut], summary="模拟支付")
async def pay_order(
    order_id: int,
    payload: OrderPayPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_crud.get_order(db, order_id)
    if not order:
        raise_error("ORDER_NOT_FOUND", "订单不存在", status_code=404)
    if current_user.role != UserRole.buyer or order.user_id != current_user.id:
        raise_error("ORDER_FORBIDDEN", "仅订单买家可支付", status_code=403)

    try:
        order = await order_crud.pay_order(db, order, current_user, payload.pay_channel)
    except ValueError as exc:
        raise_error("ORDER_NOT_PAYABLE", str(exc), status_code=400)
    return {"code": "OK", "message": "模拟支付成功", "data": order}


@router.post("/{order_id}/close", response_model=APIResponse[OrderOut], summary="关闭订单")
async def close_order(
    order_id: int,
    payload: OrderClosePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_crud.get_order(db, order_id)
    if not order:
        raise_error("ORDER_NOT_FOUND", "订单不存在", status_code=404)
    await _ensure_order_access(db, current_user, order)

    if current_user.role not in {UserRole.admin, UserRole.buyer}:
        raise_error("ROLE_DENIED", "当前角色不可关闭订单", status_code=403)

    try:
        order = await order_crud.close_order(db, order, current_user, payload.reason)
    except ValueError as exc:
        raise_error("ORDER_NOT_CLOSABLE", str(exc), status_code=400)
    return {"code": "OK", "message": "订单关闭成功", "data": order}


@router.get("", response_model=APIResponse[list[OrderOut]], summary="获取订单列表")
async def list_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    orders = await order_crud.list_orders_by_role(db, current_user)
    return {"code": "OK", "message": "订单列表获取成功", "data": orders}


@router.get("/{order_id}", response_model=APIResponse[OrderOut], summary="获取单个订单")
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_crud.get_order(db, order_id)
    if not order:
        raise_error("ORDER_NOT_FOUND", "订单不存在", status_code=404)
    await _ensure_order_access(db, current_user, order)
    return {"code": "OK", "message": "订单获取成功", "data": order}


@router.get("/{order_id}/status", response_model=APIResponse[OrderStatusOut], summary="根据订单ID查询状态")
async def get_order_status(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_crud.get_order(db, order_id)
    if not order:
        raise_error("ORDER_NOT_FOUND", "订单不存在", status_code=404)
    await _ensure_order_access(db, current_user, order)

    return {
        "code": "OK",
        "message": "订单状态获取成功",
        "data": {"order_id": order.id, "status": order.status.value},
    }


@router.patch("/{order_id}/status", response_model=APIResponse[OrderStatusOut], summary="买家取消订单")
async def patch_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_crud.get_order(db, order_id)
    if not order:
        raise_error("ORDER_NOT_FOUND", "订单不存在", status_code=404)
    if current_user.role != UserRole.buyer or order.user_id != current_user.id:
        raise_error("ORDER_FORBIDDEN", "仅订单买家可取消订单", status_code=403)

    try:
        order = await order_crud.update_order_status(
            db,
            order,
            status=OrderStatus(payload.status),
            actor=current_user,
            reason="买家取消订单",
        )
    except ValueError as exc:
        raise_error("ORDER_NOT_CANCELLABLE", str(exc), status_code=400)
    return {
        "code": "OK",
        "message": "订单状态修改成功",
        "data": {"order_id": order.id, "status": order.status.value},
    }


@router.post("/{order_id}/ship", response_model=APIResponse[OrderOut], summary="卖家发货")
async def ship_order(
    order_id: int,
    payload: ShipOrderPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_crud.get_order(db, order_id)
    if not order:
        raise_error("ORDER_NOT_FOUND", "订单不存在", status_code=404)
    if current_user.role != UserRole.seller:
        raise_error("ROLE_DENIED", "仅卖家可发货", status_code=403)

    product = await product_crud.get_product(db, order.product_id)
    if not product or product.seller_id != current_user.id:
        raise_error("ORDER_FORBIDDEN", "仅订单所属卖家可发货", status_code=403)

    try:
        order = await order_crud.ship_order(db, order, current_user, payload)
    except ValueError as exc:
        raise_error("ORDER_NOT_SHIPPABLE", str(exc), status_code=400)
    return {"code": "OK", "message": "发货成功", "data": order}


@router.post("/{order_id}/receive", response_model=APIResponse[OrderOut], summary="买家确认收货")
async def receive_order(
    order_id: int,
    payload: ReceiveOrderPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_crud.get_order(db, order_id)
    if not order:
        raise_error("ORDER_NOT_FOUND", "订单不存在", status_code=404)
    if current_user.role != UserRole.buyer or order.user_id != current_user.id:
        raise_error("ORDER_FORBIDDEN", "仅订单买家可确认收货", status_code=403)

    try:
        order = await order_crud.receive_order(db, order, current_user, payload.reason)
    except ValueError as exc:
        raise_error("ORDER_NOT_RECEIVABLE", str(exc), status_code=400)
    return {"code": "OK", "message": "收货成功", "data": order}


@router.get("/{order_id}/logs", response_model=APIResponse[list[OrderStatusLogOut]], summary="订单状态日志")
async def get_order_logs(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_crud.get_order(db, order_id)
    if not order:
        raise_error("ORDER_NOT_FOUND", "订单不存在", status_code=404)
    await _ensure_order_access(db, current_user, order)

    logs = await order_crud.list_order_logs(db, order_id)
    return {"code": "OK", "message": "订单状态日志获取成功", "data": logs}


@router.post("/{order_id}/comments", response_model=APIResponse[OrderCommentOut], summary="买家评论")
async def create_order_comment(
    order_id: int,
    payload: OrderCommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_crud.get_order(db, order_id)
    if not order:
        raise_error("ORDER_NOT_FOUND", "订单不存在", status_code=404)
    if current_user.role != UserRole.buyer or order.user_id != current_user.id:
        raise_error("ORDER_FORBIDDEN", "仅订单买家可评论", status_code=403)

    try:
        comment = await order_crud.create_order_comment(db, order, current_user, payload)
    except ValueError as exc:
        raise_error("ORDER_COMMENT_REJECTED", str(exc), status_code=400)
    return {"code": "OK", "message": "评论成功", "data": comment}


@router.delete("/{order_id}", response_model=APIResponse[dict], summary="删除订单")
async def delete_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_crud.get_order(db, order_id)
    if not order:
        raise_error("ORDER_NOT_FOUND", "订单不存在", status_code=404)
    await _ensure_order_access(db, current_user, order)

    await order_crud.delete_order(db, order)
    return {"code": "OK", "message": "订单删除成功", "data": {"order_id": order_id}}
