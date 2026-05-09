from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from PyPDF2 import PdfReader
import io
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user
from app.core.errors import raise_error
from app.db.session import get_db
from app.models.user import User
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
from app.schemas.category import CategoryCreate, CategoryOut, CategoryStatusUpdate, CategoryUpdate
from app.schemas.common import APIResponse, PagedData
from app.schemas.knowledge import KBDocumentCreate, KBDocumentOut
from app.schemas.refund import RefundAdminReview, RefundExecutePayload, RefundOut
from app.services import admin as admin_service
from app.services import knowledge as kb_service
from app.services.common import ServiceError

router = APIRouter(prefix="/admin", tags=["Admin"])


def _handle_error(exc: ServiceError):
    raise_error(exc.code, exc.message, status_code=exc.status_code)


@router.get("/categories", response_model=APIResponse[list[CategoryOut]], summary="管理员查看分类列表")
async def get_categories_admin(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await admin_service.get_categories_admin(db, current_user)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "分类列表获取成功", "data": data}


@router.post("/categories", response_model=APIResponse[CategoryOut], summary="管理员创建分类")
async def create_category_admin(
    payload: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await admin_service.create_category_admin(db, current_user, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "分类创建成功", "data": data}


@router.put("/categories/{category_id}", response_model=APIResponse[CategoryOut], summary="管理员更新分类")
async def update_category_admin(
    category_id: int,
    payload: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await admin_service.update_category_admin(db, current_user, category_id, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "分类更新成功", "data": data}


@router.patch("/categories/{category_id}/status", response_model=APIResponse[CategoryOut], summary="管理员启停分类")
async def update_category_status_admin(
    category_id: int,
    payload: CategoryStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await admin_service.update_category_status_admin(db, current_user, category_id, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "分类状态更新成功", "data": data}


@router.delete("/categories/{category_id}", response_model=APIResponse[dict], summary="管理员删除分类")
async def delete_category_admin(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await admin_service.delete_category_admin(db, current_user, category_id)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "分类删除成功", "data": data}


@router.get("/overview", response_model=APIResponse[AdminOverviewOut], summary="管理员运营总览")
async def get_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await admin_service.get_overview(db, current_user)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "运营总览获取成功", "data": data}


@router.get("/sellers", response_model=APIResponse[list[SellerInfoOut]], summary="获取卖家列表与统计")
async def get_sellers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await admin_service.get_sellers(db, current_user)
    except ServiceError as exc:
        _handle_error(exc)
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
    try:
        data = await admin_service.get_pending_products(db, current_user)
    except ServiceError as exc:
        _handle_error(exc)
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
    try:
        data = await admin_service.get_pending_seller_profiles(db, current_user)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "待审核卖家资料获取成功", "data": data}


@router.get("/orders/recent", response_model=APIResponse[list[AdminRecentOrderOut]], summary="获取最近订单")
async def get_recent_orders(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await admin_service.get_recent_orders(db, current_user, limit)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "最近订单获取成功", "data": data}


@router.get("/refunds", response_model=APIResponse[list[AdminRefundCaseOut]], summary="获取退款工单列表")
async def get_refund_cases(
    status: str | None = Query(default=None, description="退款状态过滤"),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await admin_service.get_refund_cases(db, current_user, status, limit)
    except ServiceError as exc:
        _handle_error(exc)
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
    try:
        data = await admin_service.get_orders_paged(
            db,
            current_user,
            page=page,
            page_size=page_size,
            status=status,
            pay_status=pay_status,
            keyword=keyword,
        )
    except ServiceError as exc:
        _handle_error(exc)
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
    try:
        data = await admin_service.get_refunds_paged(
            db,
            current_user,
            page=page,
            page_size=page_size,
            status=status,
            keyword=keyword,
        )
    except ServiceError as exc:
        _handle_error(exc)
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
    try:
        data = await admin_service.get_operation_timeline(
            db,
            current_user,
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit,
        )
    except ServiceError as exc:
        _handle_error(exc)
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
    try:
        profile = await admin_service.patch_seller_profile_audit(
            db,
            current_user,
            profile_id=profile_id,
            payload=payload,
        )
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "卖家资料审核成功", "data": profile}


@router.patch("/refunds/{refund_id}/arbitrate", response_model=APIResponse[RefundOut], summary="管理员仲裁退款")
async def arbitrate_refund(
    refund_id: int,
    payload: RefundAdminReview,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        refund = await admin_service.arbitrate_refund(
            db,
            current_user,
            refund_id=refund_id,
            payload=payload,
        )
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "退款仲裁完成", "data": refund}


@router.post("/refunds/{refund_id}/execute", response_model=APIResponse[RefundOut], summary="管理员执行退款")
async def execute_refund_payment(
    refund_id: int,
    payload: RefundExecutePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        refund = await admin_service.execute_refund_payment(
            db,
            current_user,
            refund_id=refund_id,
            payload=payload,
        )
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "退款执行完成", "data": refund}


# ────────────────────── 知识库管理 ──────────────────────


@router.post("/knowledge/documents/upload", response_model=APIResponse[KBDocumentOut], summary="上传知识库文件")
async def upload_kb_document_file(
    title: str = Form(..., min_length=1, max_length=255),
    file: UploadFile = File(..., description="支持 .txt / .md 文件"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(('.txt', '.md', '.pdf')):
        raise ServiceError("KB_INVALID_FILE", "仅支持 .txt / .md / .pdf 文件", 400)
    raw = await file.read()
    filename_lower = file.filename.lower()
    if filename_lower.endswith('.pdf'):
        try:
            reader = PdfReader(io.BytesIO(raw))
            content = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            raise ServiceError("KB_PDF_PARSE_FAILED", "PDF 文件解析失败", 400)
    else:
        try:
            content = raw.decode('utf-8')
        except UnicodeDecodeError:
            content = raw.decode('utf-8', errors='ignore')
    if not content.strip():
        raise ServiceError("KB_EMPTY_FILE", "文件内容为空", 400)
    try:
        doc = await kb_service.upload_document(db, current_user, title, content)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "文档上传成功", "data": doc}


@router.post("/knowledge/documents", response_model=APIResponse[KBDocumentOut], summary="上传知识库文档")
async def upload_kb_document(
    payload: KBDocumentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        doc = await kb_service.upload_document(db, current_user, payload.title, payload.content)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "文档上传成功", "data": doc}


@router.get("/knowledge/documents", response_model=APIResponse[PagedData[KBDocumentOut]], summary="知识库文档列表")
async def list_kb_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await kb_service.list_documents(db, current_user, page=page, page_size=page_size)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "查询成功", "data": data}


@router.delete("/knowledge/documents/{document_id}", response_model=APIResponse, summary="删除知识库文档")
async def delete_kb_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await kb_service.delete_document_by_id(db, current_user, document_id)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "文档已删除", "data": None}
