from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.category import Category
from app.models.cart import CartItem
from app.models.product import Product, ProductStatus


async def list_cart_items(db: AsyncSession, user_id: int) -> list[CartItem]:
    result = await db.execute(
        select(CartItem)
        .options(selectinload(CartItem.product).selectinload(Product.category))
        .where(
            CartItem.user_id == user_id,
            CartItem.product.has(Product.is_deleted.is_(False)),
            CartItem.product.has(Product.category.has(Category.is_active.is_(True))),
        )
        .order_by(CartItem.id.desc())
    )
    return list(result.scalars().all())


async def get_cart_item(db: AsyncSession, item_id: int) -> CartItem | None:
    result = await db.execute(
        select(CartItem)
        .options(selectinload(CartItem.product).selectinload(Product.category))
        .where(CartItem.id == item_id)
    )
    return result.scalar_one_or_none()


async def get_cart_item_by_user_product(db: AsyncSession, user_id: int, product_id: int) -> CartItem | None:
    result = await db.execute(
        select(CartItem).where(CartItem.user_id == user_id, CartItem.product_id == product_id)
    )
    return result.scalar_one_or_none()


async def add_cart_item(db: AsyncSession, user_id: int, product_id: int, quantity: int) -> CartItem:
    product_result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.id == product_id)
    )
    product = product_result.scalar_one_or_none()
    if product is None:
        raise ValueError("商品不存在")
    if product.is_deleted:
        raise ValueError("商品已下架，无法加入购物车")
    if product.approval_status != ProductStatus.approved:
        raise ValueError("商品不可加入购物车")
    if product.category is None or not product.category.is_active:
        raise ValueError("商品所属分类已停用，暂不可购买")

    item = await get_cart_item_by_user_product(db, user_id, product_id)
    if item is None:
        if quantity > product.stock:
            raise ValueError("超出库存")
        item = CartItem(user_id=user_id, product_id=product_id, quantity=quantity, selected=True)
        db.add(item)
        await db.commit()
    else:
        target_quantity = item.quantity + quantity
        if target_quantity > product.stock:
            raise ValueError("超出库存")
        item.quantity = target_quantity
        item.selected = True
        await db.commit()

    result = await db.execute(
        select(CartItem)
        .options(selectinload(CartItem.product).selectinload(Product.category))
        .where(CartItem.id == item.id)
    )
    return result.scalar_one()


async def update_cart_item(
    db: AsyncSession,
    item: CartItem,
    quantity: int | None = None,
    selected: bool | None = None,
) -> CartItem:
    if quantity is not None:
        product_result = await db.execute(
            select(Product)
            .options(selectinload(Product.category))
            .where(Product.id == item.product_id)
        )
        product = product_result.scalar_one_or_none()
        if product is None:
            raise ValueError("商品不存在")
        if product.is_deleted:
            raise ValueError("商品已下架，无法更新购物车")
        if product.category is None or not product.category.is_active:
            raise ValueError("商品所属分类已停用，暂不可购买")
        if quantity > product.stock:
            raise ValueError("超出库存")
        item.quantity = quantity

    if selected is not None:
        item.selected = selected

    await db.commit()

    result = await db.execute(
        select(CartItem)
        .options(selectinload(CartItem.product).selectinload(Product.category))
        .where(CartItem.id == item.id)
    )
    return result.scalar_one()


async def remove_cart_item(db: AsyncSession, item: CartItem) -> None:
    await db.delete(item)
    await db.commit()


async def remove_cart_items_by_product(db: AsyncSession, product_id: int) -> int:
    result = await db.execute(select(CartItem).where(CartItem.product_id == product_id))
    items = result.scalars().all()
    for item in items:
        await db.delete(item)
    return len(items)
