from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user
from app.core.errors import raise_error
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
from app.crud.refund import admin_review_refund, execute_refund, get_refund
from app.crud.seller import audit_seller_profile, get_seller_profile_by_id, list_pending_seller_profiles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.admin import (
    AdminOrderOut,
    AdminOverviewOut,
    AdminRecentOrderOut,
    AdminRefundCaseOut,
    OperationTimelineItemOut,
    PendingProductOut,
    PendingSellerProfileOut,
    SellerInfoOut,
    SellerProfileAuditUpdate,
)
from app.schemas.common import APIResponse, PagedData
from app.schemas.category import CategoryCreate, CategoryOut, CategoryStatusUpdate, CategoryUpdate
from app.schemas.refund import RefundAdminReview, RefundExecutePayload, RefundOut

router = APIRouter(prefix="/admin", tags=["Admin"])
SYSTEM_FALLBACK_CATEGORY = "其他"


def _ensure_admin(current_user: User) -> None:
    if current_user.role != UserRole.admin:
        raise_error("ROLE_DENIED", "仅管理员可访问", status_code=403)


@router.get("/categories", response_model=APIResponse[list[CategoryOut]], summary="管理员查看分类列表")
async def get_categories_admin(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    data = await category_crud.list_all_categories(db)
    return {"code": "OK", "message": "分类列表获取成功", "data": data}


@router.post("/categories", response_model=APIResponse[CategoryOut], summary="管理员创建分类")
async def create_category_admin(
    payload: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    if payload.name == SYSTEM_FALLBACK_CATEGORY and not payload.is_active:
        raise_error("CATEGORY_DISABLE_FORBIDDEN", "系统保底分类“其他”必须保持启用", status_code=400)
    existing = await category_crud.get_category_by_name(db, payload.name)
    if existing:
        raise_error("CATEGORY_NAME_DUPLICATED", "分类名称已存在", status_code=400)
    data = await category_crud.create_category(db, payload)
    return {"code": "OK", "message": "分类创建成功", "data": data}


@router.put("/categories/{category_id}", response_model=APIResponse[CategoryOut], summary="管理员更新分类")
async def update_category_admin(
    category_id: int,
    payload: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    category = await category_crud.get_category_by_id(db, category_id)
    if not category:
        raise_error("CATEGORY_NOT_FOUND", "分类不存在", status_code=404)

    if payload.name is not None:
        if category.name == SYSTEM_FALLBACK_CATEGORY and payload.name != SYSTEM_FALLBACK_CATEGORY:
            raise_error("CATEGORY_UPDATE_FORBIDDEN", "系统保底分类“其他”不允许改名", status_code=400)
        existing = await category_crud.get_category_by_name(db, payload.name)
        if existing and existing.id != category.id:
            raise_error("CATEGORY_NAME_DUPLICATED", "分类名称已存在", status_code=400)

    data = await category_crud.update_category(db, category, payload)
    return {"code": "OK", "message": "分类更新成功", "data": data}


@router.patch("/categories/{category_id}/status", response_model=APIResponse[CategoryOut], summary="管理员启停分类")
async def update_category_status_admin(
    category_id: int,
    payload: CategoryStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    category = await category_crud.get_category_by_id(db, category_id)
    if not category:
        raise_error("CATEGORY_NOT_FOUND", "分类不存在", status_code=404)
    if category.name == SYSTEM_FALLBACK_CATEGORY and not payload.is_active:
        raise_error("CATEGORY_DISABLE_FORBIDDEN", "系统保底分类“其他”不允许停用", status_code=400)
    data = await category_crud.set_category_status(db, category, payload.is_active)
    return {"code": "OK", "message": "分类状态更新成功", "data": data}


@router.delete("/categories/{category_id}", response_model=APIResponse[dict], summary="管理员删除分类")
async def delete_category_admin(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    category = await category_crud.get_category_by_id(db, category_id)
    if not category:
        raise_error("CATEGORY_NOT_FOUND", "分类不存在", status_code=404)
    if category.name == SYSTEM_FALLBACK_CATEGORY:
        raise_error("CATEGORY_DELETE_FORBIDDEN", "系统保底分类“其他”不允许删除", status_code=400)
    used_count = await category_crud.count_products_by_category(db, category_id)
    if used_count > 0:
        raise_error("CATEGORY_IN_USE", "分类下仍有商品，无法删除", status_code=400)
    await category_crud.delete_category(db, category)
    return {"code": "OK", "message": "分类删除成功", "data": {"category_id": category_id}}


@router.get("/overview", response_model=APIResponse[AdminOverviewOut], summary="管理员运营总览")
async def get_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    data = await get_admin_overview(db)
    return {"code": "OK", "message": "运营总览获取成功", "data": data}


@router.get("/sellers", response_model=APIResponse[list[SellerInfoOut]], summary="获取卖家列表与统计")
async def get_sellers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    data = await list_sellers_with_stats(db)
    return {"code": "OK", "message": "卖家列表获取成功", "data": data}


@router.get(
    "/products/pending",
    response_model=APIResponse[list[PendingProductOut]],
    summary="获取待审核商品列表",
)
async def get_pending_products(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    data = await list_pending_products(db)
    return {"code": "OK", "message": "待审核商品列表获取成功", "data": data}


@router.get(
    "/seller-profiles/pending",
    response_model=APIResponse[list[PendingSellerProfileOut]],
    summary="获取待审核卖家资料",
)
async def get_pending_seller_profiles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    data = await list_pending_seller_profiles(db)
    return {"code": "OK", "message": "待审核卖家资料获取成功", "data": data}


@router.get("/orders/recent", response_model=APIResponse[list[AdminRecentOrderOut]], summary="获取最近订单")
async def get_recent_orders(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    data = await list_recent_orders(db, limit=limit)
    return {"code": "OK", "message": "最近订单获取成功", "data": data}


@router.get("/refunds", response_model=APIResponse[list[AdminRefundCaseOut]], summary="获取退款工单列表")
async def get_refund_cases(
    status: str | None = Query(default=None, description="退款状态过滤"),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    data = await list_refund_cases(db, status=status, limit=limit)
    return {"code": "OK", "message": "退款工单列表获取成功", "data": data}


@router.get("/orders", response_model=APIResponse[PagedData[AdminOrderOut]], summary="分页获取订单监控列表")
async def get_orders_paged(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    pay_status: str | None = Query(default=None),
    keyword: str | None = Query(default=None, description="买家邮箱/卖家邮箱/商品名关键词"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    data = await list_orders_paged(
        db,
        page=page,
        page_size=page_size,
        status=status,
        pay_status=pay_status,
        keyword=keyword,
    )
    return {"code": "OK", "message": "订单监控列表获取成功", "data": data}


@router.get("/refunds/paged", response_model=APIResponse[PagedData[AdminRefundCaseOut]], summary="分页获取退款工单")
async def get_refunds_paged(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, description="退款状态过滤"),
    keyword: str | None = Query(default=None, description="买家邮箱/卖家邮箱/订单ID关键词"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    data = await list_refund_cases_paged(db, page=page, page_size=page_size, status=status, keyword=keyword)
    return {"code": "OK", "message": "退款工单分页列表获取成功", "data": data}


@router.get(
    "/timelines/{entity_type}/{entity_id}",
    response_model=APIResponse[list[OperationTimelineItemOut]],
    summary="查看业务操作时间线",
)
async def get_operation_timeline(
    entity_type: str,
    entity_id: int,
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    if entity_type not in {"order", "refund"}:
        raise_error("ENTITY_TYPE_INVALID", "仅支持 order/refund 时间线", status_code=400)
    data = await list_timeline(db, entity_type=entity_type, entity_id=entity_id, limit=limit)
    return {"code": "OK", "message": "时间线获取成功", "data": data}


@router.patch(
    "/seller-profiles/{profile_id}/audit",
    response_model=APIResponse[PendingSellerProfileOut],
    summary="审核卖家资料",
)
async def patch_seller_profile_audit(
    profile_id: int,
    payload: SellerProfileAuditUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    profile = await get_seller_profile_by_id(db, profile_id)
    if not profile:
        raise_error("SELLER_PROFILE_NOT_FOUND", "卖家资料不存在", status_code=404)
    profile = await audit_seller_profile(db, profile, payload.approval_status)
    return {"code": "OK", "message": "卖家资料审核成功", "data": profile}


@router.patch("/refunds/{refund_id}/arbitrate", response_model=APIResponse[RefundOut], summary="管理员仲裁退款")
async def arbitrate_refund(
    refund_id: int,
    payload: RefundAdminReview,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    refund = await get_refund(db, refund_id)
    if not refund:
        raise_error("REFUND_NOT_FOUND", "退款单不存在", status_code=404)

    try:
        refund = await admin_review_refund(db, refund, current_user, payload.action, payload.admin_note)
    except ValueError as exc:
        raise_error("REFUND_ARBITRATE_FAILED", str(exc), status_code=400)
    return {"code": "OK", "message": "退款仲裁完成", "data": refund}


@router.post("/refunds/{refund_id}/execute", response_model=APIResponse[RefundOut], summary="管理员执行退款")
async def execute_refund_payment(
    refund_id: int,
    payload: RefundExecutePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    refund = await get_refund(db, refund_id)
    if not refund:
        raise_error("REFUND_NOT_FOUND", "退款单不存在", status_code=404)
    try:
        refund = await execute_refund(
            db,
            refund,
            actor=current_user,
            result=payload.result,
            fail_reason=payload.fail_reason,
        )
    except ValueError as exc:
        raise_error("REFUND_EXECUTE_FAILED", str(exc), status_code=400)
    return {"code": "OK", "message": "退款执行完成", "data": refund}
