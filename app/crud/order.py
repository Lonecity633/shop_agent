import json
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.audit import append_audit
from app.models.category import Category
from app.models.address import UserAddress
from app.models.comment import Comment
from app.models.order import Order, OrderItem, OrderStatus, OrderStatusLog, PayStatus
from app.models.product import Product, ProductStatus
from app.models.user import User, UserRole
from app.schemas.order import OrderCommentCreate, OrderCreate, ShipOrderPayload


def _can_transition(from_status: OrderStatus, to_status: OrderStatus) -> bool:
    transitions = {
        OrderStatus.created: {OrderStatus.pending_paid, OrderStatus.paid, OrderStatus.cancelled, OrderStatus.closed},
        OrderStatus.pending_paid: {OrderStatus.paid, OrderStatus.cancelled, OrderStatus.closed},
        OrderStatus.paid: {OrderStatus.shipped, OrderStatus.cancelled, OrderStatus.closed},
        OrderStatus.shipped: {OrderStatus.completed},
        OrderStatus.completed: set(),
        OrderStatus.cancelled: set(),
        OrderStatus.closed: set(),
    }
    return to_status in transitions[from_status]


async def _append_status_log(
    db: AsyncSession,
    order: Order,
    from_status: OrderStatus,
    to_status: OrderStatus,
    actor: User,
    reason: str,
) -> None:
    db.add(
        OrderStatusLog(
            order_id=order.id,
            from_status=from_status.value,
            to_status=to_status.value,
            actor_id=actor.id,
            actor_role=actor.role.value,
            reason=reason,
        )
    )


def _serialize_address(address: UserAddress) -> str:
    return json.dumps(
        {
            "address_id": address.id,
            "receiver_name": address.receiver_name,
            "receiver_phone": address.receiver_phone,
            "province": address.province,
            "city": address.city,
            "district": address.district,
            "detail_address": address.detail_address,
        },
        ensure_ascii=False,
    )


def _serialize_placeholder_address() -> str:
    return json.dumps(
        {
            "address_id": None,
            "receiver_name": "未填写",
            "receiver_phone": "未填写",
            "province": "",
            "city": "",
            "district": "",
            "detail_address": "未填写收货地址",
        },
        ensure_ascii=False,
    )


async def create_order(db: AsyncSession, payload: OrderCreate, buyer_id: int) -> Order:
    product_result = await db.execute(select(Product).where(Product.id == payload.product_id).with_for_update())
    product = product_result.scalar_one_or_none()
    if product is None:
        raise ValueError("商品不存在")
    if product.is_deleted:
        raise ValueError("商品已下架，暂不可下单")
    if product.approval_status != ProductStatus.approved:
        raise ValueError("商品未审核通过，暂不可下单")
    category_result = await db.execute(select(Category.is_active).where(Category.id == product.category_id))
    category_is_active = category_result.scalar_one_or_none()
    if category_is_active is not True:
        raise ValueError("商品所属分类已停用，暂不可下单")

    if payload.address_id is not None:
        address_result = await db.execute(
            select(UserAddress).where(UserAddress.id == payload.address_id, UserAddress.user_id == buyer_id)
        )
        address = address_result.scalar_one_or_none()
    else:
        address_result = await db.execute(
            select(UserAddress)
            .where(UserAddress.user_id == buyer_id)
            .order_by(UserAddress.is_default.desc(), UserAddress.id.desc())
        )
        address = address_result.scalars().first()
    address_snapshot = _serialize_address(address) if address is not None else _serialize_placeholder_address()

    quantity = payload.quantity
    if product.stock < quantity:
        raise ValueError("商品库存不足")

    unit_price = Decimal(product.price)
    subtotal = unit_price * Decimal(quantity)
    product.stock -= quantity

    order = Order(
        user_id=buyer_id,
        product_id=payload.product_id,
        status=OrderStatus.pending_paid,
        pay_status=PayStatus.pending,
        total_price=subtotal,
        pay_amount=subtotal,
        pay_channel="simulated",
        address_snapshot=address_snapshot,
    )
    db.add(order)
    await db.flush()

    order_item = OrderItem(
        order_id=order.id,
        product_id=payload.product_id,
        product_name_snapshot=product.name,
        unit_price_snapshot=unit_price,
        quantity=quantity,
        subtotal=subtotal,
    )
    db.add(order_item)
    await append_audit(
        db,
        entity_type="order",
        entity_id=order.id,
        action="order_created",
        actor_id=buyer_id,
        actor_role=UserRole.buyer.value,
        before_state={},
        after_state={
            "status": order.status.value,
            "pay_status": order.pay_status.value,
            "inventory_reverted": order.inventory_reverted,
        },
        reason="买家创建订单",
    )

    await db.commit()
    loaded_order = await get_order(db, order.id)
    if loaded_order is None:
        raise ValueError("订单创建后读取失败")
    return loaded_order


