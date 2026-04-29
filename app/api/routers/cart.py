from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user
from app.core.errors import raise_error
from app.db.session import get_db
from app.models.user import User
from app.schemas.cart import CartItemCreate, CartItemOut, CartItemUpdate
from app.schemas.common import APIResponse
from app.services import cart as cart_service
from app.services.common import ServiceError

router = APIRouter(prefix="/cart", tags=["Cart"])


def _handle_error(exc: ServiceError):
    raise_error(exc.code, exc.message, status_code=exc.status_code)


@router.get("", response_model=APIResponse[list[CartItemOut]], summary="购物车列表")
async def list_cart_items(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        items = await cart_service.list_cart_items(db, current_user)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "购物车列表获取成功", "data": items}


@router.post("/items", response_model=APIResponse[CartItemOut], summary="加入购物车")
async def add_cart_item(
    payload: CartItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        item = await cart_service.add_cart_item(db, current_user, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "加入购物车成功", "data": item}


@router.patch("/items/{item_id}", response_model=APIResponse[CartItemOut], summary="更新购物车项")
async def update_cart_item(
    item_id: int,
    payload: CartItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        item = await cart_service.update_cart_item(db, current_user, item_id, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "购物车更新成功", "data": item}


@router.delete("/items/{item_id}", response_model=APIResponse[dict], summary="删除购物车项")
async def remove_cart_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await cart_service.remove_cart_item(db, current_user, item_id)
    except ServiceError as exc:
        _handle_error(exc)

    return {"code": "OK", "message": "购物车项删除成功", "data": {"item_id": item_id}}
