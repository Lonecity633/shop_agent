import json
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.category import Category
from app.models.product import Product, ProductStatus
from app.models.user import User, UserRole
from app.crud import category as category_crud
from app.schemas.product import ProductAuditUpdate, ProductCreate, ProductUpdate


def _apply_visibility(stmt, current_user: User | None):
    storefront_category_filter = Product.category.has(Category.is_active.is_(True))
    if current_user is None:
        return stmt.where(
            Product.approval_status == ProductStatus.approved,
            Product.is_deleted.is_(False),
            storefront_category_filter,
        )
    if current_user.role == UserRole.seller:
        return stmt.where(Product.seller_id == current_user.id, Product.is_deleted.is_(False))
    if current_user.role == UserRole.buyer:
        return stmt.where(
            Product.approval_status == ProductStatus.approved,
            Product.is_deleted.is_(False),
            storefront_category_filter,
        )
    return stmt


async def create_product(db: AsyncSession, payload: ProductCreate, seller_id: int) -> Product:
    data = payload.model_dump()
    category = await category_crud.get_active_category_by_id(db, data["category_id"])
    if category is None:
        raise ValueError("分类不存在或已停用，请重新选择")

    data["image_urls"] = json.dumps([str(url) for url in data.get("image_urls", [])], ensure_ascii=False)
    product = Product(
        **data,
        seller_id=seller_id,
        approval_status=ProductStatus.pending,
        is_deleted=False,
    )
    db.add(product)
    await db.commit()

    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.id == product.id)
    )
    return result.scalar_one()


async def list_products(
    db: AsyncSession,
    current_user: User | None,
    keyword: str | None = None,
    category_id: int | None = None,
    random_order: bool = False,
) -> list[Product]:
    stmt = select(Product).options(selectinload(Product.category))
    stmt = _apply_visibility(stmt, current_user)

    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(or_(Product.name.like(pattern), Product.description.like(pattern)))
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)

    if random_order:
        stmt = stmt.order_by(func.rand())
    else:
        stmt = stmt.order_by(Product.id.desc())

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def search_products_by_role(db: AsyncSession, keyword: str, current_user: User | None) -> list[Product]:
    return await list_products(db, current_user, keyword=keyword, random_order=False)


async def list_products_by_role(db: AsyncSession, current_user: User) -> list[Product]:
    # Backward-compatible wrapper for existing seller/admin call sites.
    return await list_products(db, current_user=current_user, random_order=False)


async def get_product(db: AsyncSession, product_id: int) -> Product | None:
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.id == product_id)
    )
    return result.scalar_one_or_none()


async def get_product_active(db: AsyncSession, product_id: int) -> Product | None:
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.id == product_id, Product.is_deleted.is_(False))
    )
    return result.scalar_one_or_none()


async def update_product(db: AsyncSession, product: Product, payload: ProductUpdate) -> Product:
    update_data = payload.model_dump(exclude_unset=True)

    target_category_id = update_data.get("category_id", product.category_id)
    if target_category_id is None:
        raise ValueError("商品分类不能为空，请选择有效分类")
    target_category = await category_crud.get_active_category_by_id(db, int(target_category_id))
    if target_category is None:
        raise ValueError("分类不存在或已停用，请重新选择")

    if "image_urls" in update_data and update_data["image_urls"] is not None:
        update_data["image_urls"] = json.dumps(
            [str(url) for url in update_data["image_urls"]],
            ensure_ascii=False,
        )

    for field, value in update_data.items():
        setattr(product, field, value)

    product.approval_status = ProductStatus.pending
    product.review_note = ""
    product.reviewed_at = None

    await db.commit()
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.id == product.id)
    )
    return result.scalar_one()


async def audit_product(db: AsyncSession, product: Product, payload: ProductAuditUpdate) -> Product:
    product.approval_status = ProductStatus(payload.approval_status)
    product.review_note = payload.review_note
    product.reviewed_at = datetime.now(UTC)
    await db.commit()

    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.id == product.id)
    )
    return result.scalar_one()


async def delete_product(db: AsyncSession, product: Product) -> None:
    product.is_deleted = True
    product.approval_status = ProductStatus.rejected
    product.review_note = "已删除（逻辑删除）"
    product.reviewed_at = datetime.now(UTC)
    await db.commit()
