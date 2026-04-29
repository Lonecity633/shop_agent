from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import product as product_crud
from app.crud.cart import remove_cart_items_by_product
from app.crud.favorite import remove_favorites_by_product
from app.crud.seller import get_seller_profile_by_user_id, upsert_seller_profile
from app.models.seller_profile import SellerAuditStatus
from app.models.user import User, UserRole
from app.schemas.seller import SellerProductCreate, SellerProductUpdate, SellerProfileUpsert
from app.services.common import ServiceError, ensure


def _ensure_seller(current_user: User) -> None:
    ensure(current_user.role == UserRole.seller, "ROLE_DENIED", "仅商家可访问", 403)


async def get_profile(db: AsyncSession, current_user: User):
    _ensure_seller(current_user)
    return await get_seller_profile_by_user_id(db, current_user.id)


async def put_profile(db: AsyncSession, current_user: User, payload: SellerProfileUpsert):
    _ensure_seller(current_user)
    return await upsert_seller_profile(db, current_user.id, payload)


async def create_my_product(db: AsyncSession, current_user: User, payload: SellerProductCreate):
    _ensure_seller(current_user)
    profile = await get_seller_profile_by_user_id(db, current_user.id)
    ensure(profile is not None, "SELLER_PROFILE_REQUIRED", "请先完善店铺资料并通过审核", 400)
    ensure(profile.audit_status == SellerAuditStatus.approved, "SELLER_PROFILE_NOT_APPROVED", "店铺资料未通过审核，暂不可上架", 403)
    ensure(profile.is_active, "SELLER_PROFILE_INACTIVE", "店铺已停用，暂不可上架", 403)
    try:
        return await product_crud.create_product(db, payload, seller_id=current_user.id)
    except ValueError as exc:
        raise ServiceError("SELLER_PRODUCT_CREATE_FAILED", str(exc), 400) from exc


async def list_my_products(db: AsyncSession, current_user: User):
    _ensure_seller(current_user)
    return await product_crud.list_products_by_role(db, current_user)


async def update_my_product(db: AsyncSession, current_user: User, product_id: int, payload: SellerProductUpdate):
    _ensure_seller(current_user)
    product = await product_crud.get_product_active(db, product_id)
    ensure(product is not None, "PRODUCT_NOT_FOUND", "商品不存在", 404)
    ensure(product.seller_id == current_user.id, "PRODUCT_FORBIDDEN", "只能更新自己的商品", 403)
    try:
        return await product_crud.update_product(db, product, payload)
    except ValueError as exc:
        raise ServiceError("SELLER_PRODUCT_UPDATE_FAILED", str(exc), 400) from exc


async def delete_my_product(db: AsyncSession, current_user: User, product_id: int):
    _ensure_seller(current_user)
    product = await product_crud.get_product_active(db, product_id)
    ensure(product is not None, "PRODUCT_NOT_FOUND", "商品不存在", 404)
    ensure(product.seller_id == current_user.id, "PRODUCT_FORBIDDEN", "只能删除自己的商品", 403)
    try:
        await remove_favorites_by_product(db, product.id)
        await remove_cart_items_by_product(db, product.id)
        await product_crud.delete_product(db, product)
    except ValueError as exc:
        raise ServiceError("SELLER_PRODUCT_DELETE_FAILED", str(exc), 400) from exc
