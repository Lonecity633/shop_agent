from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import product as product_crud
from app.crud.cart import remove_cart_items_by_product
from app.crud.favorite import remove_favorites_by_product
from app.crud.seller import get_seller_profile_by_user_id
from app.models.seller_profile import SellerAuditStatus
from app.models.user import User, UserRole
from app.schemas.product import ProductAuditUpdate, ProductCreate, ProductUpdate
from app.services.common import ServiceError, ensure


def _ensure_admin_not_allowed_in_storefront(current_user: User | None) -> None:
    if current_user and current_user.role == UserRole.admin:
        raise ServiceError("ROLE_DENIED", "管理员请在管理后台查看商品", 403)


def _can_read_product(current_user: User | None, product_seller_id: int, approval_status: str) -> bool:
    if current_user is None:
        return approval_status == "approved"
    if current_user.role == UserRole.seller:
        return current_user.id == product_seller_id
    if current_user.role == UserRole.buyer:
        return approval_status == "approved"
    if current_user.role == UserRole.admin:
        return True
    return False


def _should_enforce_storefront_category(current_user: User | None) -> bool:
    return current_user is None or current_user.role == UserRole.buyer


async def create_product(db: AsyncSession, current_user: User, payload: ProductCreate):
    ensure(current_user.role == UserRole.seller, "ROLE_DENIED", "仅商家可创建商品", 403)
    profile = await get_seller_profile_by_user_id(db, current_user.id)
    ensure(profile is not None, "SELLER_PROFILE_REQUIRED", "请先完善店铺资料并通过审核", 400)
    ensure(profile.audit_status == SellerAuditStatus.approved, "SELLER_PROFILE_NOT_APPROVED", "店铺资料未通过审核，暂不可上架", 403)
    ensure(profile.is_active, "SELLER_PROFILE_INACTIVE", "店铺已停用，暂不可上架", 403)

    try:
        return await product_crud.create_product(db, payload, seller_id=current_user.id)
    except ValueError as exc:
        raise ServiceError("PRODUCT_CREATE_FAILED", str(exc), 400) from exc


async def list_products(
    db: AsyncSession,
    current_user: User | None,
    *,
    keyword: str | None,
    category_id: int | None,
    random: bool,
):
    _ensure_admin_not_allowed_in_storefront(current_user)
    return await product_crud.list_products(
        db,
        current_user=current_user,
        keyword=keyword,
        category_id=category_id,
        random_order=random,
    )


async def search_products(db: AsyncSession, current_user: User | None, keyword: str):
    _ensure_admin_not_allowed_in_storefront(current_user)
    return await product_crud.search_products_by_role(db, keyword, current_user)


async def get_product(db: AsyncSession, current_user: User | None, product_id: int):
    _ensure_admin_not_allowed_in_storefront(current_user)
    product = await product_crud.get_product_active(db, product_id)
    ensure(product is not None, "PRODUCT_NOT_FOUND", "商品不存在", 404)
    ensure(
        _can_read_product(current_user, product.seller_id, product.approval_status.value),
        "PRODUCT_FORBIDDEN",
        "无权限查看该商品",
        403,
    )
    if _should_enforce_storefront_category(current_user):
        ensure(
            product.category is not None and product.category.is_active,
            "PRODUCT_NOT_FOUND",
            "商品不存在",
            404,
        )
    return product


async def update_product(db: AsyncSession, current_user: User, product_id: int, payload: ProductUpdate):
    product = await product_crud.get_product_active(db, product_id)
    ensure(product is not None, "PRODUCT_NOT_FOUND", "商品不存在", 404)
    ensure(
        current_user.role == UserRole.seller and product.seller_id == current_user.id,
        "PRODUCT_FORBIDDEN",
        "仅商品所属商家可修改",
        403,
    )
    try:
        return await product_crud.update_product(db, product, payload)
    except ValueError as exc:
        raise ServiceError("PRODUCT_UPDATE_FAILED", str(exc), 400) from exc


async def audit_product(db: AsyncSession, current_user: User, product_id: int, payload: ProductAuditUpdate):
    ensure(current_user.role == UserRole.admin, "ROLE_DENIED", "仅管理员可审核商品", 403)
    product = await product_crud.get_product_active(db, product_id)
    ensure(product is not None, "PRODUCT_NOT_FOUND", "商品不存在", 404)
    return await product_crud.audit_product(db, product, payload)


async def delete_product(db: AsyncSession, current_user: User, product_id: int):
    product = await product_crud.get_product_active(db, product_id)
    ensure(product is not None, "PRODUCT_NOT_FOUND", "商品不存在", 404)
    ensure(
        current_user.role == UserRole.admin or (current_user.role == UserRole.seller and product.seller_id == current_user.id),
        "PRODUCT_FORBIDDEN",
        "无权限删除该商品",
        403,
    )
    try:
        await remove_favorites_by_product(db, product.id)
        await remove_cart_items_by_product(db, product.id)
        await product_crud.delete_product(db, product)
    except ValueError as exc:
        raise ServiceError("PRODUCT_DELETE_FAILED", str(exc), 400) from exc
