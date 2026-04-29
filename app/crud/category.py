from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.product import Product
from app.schemas.category import CategoryCreate, CategoryUpdate


async def list_active_categories(db: AsyncSession) -> list[Category]:
    result = await db.execute(
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.sort_order.asc(), Category.id.asc())
    )
    return list(result.scalars().all())


async def list_all_categories(db: AsyncSession) -> list[Category]:
    result = await db.execute(
        select(Category)
        .order_by(Category.sort_order.asc(), Category.id.asc())
    )
    return list(result.scalars().all())


async def get_category_by_id(db: AsyncSession, category_id: int) -> Category | None:
    result = await db.execute(select(Category).where(Category.id == category_id))
    return result.scalar_one_or_none()


async def get_category_by_name(db: AsyncSession, name: str) -> Category | None:
    result = await db.execute(select(Category).where(Category.name == name.strip()))
    return result.scalar_one_or_none()


async def get_active_category_by_id(db: AsyncSession, category_id: int) -> Category | None:
    result = await db.execute(
        select(Category).where(
            Category.id == category_id,
            Category.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def create_category(db: AsyncSession, payload: CategoryCreate) -> Category:
    category = Category(
        name=payload.name.strip(),
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


async def update_category(db: AsyncSession, category: Category, payload: CategoryUpdate) -> Category:
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        category.name = data["name"].strip()
    if "sort_order" in data and data["sort_order"] is not None:
        category.sort_order = data["sort_order"]
    await db.commit()
    await db.refresh(category)
    return category


async def set_category_status(db: AsyncSession, category: Category, is_active: bool) -> Category:
    category.is_active = is_active
    await db.commit()
    await db.refresh(category)
    return category


async def count_products_by_category(db: AsyncSession, category_id: int) -> int:
    result = await db.execute(select(func.count(Product.id)).where(Product.category_id == category_id))
    return int(result.scalar_one() or 0)


async def delete_category(db: AsyncSession, category: Category) -> None:
    await db.delete(category)
    await db.commit()


async def ensure_fallback_category(
    db: AsyncSession,
    *,
    fallback_name: str,
    fallback_sort_order: int = 9999,
) -> Category:
    category = await get_category_by_name(db, fallback_name)
    if category is None:
        category = Category(
            name=fallback_name,
            sort_order=fallback_sort_order,
            is_active=True,
        )
        db.add(category)
        await db.flush()
    elif not category.is_active:
        category.is_active = True
        await db.flush()
    return category


async def reassign_products_category(
    db: AsyncSession,
    *,
    source_category_id: int,
    target_category_id: int,
) -> int:
    result = await db.execute(
        select(Product).where(Product.category_id == source_category_id)
    )
    products = result.scalars().all()
    for product in products:
        product.category_id = target_category_id
    await db.flush()
    return len(products)
