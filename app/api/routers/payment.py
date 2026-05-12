from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user
from app.core.errors import raise_error
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.payment import MockPaymentCallbackPayload, PaymentInitiatePayload, PaymentTransactionOut
from app.services import payment as payment_service
from app.services.common import ServiceError

router = APIRouter(prefix="/payments", tags=["Payments"])


def _handle_error(exc: ServiceError):
    raise_error(exc.code, exc.message, status_code=exc.status_code)


@router.post("/orders/{order_no}/initiate", response_model=APIResponse[PaymentTransactionOut], summary="发起模拟支付")
async def initiate_payment(
    order_no: str,
    payload: PaymentInitiatePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        payment = await payment_service.initiate_payment(db, current_user, order_no, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "支付流水已创建", "data": payment}


@router.post("/{payment_no}/mock-callback", response_model=APIResponse[PaymentTransactionOut], summary="模拟支付回调")
async def mock_payment_callback(
    payment_no: str,
    payload: MockPaymentCallbackPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        payment = await payment_service.mock_callback(db, current_user, payment_no, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "模拟支付回调已处理", "data": payment}


@router.get("/orders/{order_no}", response_model=APIResponse[list[PaymentTransactionOut]], summary="查看订单支付流水")
async def list_order_payments(
    order_no: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        payments = await payment_service.list_order_payments(db, current_user, order_no)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "支付流水获取成功", "data": payments}
