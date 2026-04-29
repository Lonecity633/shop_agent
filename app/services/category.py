from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import category as category_crud


async def list_active_categories(db: AsyncSession):
    return await category_crud.list_active_categories(db)
