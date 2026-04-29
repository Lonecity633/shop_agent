from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import cart as cart_crud
from app.models.user import User, UserRole
from app.schemas.cart import CartItemCreate, CartItemUpdate
from app.services.common import ServiceError, ensure


def _ensure_buyer(current_user: User) -> None:
    ensure(current_user.role == UserRole.buyer, "ROLE_DENIED", "仅买家可使用购物车", 403)


async def list_cart_items(db: AsyncSession, current_user: User):
    _ensure_buyer(current_user)
    return await cart_crud.list_cart_items(db, current_user.id)


async def add_cart_item(db: AsyncSession, current_user: User, payload: CartItemCreate):
    _ensure_buyer(current_user)
    try:
        return await cart_crud.add_cart_item(db, current_user.id, payload.product_id, payload.quantity)
    except ValueError as exc:
        raise ServiceError("CART_ADD_FAILED", str(exc), 400) from exc


async def update_cart_item(db: AsyncSession, current_user: User, item_id: int, payload: CartItemUpdate):
    _ensure_buyer(current_user)
    item = await cart_crud.get_cart_item(db, item_id)
    ensure(item is not None and item.user_id == current_user.id, "CART_ITEM_NOT_FOUND", "购物车项不存在", 404)
    ensure(payload.quantity is not None or payload.selected is not None, "CART_UPDATE_EMPTY", "请提供 quantity 或 selected", 400)
    try:
        return await cart_crud.update_cart_item(db, item, quantity=payload.quantity, selected=payload.selected)
    except ValueError as exc:
        raise ServiceError("CART_UPDATE_FAILED", str(exc), 400) from exc


async def remove_cart_item(db: AsyncSession, current_user: User, item_id: int):
    _ensure_buyer(current_user)
    item = await cart_crud.get_cart_item(db, item_id)
    ensure(item is not None and item.user_id == current_user.id, "CART_ITEM_NOT_FOUND", "购物车项不存在", 404)
    await cart_crud.remove_cart_item(db, item)
