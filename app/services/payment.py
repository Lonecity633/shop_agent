from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import order as order_crud
from app.crud import payment as payment_crud
from app.models.order import OrderStatus, PayStatus
from app.models.payment import PaymentStatus, PaymentTransaction
from app.models.user import User, UserRole
from app.schemas.payment import MockPaymentCallbackPayload, PaymentInitiatePayload
from app.services.common import ensure


def _attach_order_no(payment: PaymentTransaction, order_no: str | None) -> PaymentTransaction:
    setattr(payment, "order_no", order_no)
    return payment


async def initiate_payment(
    db: AsyncSession,
    current_user: User,
    order_no: str,
    payload: PaymentInitiatePayload,
) -> PaymentTransaction:
    order = await order_crud.get_order_for_update_by_no(db, order_no)
    ensure(order is not None, "ORDER_NOT_FOUND", "订单不存在", 404)
    ensure(
        current_user.role == UserRole.buyer and order.user_id == current_user.id,
        "PAYMENT_FORBIDDEN",
        "仅订单买家可发起支付",
        403,
    )
    ensure(
        order.status == OrderStatus.pending_paid and order.pay_status == PayStatus.pending,
        "ORDER_NOT_PAYABLE",
        "仅待支付订单可发起支付",
        400,
    )

    pending = await payment_crud.get_pending_payment_by_order(db, order.id)
    if pending is not None:
        return _attach_order_no(pending, order.order_no)

    payment = await payment_crud.create_payment(
        db,
        order=order,
        buyer_id=current_user.id,
        channel=payload.channel,
    )
    return _attach_order_no(payment, order.order_no)


async def mock_callback(
    db: AsyncSession,
    current_user: User,
    payment_no: str,
    payload: MockPaymentCallbackPayload,
) -> PaymentTransaction:
    payment = await payment_crud.get_payment_for_update(db, payment_no)
    ensure(payment is not None, "PAYMENT_NOT_FOUND", "支付流水不存在", 404)
    ensure(
        current_user.role == UserRole.buyer and payment.buyer_id == current_user.id,
        "PAYMENT_FORBIDDEN",
        "仅支付买家可模拟回调",
        403,
    )

    order = await order_crud.get_order_for_update(db, payment.order_id)
    ensure(order is not None, "ORDER_NOT_FOUND", "订单不存在", 404)

    if payment.status == PaymentStatus.succeeded:
        return _attach_order_no(payment, order.order_no)
    if payment.status == PaymentStatus.failed:
        ensure(payload.result == "failed", "PAYMENT_FINALIZED", "失败流水不可再次改为成功", 400)
        return _attach_order_no(payment, order.order_no)
    ensure(payment.status == PaymentStatus.pending, "PAYMENT_FINALIZED", "该支付流水已结束", 400)

    if payload.result == "failed":
        updated = await payment_crud.mark_payment_failed(
            db,
            payment=payment,
            order=order,
            actor=current_user,
            failure_reason=payload.failure_reason,
        )
        return _attach_order_no(updated, order.order_no)

    ensure(
        (order.status == OrderStatus.pending_paid and order.pay_status == PayStatus.pending)
        or (order.status == OrderStatus.paid and order.pay_status == PayStatus.paid),
        "ORDER_NOT_PAYABLE",
        "订单当前状态不允许支付成功回调",
        400,
    )
    updated = await payment_crud.mark_payment_succeeded(
        db,
        payment=payment,
        order=order,
        actor=current_user,
    )
    return _attach_order_no(updated, order.order_no)


async def list_order_payments(db: AsyncSession, current_user: User, order_no: str) -> list[PaymentTransaction]:
    order = await order_crud.get_order_by_no(db, order_no)
    ensure(order is not None, "ORDER_NOT_FOUND", "订单不存在", 404)
    ensure(
        current_user.role == UserRole.admin
        or (current_user.role == UserRole.buyer and order.user_id == current_user.id),
        "PAYMENT_FORBIDDEN",
        "无权限查看该订单支付流水",
        403,
    )
    payments = await payment_crud.list_payments_by_order(db, order.id)
    for item in payments:
        _attach_order_no(item, order.order_no)
    return payments


async def pay_order_compat(
    db: AsyncSession,
    current_user: User,
    order_no: str,
    channel: str,
) -> PaymentTransaction:
    payment = await initiate_payment(
        db,
        current_user,
        order_no,
        PaymentInitiatePayload(channel=channel or "mock_alipay"),
    )
    return await mock_callback(
        db,
        current_user,
        payment.payment_no,
        MockPaymentCallbackPayload(result="success"),
    )
