from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.category import CategoryOut
from app.schemas.common import APIResponse
from app.services import category as category_service

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=APIResponse[list[CategoryOut]], summary="获取分类列表")
async def list_categories(db: AsyncSession = Depends(get_db)):
    categories = await category_service.list_active_categories(db)
    return {"code": "OK", "message": "分类列表获取成功", "data": categories}
