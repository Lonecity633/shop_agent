import json
from datetime import UTC, datetime
from secrets import randbelow

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.audit import append_audit
from app.models.order import Order, OrderStatus, OrderStatusLog, PayStatus
from app.models.payment import PaymentStatus, PaymentTransaction
from app.models.user import User, UserRole


def _generate_payment_no() -> str:
    return f"PAY{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}{randbelow(10000):04d}"


def _generate_provider_trade_no() -> str:
    return f"MOCKALIPAY{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}{randbelow(10000):04d}"


async def get_payment_by_no(db: AsyncSession, payment_no: str) -> PaymentTransaction | None:
    result = await db.execute(select(PaymentTransaction).where(PaymentTransaction.payment_no == payment_no))
    return result.scalar_one_or_none()


async def get_payment_for_update(db: AsyncSession, payment_no: str) -> PaymentTransaction | None:
    result = await db.execute(
        select(PaymentTransaction).where(PaymentTransaction.payment_no == payment_no).with_for_update()
    )
    return result.scalar_one_or_none()


async def list_payments_by_order(db: AsyncSession, order_id: int) -> list[PaymentTransaction]:
    result = await db.execute(
        select(PaymentTransaction)
        .where(PaymentTransaction.order_id == order_id)
        .order_by(PaymentTransaction.id.desc())
    )
    return list(result.scalars().all())


async def get_pending_payment_by_order(db: AsyncSession, order_id: int) -> PaymentTransaction | None:
    result = await db.execute(
        select(PaymentTransaction)
        .where(
            PaymentTransaction.order_id == order_id,
            PaymentTransaction.status == PaymentStatus.pending,
        )
        .order_by(PaymentTransaction.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_payment(
    db: AsyncSession,
    *,
    order: Order,
    buyer_id: int,
    channel: str,
) -> PaymentTransaction:
    payment = PaymentTransaction(
        payment_no=_generate_payment_no(),
        order_id=order.id,
        buyer_id=buyer_id,
        channel=channel,
        amount=order.pay_amount,
        status=PaymentStatus.pending,
    )
    db.add(payment)
    await db.flush()
    await append_audit(
        db,
        entity_type="payment",
        entity_id=payment.id,
        action="payment_initiated",
        actor_id=buyer_id,
        actor_role=UserRole.buyer.value,
        before_state={},
        after_state={
            "payment_no": payment.payment_no,
            "order_id": order.id,
            "status": payment.status.value,
            "amount": str(payment.amount),
            "channel": payment.channel,
        },
        reason="买家发起模拟支付",
    )
    await db.commit()
    await db.refresh(payment)
    return payment


async def mark_payment_failed(
    db: AsyncSession,
    *,
    payment: PaymentTransaction,
    order: Order,
    actor: User,
    failure_reason: str,
) -> PaymentTransaction:
    before_state = {
        "status": payment.status.value,
        "failure_reason": payment.failure_reason,
    }
    payment.status = PaymentStatus.failed
    payment.failure_reason = failure_reason or "模拟支付失败"
    payment.callback_payload = json.dumps(
        {"result": "failed", "failure_reason": payment.failure_reason},
        ensure_ascii=False,
    )
    db.add(
        OrderStatusLog(
            order_id=order.id,
            from_status=order.status.value,
            to_status=order.status.value,
            actor_id=actor.id,
            actor_role=actor.role.value,
            reason=f"模拟支付失败，流水号 {payment.payment_no}，原因：{payment.failure_reason}",
        )
    )
    await append_audit(
        db,
        entity_type="payment",
        entity_id=payment.id,
        action="payment_failed",
        actor_id=actor.id,
        actor_role=actor.role.value,
        before_state=before_state,
        after_state={
            "status": payment.status.value,
            "failure_reason": payment.failure_reason,
        },
        reason=payment.failure_reason,
    )
    await db.commit()
    await db.refresh(payment)
    return payment


async def mark_payment_succeeded(
    db: AsyncSession,
    *,
    payment: PaymentTransaction,
    order: Order,
    actor: User,
) -> PaymentTransaction:
    now = datetime.now(UTC)
    from_status = order.status
    before_payment = {
        "status": payment.status.value,
        "provider_trade_no": payment.provider_trade_no,
    }
    before_order = {
        "status": order.status.value,
        "pay_status": order.pay_status.value,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
    }

    payment.status = PaymentStatus.succeeded
    payment.failure_reason = ""
    payment.provider_trade_no = payment.provider_trade_no or _generate_provider_trade_no()
    payment.paid_at = payment.paid_at or now
    payment.callback_payload = json.dumps(
        {
            "result": "success",
            "provider_trade_no": payment.provider_trade_no,
        },
        ensure_ascii=False,
    )

    order_changed = not (order.status == OrderStatus.paid and order.pay_status == PayStatus.paid)
    if order_changed:
        order.status = OrderStatus.paid
        order.pay_status = PayStatus.paid
        order.pay_channel = payment.channel
        order.paid_at = order.paid_at or now
        db.add(
            OrderStatusLog(
                order_id=order.id,
                from_status=from_status.value,
                to_status=OrderStatus.paid.value,
                actor_id=actor.id,
                actor_role=actor.role.value,
                reason=f"模拟支付成功，流水号 {payment.payment_no}",
            )
        )

    await append_audit(
        db,
        entity_type="payment",
        entity_id=payment.id,
        action="payment_succeeded",
        actor_id=actor.id,
        actor_role=actor.role.value,
        before_state=before_payment,
        after_state={
            "status": payment.status.value,
            "provider_trade_no": payment.provider_trade_no,
            "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
        },
        reason="模拟支付回调成功",
    )
    if order_changed:
        await append_audit(
            db,
            entity_type="order",
            entity_id=order.id,
            action="order_paid",
            actor_id=actor.id,
            actor_role=actor.role.value,
            before_state=before_order,
            after_state={
                "status": order.status.value,
                "pay_status": order.pay_status.value,
                "pay_channel": order.pay_channel,
                "paid_at": order.paid_at.isoformat() if order.paid_at else None,
            },
            reason=f"支付渠道: {payment.channel}; 支付流水: {payment.payment_no}",
        )

    await db.commit()
    await db.refresh(payment)
    return payment
