from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user
from app.core.errors import raise_error
from app.crud import favorite as favorite_crud
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.common import APIResponse
from app.schemas.favorite import FavoriteCreate, FavoriteOut

router = APIRouter(prefix="/favorites", tags=["Favorites"])


def _ensure_buyer(current_user: User) -> None:
    if current_user.role != UserRole.buyer:
        raise_error("ROLE_DENIED", "仅买家可使用收藏功能", status_code=status.HTTP_403_FORBIDDEN)


@router.get("", response_model=APIResponse[list[FavoriteOut]], summary="收藏列表")
async def list_favorites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_buyer(current_user)
    favorites = await favorite_crud.list_favorites(db, current_user.id)
    return {"code": "OK", "message": "收藏列表获取成功", "data": favorites}


@router.post("", response_model=APIResponse[FavoriteOut], summary="添加收藏")
async def add_favorite(
    payload: FavoriteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_buyer(current_user)
    try:
        favorite = await favorite_crud.add_favorite(db, current_user.id, payload.product_id)
    except ValueError as exc:
        raise_error("FAVORITE_CREATE_FAILED", str(exc), status_code=400)
    return {"code": "OK", "message": "收藏成功", "data": favorite}


@router.delete("/{product_id}", response_model=APIResponse[dict], summary="取消收藏")
async def remove_favorite(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_buyer(current_user)
    removed = await favorite_crud.remove_favorite(db, current_user.id, product_id)
    return {
        "code": "OK",
        "message": "取消收藏成功" if removed else "该商品未收藏",
        "data": {"removed": removed, "product_id": product_id},
    }