async def pay_order(db: AsyncSession, order: Order, actor: User, pay_channel: str) -> Order:
    from_status = order.status
    from_pay_status = order.pay_status
    to_status = OrderStatus.paid
    if not _can_transition(from_status, to_status):
        raise ValueError(f"当前状态不允许支付: {from_status.value}")

    order.status = to_status
    order.pay_status = PayStatus.paid
    order.pay_channel = pay_channel
    order.paid_at = datetime.now(UTC)
    before_state = {"status": from_status.value, "pay_status": from_pay_status.value}
    after_state = {"status": to_status.value, "pay_status": PayStatus.paid.value}

    await _append_status_log(
        db,
        order=order,
        from_status=from_status,
        to_status=to_status,
        actor=actor,
        reason="买家完成支付",
    )
    await append_audit(
        db,
        entity_type="order",
        entity_id=order.id,
        action="order_paid",
        actor_id=actor.id,
        actor_role=actor.role.value,
        before_state=before_state,
        after_state=after_state,
        reason=f"支付渠道: {pay_channel}",
    )

    await db.commit()
    loaded_order = await get_order(db, order.id)
    if loaded_order is None:
        raise ValueError("订单支付后读取失败")
    return loaded_order


async def close_order(db: AsyncSession, order: Order, actor: User, reason: str) -> Order:
    from_status = order.status
    from_pay_status = order.pay_status
    to_status = OrderStatus.closed
    if not _can_transition(from_status, to_status):
        raise ValueError(f"当前状态不允许关闭: {from_status.value}")

    order.status = to_status
    order.pay_status = PayStatus.closed
    order.close_reason = reason
    restored = False
    if from_status in {OrderStatus.created, OrderStatus.pending_paid}:
        restored = await restore_inventory_if_needed(db, order)

    await _append_status_log(
        db,
        order=order,
        from_status=from_status,
        to_status=to_status,
        actor=actor,
        reason=reason,
    )
    await append_audit(
        db,
        entity_type="order",
        entity_id=order.id,
        action="order_closed",
        actor_id=actor.id,
        actor_role=actor.role.value,
        before_state={"status": from_status.value, "pay_status": from_pay_status.value},
        after_state={
            "status": to_status.value,
            "pay_status": PayStatus.closed.value,
            "inventory_reverted": order.inventory_reverted,
        },
        reason=f"{reason}；库存回补={restored}",
    )

    await db.commit()
    loaded_order = await get_order(db, order.id)
    if loaded_order is None:
        raise ValueError("订单关闭后读取失败")
    return loaded_order


async def list_orders_by_role(db: AsyncSession, current_user: User) -> list[Order]:
    stmt = select(Order).options(selectinload(Order.items)).order_by(Order.id.desc())
    if current_user.role == UserRole.buyer:
        stmt = stmt.where(Order.user_id == current_user.id)
    elif current_user.role == UserRole.seller:
        stmt = stmt.join(Product, Product.id == Order.product_id).where(Product.seller_id == current_user.id)

    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def get_order(db: AsyncSession, order_id: int) -> Order | None:
    result = await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    return result.scalar_one_or_none()


async def get_order_for_update(db: AsyncSession, order_id: int) -> Order | None:
    result = await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id).with_for_update()
    )
    return result.scalar_one_or_none()


