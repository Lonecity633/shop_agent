from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.favorite import Favorite
from app.models.product import Product, ProductStatus


async def list_favorites(db: AsyncSession, user_id: int) -> list[Favorite]:
    result = await db.execute(
        select(Favorite)
        .options(selectinload(Favorite.product).selectinload(Product.category))
        .where(Favorite.user_id == user_id)
        .order_by(Favorite.id.desc())
    )
    return list(result.scalars().all())


async def get_favorite_by_user_product(db: AsyncSession, user_id: int, product_id: int) -> Favorite | None:
    result = await db.execute(
        select(Favorite).where(Favorite.user_id == user_id, Favorite.product_id == product_id)
    )
    return result.scalar_one_or_none()


async def add_favorite(db: AsyncSession, user_id: int, product_id: int) -> Favorite:
    existing = await get_favorite_by_user_product(db, user_id, product_id)
    if existing is not None:
        result = await db.execute(
            select(Favorite)
            .options(selectinload(Favorite.product).selectinload(Product.category))
            .where(Favorite.id == existing.id)
        )
        return result.scalar_one()

    product_result = await db.execute(select(Product).where(Product.id == product_id))
    product = product_result.scalar_one_or_none()
    if product is None:
        raise ValueError("商品不存在")
    if product.approval_status != ProductStatus.approved:
        raise ValueError("商品不可收藏")

    favorite = Favorite(user_id=user_id, product_id=product_id)
    db.add(favorite)
    await db.commit()

    result = await db.execute(
        select(Favorite)
        .options(selectinload(Favorite.product).selectinload(Product.category))
        .where(Favorite.id == favorite.id)
    )
    return result.scalar_one()


async def remove_favorite(db: AsyncSession, user_id: int, product_id: int) -> bool:
    favorite = await get_favorite_by_user_product(db, user_id, product_id)
    if favorite is None:
        return False
    await db.delete(favorite)
    await db.commit()
    return True
