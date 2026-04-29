from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import favorite as favorite_crud
from app.models.user import User, UserRole
from app.schemas.favorite import FavoriteCreate
from app.services.common import ServiceError, ensure


def _ensure_buyer(current_user: User) -> None:
    ensure(current_user.role == UserRole.buyer, "ROLE_DENIED", "仅买家可使用收藏功能", 403)


async def list_favorites(db: AsyncSession, current_user: User):
    _ensure_buyer(current_user)
    return await favorite_crud.list_favorites(db, current_user.id)


async def add_favorite(db: AsyncSession, current_user: User, payload: FavoriteCreate):
    _ensure_buyer(current_user)
    try:
        return await favorite_crud.add_favorite(db, current_user.id, payload.product_id)
    except ValueError as exc:
        raise ServiceError("FAVORITE_CREATE_FAILED", str(exc), 400) from exc


async def remove_favorite(db: AsyncSession, current_user: User, product_id: int):
    _ensure_buyer(current_user)
    return await favorite_crud.remove_favorite(db, current_user.id, product_id)
