from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import category as category_crud
from app.crud.admin import (
    get_admin_overview,
    list_orders_paged,
    list_pending_products,
    list_recent_orders,
    list_refund_cases,
    list_refund_cases_paged,
    list_sellers_with_stats,
)
from app.crud.audit import list_timeline
from app.crud.refund import admin_review_refund, execute_refund, get_refund_for_update
from app.crud.seller import audit_seller_profile, get_seller_profile_by_id, list_pending_seller_profiles
from app.models.user import User, UserRole
from app.schemas.admin import SellerProfileAuditUpdate
from app.schemas.category import CategoryCreate, CategoryStatusUpdate, CategoryUpdate
from app.schemas.refund import RefundAdminReview, RefundExecutePayload
from app.services.common import ServiceError, ensure

SYSTEM_FALLBACK_CATEGORY = "其他"


def _ensure_admin(current_user: User) -> None:
    ensure(current_user.role == UserRole.admin, "ROLE_DENIED", "仅管理员可访问", 403)


async def get_categories_admin(db: AsyncSession, current_user: User):
    _ensure_admin(current_user)
    return await category_crud.list_all_categories(db)


async def create_category_admin(db: AsyncSession, current_user: User, payload: CategoryCreate):
    _ensure_admin(current_user)
    if payload.name == SYSTEM_FALLBACK_CATEGORY and not payload.is_active:
        raise ServiceError("CATEGORY_DISABLE_FORBIDDEN", "系统保底分类“其他”必须保持启用", 400)
    existing = await category_crud.get_category_by_name(db, payload.name)
    ensure(existing is None, "CATEGORY_NAME_DUPLICATED", "分类名称已存在", 400)
    return await category_crud.create_category(db, payload)


async def update_category_admin(db: AsyncSession, current_user: User, category_id: int, payload: CategoryUpdate):
    _ensure_admin(current_user)
    category = await category_crud.get_category_by_id(db, category_id)
    ensure(category is not None, "CATEGORY_NOT_FOUND", "分类不存在", 404)

    if payload.name is not None:
        if category.name == SYSTEM_FALLBACK_CATEGORY and payload.name != SYSTEM_FALLBACK_CATEGORY:
            raise ServiceError("CATEGORY_UPDATE_FORBIDDEN", "系统保底分类“其他”不允许改名", 400)
        existing = await category_crud.get_category_by_name(db, payload.name)
        if existing and existing.id != category.id:
            raise ServiceError("CATEGORY_NAME_DUPLICATED", "分类名称已存在", 400)

    return await category_crud.update_category(db, category, payload)


async def update_category_status_admin(
    db: AsyncSession,
    current_user: User,
    category_id: int,
    payload: CategoryStatusUpdate,
):
    _ensure_admin(current_user)
    category = await category_crud.get_category_by_id(db, category_id)
    ensure(category is not None, "CATEGORY_NOT_FOUND", "分类不存在", 404)
    if category.name == SYSTEM_FALLBACK_CATEGORY and not payload.is_active:
        raise ServiceError("CATEGORY_DISABLE_FORBIDDEN", "系统保底分类“其他”不允许停用", 400)
    return await category_crud.set_category_status(db, category, payload.is_active)


async def delete_category_admin(db: AsyncSession, current_user: User, category_id: int) -> dict:
    _ensure_admin(current_user)
    category = await category_crud.get_category_by_id(db, category_id)
    ensure(category is not None, "CATEGORY_NOT_FOUND", "分类不存在", 404)
    if category.name == SYSTEM_FALLBACK_CATEGORY:
        raise ServiceError("CATEGORY_DELETE_FORBIDDEN", "系统保底分类“其他”不允许删除", 400)

    fallback_category = await category_crud.ensure_fallback_category(
        db,
        fallback_name=SYSTEM_FALLBACK_CATEGORY,
    )
    if fallback_category.id == category.id:
        raise ServiceError("CATEGORY_DELETE_FORBIDDEN", "系统保底分类“其他”不允许删除", 400)

    migrated_count = await category_crud.reassign_products_category(
        db,
        source_category_id=category.id,
        target_category_id=fallback_category.id,
    )
    await db.delete(category)
    await db.commit()

    return {
        "category_id": category_id,
        "fallback_category_id": fallback_category.id,
        "migrated_product_count": migrated_count,
    }


