from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user
from app.core.errors import raise_error
from app.db.session import get_db
from app.models.user import User
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
from app.services import order as order_service
from app.services.common import ServiceError

router = APIRouter(prefix="/orders", tags=["Orders"])


def _handle_error(exc: ServiceError):
    raise_error(exc.code, exc.message, status_code=exc.status_code)


@router.post("", response_model=APIResponse[OrderOut], summary="创建订单（买家）")
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        order = await order_service.create_order(db, current_user, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "订单创建成功", "data": order}


@router.post("/{order_id}/pay", response_model=APIResponse[OrderOut], summary="模拟支付")
async def pay_order(
    order_id: int,
    payload: OrderPayPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        order = await order_service.pay_order(db, current_user, order_id, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "模拟支付成功", "data": order}


@router.post("/{order_id}/close", response_model=APIResponse[OrderOut], summary="关闭订单")
async def close_order(
    order_id: int,
    payload: OrderClosePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        order = await order_service.close_order(db, current_user, order_id, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "订单关闭成功", "data": order}


@router.get("", response_model=APIResponse[list[OrderOut]], summary="获取订单列表")
async def list_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        orders = await order_service.list_orders(db, current_user)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "订单列表获取成功", "data": orders}


@router.get("/{order_id}", response_model=APIResponse[OrderOut], summary="获取单个订单")
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        order = await order_service.get_order(db, current_user, order_id)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "订单获取成功", "data": order}


@router.get("/{order_id}/status", response_model=APIResponse[OrderStatusOut], summary="根据订单ID查询状态")
async def get_order_status(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await order_service.get_order_status(db, current_user, order_id)
    except ServiceError as exc:
        _handle_error(exc)

    return {
        "code": "OK",
        "message": "订单状态获取成功",
        "data": data,
    }


@router.patch("/{order_id}/status", response_model=APIResponse[OrderStatusOut], summary="买家取消订单")
async def patch_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await order_service.patch_order_status(db, current_user, order_id, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {
        "code": "OK",
        "message": "订单状态修改成功",
        "data": data,
    }


@router.post("/{order_id}/ship", response_model=APIResponse[OrderOut], summary="卖家发货")
async def ship_order(
    order_id: int,
    payload: ShipOrderPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        order = await order_service.ship_order(db, current_user, order_id, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "发货成功", "data": order}


@router.post("/{order_id}/receive", response_model=APIResponse[OrderOut], summary="买家确认收货")
async def receive_order(
    order_id: int,
    payload: ReceiveOrderPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        order = await order_service.receive_order(db, current_user, order_id, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "收货成功", "data": order}


@router.get("/{order_id}/logs", response_model=APIResponse[list[OrderStatusLogOut]], summary="订单状态日志")
async def get_order_logs(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logs = await order_service.get_order_logs(db, current_user, order_id)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "订单状态日志获取成功", "data": logs}


@router.post("/{order_id}/comments", response_model=APIResponse[OrderCommentOut], summary="买家评论")
async def create_order_comment(
    order_id: int,
    payload: OrderCommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        comment = await order_service.create_order_comment(db, current_user, order_id, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "评论成功", "data": comment}


@router.delete("/{order_id}", response_model=APIResponse[dict], summary="删除订单")
async def delete_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await order_service.delete_order(db, current_user, order_id)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "订单删除成功", "data": {"order_id": order_id}}
