from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user
from app.core.errors import raise_error
from app.crud import cart as cart_crud
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.cart import CartItemCreate, CartItemOut, CartItemUpdate
from app.schemas.common import APIResponse

router = APIRouter(prefix="/cart", tags=["Cart"])


def _ensure_buyer(current_user: User) -> None:
    if current_user.role != UserRole.buyer:
        raise_error("ROLE_DENIED", "仅买家可使用购物车", status_code=status.HTTP_403_FORBIDDEN)


@router.get("", response_model=APIResponse[list[CartItemOut]], summary="购物车列表")
async def list_cart_items(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_buyer(current_user)
    items = await cart_crud.list_cart_items(db, current_user.id)
    return {"code": "OK", "message": "购物车列表获取成功", "data": items}


@router.post("/items", response_model=APIResponse[CartItemOut], summary="加入购物车")
async def add_cart_item(
    payload: CartItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_buyer(current_user)
    try:
        item = await cart_crud.add_cart_item(db, current_user.id, payload.product_id, payload.quantity)
    except ValueError as exc:
        raise_error("CART_ADD_FAILED", str(exc), status_code=400)
    return {"code": "OK", "message": "加入购物车成功", "data": item}


@router.patch("/items/{item_id}", response_model=APIResponse[CartItemOut], summary="更新购物车项")
async def update_cart_item(
    item_id: int,
    payload: CartItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_buyer(current_user)
    item = await cart_crud.get_cart_item(db, item_id)
    if item is None or item.user_id != current_user.id:
        raise_error("CART_ITEM_NOT_FOUND", "购物车项不存在", status_code=404)

    if payload.quantity is None and payload.selected is None:
        raise_error("CART_UPDATE_EMPTY", "请提供 quantity 或 selected", status_code=400)

    try:
        item = await cart_crud.update_cart_item(db, item, quantity=payload.quantity, selected=payload.selected)
    except ValueError as exc:
        raise_error("CART_UPDATE_FAILED", str(exc), status_code=400)
    return {"code": "OK", "message": "购物车更新成功", "data": item}


@router.delete("/items/{item_id}", response_model=APIResponse[dict], summary="删除购物车项")
async def remove_cart_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_buyer(current_user)
    item = await cart_crud.get_cart_item(db, item_id)
    if item is None or item.user_id != current_user.id:
        raise_error("CART_ITEM_NOT_FOUND", "购物车项不存在", status_code=404)

    await cart_crud.remove_cart_item(db, item)
    return {"code": "OK", "message": "购物车项删除成功", "data": {"item_id": item_id}}