async def update_order_status(
    db: AsyncSession,
    order: Order,
    status: OrderStatus,
    actor: User,
    reason: str,
) -> Order:
    from_status = order.status
    if not _can_transition(from_status, status):
        raise ValueError(f"非法状态流转: {from_status.value} -> {status.value}")

    order.status = status
    before_state = {"status": from_status.value, "pay_status": order.pay_status.value}
    if status in (OrderStatus.cancelled, OrderStatus.closed):
        order.close_reason = reason
        if order.pay_status == PayStatus.pending:
            order.pay_status = PayStatus.closed
            await restore_inventory_if_needed(db, order)
    if status == OrderStatus.completed:
        order.received_at = datetime.now(UTC)

    await _append_status_log(
        db,
        order=order,
        from_status=from_status,
        to_status=status,
        actor=actor,
        reason=reason,
    )
    await append_audit(
        db,
        entity_type="order",
        entity_id=order.id,
        action="order_status_updated",
        actor_id=actor.id,
        actor_role=actor.role.value,
        before_state=before_state,
        after_state={
            "status": order.status.value,
            "pay_status": order.pay_status.value,
            "inventory_reverted": order.inventory_reverted,
        },
        reason=reason,
    )

    await db.commit()
    loaded_order = await get_order(db, order.id)
    if loaded_order is None:
        raise ValueError("订单状态更新后读取失败")
    return loaded_order


async def ship_order(db: AsyncSession, order: Order, actor: User, payload: ShipOrderPayload) -> Order:
    from_status = order.status
    to_status = OrderStatus.shipped
    if not _can_transition(from_status, to_status):
        raise ValueError(f"当前状态不允许发货: {from_status.value}")

    if order.pay_status != PayStatus.paid:
        raise ValueError("订单未支付，暂不可发货")

    order.status = to_status
    order.tracking_no = payload.tracking_no
    order.logistics_company = payload.logistics_company
    order.shipped_at = datetime.now(UTC)

    await _append_status_log(
        db,
        order=order,
        from_status=from_status,
        to_status=to_status,
        actor=actor,
        reason="卖家发货",
    )
    await append_audit(
        db,
        entity_type="order",
        entity_id=order.id,
        action="order_shipped",
        actor_id=actor.id,
        actor_role=actor.role.value,
        before_state={"status": from_status.value, "pay_status": order.pay_status.value},
        after_state={"status": to_status.value, "pay_status": order.pay_status.value},
        reason=f"{payload.logistics_company}:{payload.tracking_no}",
    )

    await db.commit()
    loaded_order = await get_order(db, order.id)
    if loaded_order is None:
        raise ValueError("订单发货后读取失败")
    return loaded_order


async def receive_order(db: AsyncSession, order: Order, actor: User, reason: str) -> Order:
    return await update_order_status(
        db,
        order=order,
        status=OrderStatus.completed,
        actor=actor,
        reason=reason or "买家确认收货",
    )


async def list_order_logs(db: AsyncSession, order_id: int) -> list[OrderStatusLog]:
    result = await db.execute(
        select(OrderStatusLog).where(OrderStatusLog.order_id == order_id).order_by(OrderStatusLog.id.asc())
    )
    return list(result.scalars().all())


async def create_order_comment(
    db: AsyncSession,
    order: Order,
    current_user: User,
    payload: OrderCommentCreate,
) -> Comment:
    existing = await db.execute(select(Comment).where(Comment.order_id == order.id))
    if existing.scalar_one_or_none() is not None:
        raise ValueError("该订单已评论")
    if order.status != OrderStatus.completed:
        raise ValueError("仅已完成订单可评论")

    comment = Comment(
        order_id=order.id,
        product_id=order.product_id,
        user_id=current_user.id,
        rating=payload.rating,
        content=payload.content,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


async def delete_order(db: AsyncSession, order: Order) -> None:
    await db.delete(order)
    await db.commit()


async def restore_inventory_if_needed(db: AsyncSession, order: Order) -> bool:
    if order.inventory_reverted:
        return False

    item_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    order_items = item_result.scalars().all()
    if not order_items:
        order.inventory_reverted = True
        return True

    for item in order_items:
        product_result = await db.execute(select(Product).where(Product.id == item.product_id).with_for_update())
        product = product_result.scalar_one_or_none()
        if product is not None:
            product.stock += item.quantity

    order.inventory_reverted = True
    return True