async def get_overview(db: AsyncSession, current_user: User):
    _ensure_admin(current_user)
    return await get_admin_overview(db)


async def get_sellers(db: AsyncSession, current_user: User):
    _ensure_admin(current_user)
    return await list_sellers_with_stats(db)


async def get_pending_products(db: AsyncSession, current_user: User):
    _ensure_admin(current_user)
    return await list_pending_products(db)


async def get_pending_seller_profiles(db: AsyncSession, current_user: User):
    _ensure_admin(current_user)
    return await list_pending_seller_profiles(db)


async def get_recent_orders(db: AsyncSession, current_user: User, limit: int):
    _ensure_admin(current_user)
    return await list_recent_orders(db, limit=limit)


async def get_refund_cases(db: AsyncSession, current_user: User, status: str | None, limit: int):
    _ensure_admin(current_user)
    return await list_refund_cases(db, status=status, limit=limit)


async def get_orders_paged(
    db: AsyncSession,
    current_user: User,
    *,
    page: int,
    page_size: int,
    status: str | None,
    pay_status: str | None,
    keyword: str | None,
):
    _ensure_admin(current_user)
    return await list_orders_paged(
        db,
        page=page,
        page_size=page_size,
        status=status,
        pay_status=pay_status,
        keyword=keyword,
    )


async def get_refunds_paged(
    db: AsyncSession,
    current_user: User,
    *,
    page: int,
    page_size: int,
    status: str | None,
    keyword: str | None,
):
    _ensure_admin(current_user)
    return await list_refund_cases_paged(db, page=page, page_size=page_size, status=status, keyword=keyword)


async def get_operation_timeline(
    db: AsyncSession,
    current_user: User,
    *,
    entity_type: str,
    entity_id: int,
    limit: int,
):
    _ensure_admin(current_user)
    if entity_type not in {"order", "refund"}:
        raise ServiceError("ENTITY_TYPE_INVALID", "仅支持 order/refund 时间线", 400)
    return await list_timeline(db, entity_type=entity_type, entity_id=entity_id, limit=limit)


async def patch_seller_profile_audit(
    db: AsyncSession,
    current_user: User,
    *,
    profile_id: int,
    payload: SellerProfileAuditUpdate,
):
    _ensure_admin(current_user)
    profile = await get_seller_profile_by_id(db, profile_id)
    ensure(profile is not None, "SELLER_PROFILE_NOT_FOUND", "卖家资料不存在", 404)
    return await audit_seller_profile(db, profile, payload.approval_status)


async def arbitrate_refund(
    db: AsyncSession,
    current_user: User,
    *,
    refund_id: int,
    payload: RefundAdminReview,
):
    _ensure_admin(current_user)
    refund = await get_refund_for_update(db, refund_id)
    ensure(refund is not None, "REFUND_NOT_FOUND", "退款单不存在", 404)

    try:
        return await admin_review_refund(db, refund, current_user, payload.action, payload.admin_note)
    except ValueError as exc:
        raise ServiceError("REFUND_ARBITRATE_FAILED", str(exc), 400) from exc


async def execute_refund_payment(
    db: AsyncSession,
    current_user: User,
    *,
    refund_id: int,
    payload: RefundExecutePayload,
):
    _ensure_admin(current_user)
    refund = await get_refund_for_update(db, refund_id)
    ensure(refund is not None, "REFUND_NOT_FOUND", "退款单不存在", 404)
    try:
        return await execute_refund(
            db,
            refund,
            actor=current_user,
            result=payload.result,
            fail_reason=payload.fail_reason,
        )
    except ValueError as exc:
        raise ServiceError("REFUND_EXECUTE_FAILED", str(exc), 400) from exc
