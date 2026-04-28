from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.audit import append_audit
from app.crud.order import restore_inventory_if_needed
from app.models.order import Order, OrderStatus, PayStatus
from app.models.product import Product
from app.models.refund import RefundStatus, RefundTicket
from app.models.user import User, UserRole
from app.schemas.refund import RefundCreate


async def get_refund(db: AsyncSession, refund_id: int) -> RefundTicket | None:
    result = await db.execute(select(RefundTicket).where(RefundTicket.id == refund_id))
    return result.scalar_one_or_none()


async def list_refunds_by_role(db: AsyncSession, current_user: User) -> list[RefundTicket]:
    stmt = select(RefundTicket).order_by(RefundTicket.id.desc())
    if current_user.role == UserRole.buyer:
        stmt = stmt.where(RefundTicket.buyer_id == current_user.id)
    elif current_user.role == UserRole.seller:
        stmt = stmt.where(RefundTicket.seller_id == current_user.id)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_refund(db: AsyncSession, payload: RefundCreate, buyer: User) -> RefundTicket:
    order_result = await db.execute(select(Order).where(Order.id == payload.order_id).with_for_update())
    order = order_result.scalar_one_or_none()
    if order is None:
        raise ValueError("订单不存在")
    if order.user_id != buyer.id:
        raise PermissionError("仅订单买家可申请退款")
    if order.pay_status != PayStatus.paid:
        raise ValueError("仅已支付订单可申请退款")
    if order.status == OrderStatus.shipped:
        raise ValueError("已发货订单暂不支持本版退款")

    existing = await db.execute(
        select(RefundTicket).where(
            RefundTicket.order_id == order.id,
            RefundTicket.status.in_(
                [
                    RefundStatus.requested,
                    RefundStatus.approved_pending_refund,
                    RefundStatus.seller_approved,
                ]
            ),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError("该订单已有进行中的退款申请")

    product_result = await db.execute(select(Product).where(Product.id == order.product_id))
    product = product_result.scalar_one_or_none()
    if product is None:
        raise ValueError("订单商品不存在")

    refund = RefundTicket(
        order_id=order.id,
        buyer_id=buyer.id,
        seller_id=product.seller_id,
        status=RefundStatus.requested,
        amount=order.pay_amount,
        reason=payload.reason,
        buyer_note=payload.buyer_note,
    )
    db.add(refund)
    await db.flush()
    await append_audit(
        db,
        entity_type="refund",
        entity_id=refund.id,
        action="refund_created",
        actor_id=buyer.id,
        actor_role=buyer.role.value,
        before_state={},
        after_state={"status": refund.status.value, "amount": str(refund.amount)},
        reason=payload.reason,
    )
    await db.commit()
    await db.refresh(refund)
    return refund


async def seller_review_refund(
    db: AsyncSession,
    refund: RefundTicket,
    actor: User,
    action: str,
    seller_note: str,
) -> RefundTicket:
    if refund.status != RefundStatus.requested:
        raise ValueError("退款单当前状态不支持卖家审核")

    before_state = {"status": refund.status.value, "seller_note": refund.seller_note}
    if action == "approve":
        refund.status = RefundStatus.approved_pending_refund
        refund.seller_note = seller_note
    else:
        refund.status = RefundStatus.seller_rejected
        refund.seller_note = seller_note

    await append_audit(
        db,
        entity_type="refund",
        entity_id=refund.id,
        action="refund_seller_review",
        actor_id=actor.id,
        actor_role=actor.role.value,
        before_state=before_state,
        after_state={"status": refund.status.value, "seller_note": refund.seller_note},
        reason=seller_note,
    )
    await db.commit()
    await db.refresh(refund)
    return refund


async def admin_review_refund(
    db: AsyncSession,
    refund: RefundTicket,
    actor: User,
    action: str,
    admin_note: str,
) -> RefundTicket:
    if refund.status not in {
        RefundStatus.requested,
        RefundStatus.seller_rejected,
        RefundStatus.approved_pending_refund,
        RefundStatus.seller_approved,
    }:
        raise ValueError("退款单当前状态不支持管理员仲裁")

    before_state = {"status": refund.status.value, "admin_note": refund.admin_note}
    if action == "approve":
        refund.status = RefundStatus.approved_pending_refund
    else:
        refund.status = RefundStatus.closed

    refund.admin_note = admin_note
    await append_audit(
        db,
        entity_type="refund",
        entity_id=refund.id,
        action="refund_admin_review",
        actor_id=actor.id,
        actor_role=actor.role.value,
        before_state=before_state,
        after_state={"status": refund.status.value, "admin_note": refund.admin_note},
        reason=admin_note,
    )

    await db.commit()
    await db.refresh(refund)
    return refund


async def execute_refund(
    db: AsyncSession,
    refund: RefundTicket,
    *,
    actor: User,
    result: str,
    fail_reason: str,
) -> RefundTicket:
    if refund.status not in {RefundStatus.approved_pending_refund, RefundStatus.seller_approved}:
        raise ValueError("仅待执行退款状态可执行退款")

    refund_before = {
        "status": refund.status.value,
        "processed_at": refund.processed_at.isoformat() if refund.processed_at else None,
    }
    order_result = await db.execute(select(Order).where(Order.id == refund.order_id).with_for_update())
    order = order_result.scalar_one_or_none()
    order_before = (
        {
            "status": order.status.value,
            "pay_status": order.pay_status.value,
            "inventory_reverted": order.inventory_reverted,
        }
        if order is not None
        else None
    )

    if result == "success":
        refund.status = RefundStatus.refunded
        refund.fail_reason = ""
        refund.processed_at = datetime.now(UTC)

        if order is not None:
            if order.status in {OrderStatus.created, OrderStatus.pending_paid, OrderStatus.paid, OrderStatus.cancelled, OrderStatus.closed}:
                await restore_inventory_if_needed(db, order)
            order.status = OrderStatus.cancelled
            order.pay_status = PayStatus.refunded
            order.close_reason = "退款完成"
        action = "refund_executed_success"
    else:
        refund.status = RefundStatus.refund_failed
        refund.fail_reason = fail_reason
        refund.processed_at = datetime.now(UTC)
        action = "refund_executed_failed"

    await append_audit(
        db,
        entity_type="refund",
        entity_id=refund.id,
        action=action,
        actor_id=actor.id,
        actor_role=actor.role.value,
        before_state=refund_before,
        after_state={
            "status": refund.status.value,
            "fail_reason": refund.fail_reason,
            "processed_at": refund.processed_at.isoformat() if refund.processed_at else None,
        },
        reason=fail_reason or "模拟退款执行",
    )
    if order is not None:
        await append_audit(
            db,
            entity_type="order",
            entity_id=order.id,
            action="refund_applied_to_order",
            actor_id=actor.id,
            actor_role=actor.role.value,
            before_state=order_before or {},
            after_state={
                "status": order.status.value,
                "pay_status": order.pay_status.value,
                "inventory_reverted": order.inventory_reverted,
            },
            reason="退款单执行完成后同步订单状态",
        )

    await db.commit()
    await db.refresh(refund)
    return refund
