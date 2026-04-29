from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user
from app.core.errors import raise_error
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.favorite import FavoriteCreate, FavoriteOut
from app.services import favorite as favorite_service
from app.services.common import ServiceError

router = APIRouter(prefix="/favorites", tags=["Favorites"])


def _handle_error(exc: ServiceError):
    raise_error(exc.code, exc.message, status_code=exc.status_code)


@router.get("", response_model=APIResponse[list[FavoriteOut]], summary="收藏列表")
async def list_favorites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        favorites = await favorite_service.list_favorites(db, current_user)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "收藏列表获取成功", "data": favorites}


@router.post("", response_model=APIResponse[FavoriteOut], summary="添加收藏")
async def add_favorite(
    payload: FavoriteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        favorite = await favorite_service.add_favorite(db, current_user, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "收藏成功", "data": favorite}


@router.delete("/{product_id}", response_model=APIResponse[dict], summary="取消收藏")
async def remove_favorite(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        removed = await favorite_service.remove_favorite(db, current_user, product_id)
    except ServiceError as exc:
        _handle_error(exc)
    return {
        "code": "OK",
        "message": "取消收藏成功" if removed else "该商品未收藏",
        "data": {"removed": removed, "product_id": product_id},
    }
