from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import is_rate_limited
from app.crud import order as order_crud
from app.crud import product as product_crud
from app.models.order import OrderStatus
from app.models.user import User, UserRole
from app.schemas.order import (
    OrderClosePayload,
    OrderCommentCreate,
    OrderCreate,
    OrderPayPayload,
    OrderStatusUpdate,
    ReceiveOrderPayload,
    ShipOrderPayload,
)
from app.services.common import ServiceError, ensure


async def _ensure_order_access(db: AsyncSession, current_user: User, order):
    if current_user.role == UserRole.admin:
        return
    if current_user.role == UserRole.buyer and order.user_id == current_user.id:
        return
    if current_user.role == UserRole.seller:
        product = await product_crud.get_product(db, order.product_id)
        if product and product.seller_id == current_user.id:
            return
    raise ServiceError("ORDER_FORBIDDEN", "无权限访问该订单", 403)


async def create_order(db: AsyncSession, current_user: User, payload: OrderCreate):
    ensure(current_user.role == UserRole.buyer, "ROLE_DENIED", "仅买家可下单", 403)

    try:
        limited = await is_rate_limited(
            key=f"order:{current_user.id}",
            limit=settings.order_rate_limit_count,
            window_seconds=settings.order_rate_limit_window_seconds,
        )
    except RuntimeError as exc:
        raise ServiceError("AUTH_BACKEND_UNAVAILABLE", "下单限流服务暂不可用，请稍后再试", 503) from exc
    ensure(not limited, "ORDER_RATE_LIMITED", "下单频率过高，请稍后重试", 429)

    try:
        return await order_crud.create_order(db, payload, buyer_id=current_user.id)
    except ValueError as exc:
        raise ServiceError("ORDER_CREATE_FAILED", str(exc), 400) from exc


async def pay_order(db: AsyncSession, current_user: User, order_id: int, payload: OrderPayPayload):
    order = await order_crud.get_order_for_update(db, order_id)
    ensure(order is not None, "ORDER_NOT_FOUND", "订单不存在", 404)
    ensure(current_user.role == UserRole.buyer and order.user_id == current_user.id, "ORDER_FORBIDDEN", "仅订单买家可支付", 403)

    try:
        return await order_crud.pay_order(db, order, current_user, payload.pay_channel)
    except ValueError as exc:
        raise ServiceError("ORDER_NOT_PAYABLE", str(exc), 400) from exc


async def close_order(db: AsyncSession, current_user: User, order_id: int, payload: OrderClosePayload):
    order = await order_crud.get_order_for_update(db, order_id)
    ensure(order is not None, "ORDER_NOT_FOUND", "订单不存在", 404)
    await _ensure_order_access(db, current_user, order)

    ensure(current_user.role in {UserRole.admin, UserRole.buyer}, "ROLE_DENIED", "当前角色不可关闭订单", 403)
    try:
        return await order_crud.close_order(db, order, current_user, payload.reason)
    except ValueError as exc:
        raise ServiceError("ORDER_NOT_CLOSABLE", str(exc), 400) from exc


async def list_orders(db: AsyncSession, current_user: User):
    return await order_crud.list_orders_by_role(db, current_user)


async def get_order(db: AsyncSession, current_user: User, order_id: int):
    order = await order_crud.get_order(db, order_id)
    ensure(order is not None, "ORDER_NOT_FOUND", "订单不存在", 404)
    await _ensure_order_access(db, current_user, order)
    return order


async def get_order_status(db: AsyncSession, current_user: User, order_id: int):
    order = await get_order(db, current_user, order_id)
    return {"order_id": order.id, "status": order.status.value}


async def patch_order_status(db: AsyncSession, current_user: User, order_id: int, payload: OrderStatusUpdate):
    order = await order_crud.get_order_for_update(db, order_id)
    ensure(order is not None, "ORDER_NOT_FOUND", "订单不存在", 404)
    ensure(current_user.role == UserRole.buyer and order.user_id == current_user.id, "ORDER_FORBIDDEN", "仅订单买家可取消订单", 403)

    try:
        order = await order_crud.update_order_status(
            db,
            order,
            status=OrderStatus(payload.status),
            actor=current_user,
            reason="买家取消订单",
        )
    except ValueError as exc:
        raise ServiceError("ORDER_NOT_CANCELLABLE", str(exc), 400) from exc

    return {"order_id": order.id, "status": order.status.value}


async def ship_order(db: AsyncSession, current_user: User, order_id: int, payload: ShipOrderPayload):
    order = await order_crud.get_order_for_update(db, order_id)
    ensure(order is not None, "ORDER_NOT_FOUND", "订单不存在", 404)
    ensure(current_user.role == UserRole.seller, "ROLE_DENIED", "仅卖家可发货", 403)

    product = await product_crud.get_product(db, order.product_id)
    ensure(product is not None and product.seller_id == current_user.id, "ORDER_FORBIDDEN", "仅订单所属卖家可发货", 403)

    try:
        return await order_crud.ship_order(db, order, current_user, payload)
    except ValueError as exc:
        raise ServiceError("ORDER_NOT_SHIPPABLE", str(exc), 400) from exc


async def receive_order(db: AsyncSession, current_user: User, order_id: int, payload: ReceiveOrderPayload):
    order = await order_crud.get_order_for_update(db, order_id)
    ensure(order is not None, "ORDER_NOT_FOUND", "订单不存在", 404)
    ensure(current_user.role == UserRole.buyer and order.user_id == current_user.id, "ORDER_FORBIDDEN", "仅订单买家可确认收货", 403)

    try:
        return await order_crud.receive_order(db, order, current_user, payload.reason)
    except ValueError as exc:
        raise ServiceError("ORDER_NOT_RECEIVABLE", str(exc), 400) from exc


async def get_order_logs(db: AsyncSession, current_user: User, order_id: int):
    order = await order_crud.get_order(db, order_id)
    ensure(order is not None, "ORDER_NOT_FOUND", "订单不存在", 404)
    await _ensure_order_access(db, current_user, order)
    return await order_crud.list_order_logs(db, order_id)


async def create_order_comment(db: AsyncSession, current_user: User, order_id: int, payload: OrderCommentCreate):
    order = await order_crud.get_order(db, order_id)
    ensure(order is not None, "ORDER_NOT_FOUND", "订单不存在", 404)
    ensure(current_user.role == UserRole.buyer and order.user_id == current_user.id, "ORDER_FORBIDDEN", "仅订单买家可评论", 403)

    try:
        return await order_crud.create_order_comment(db, order, current_user, payload)
    except ValueError as exc:
        raise ServiceError("ORDER_COMMENT_REJECTED", str(exc), 400) from exc


async def delete_order(db: AsyncSession, current_user: User, order_id: int):
    order = await order_crud.get_order(db, order_id)
    ensure(order is not None, "ORDER_NOT_FOUND", "订单不存在", 404)
    await _ensure_order_access(db, current_user, order)
    raise ServiceError("ORDER_DELETE_FORBIDDEN", "订单不允许物理删除", 403)
