from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user, get_current_user_optional
from app.core.errors import raise_error
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.product import ProductAuditUpdate, ProductCreate, ProductOut, ProductUpdate
from app.services import product as product_service
from app.services.common import ServiceError

router = APIRouter(prefix="/products", tags=["Products"])


def _handle_error(exc: ServiceError):
    raise_error(exc.code, exc.message, status_code=exc.status_code)


@router.post("", response_model=APIResponse[ProductOut], summary="创建商品（商家）")
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        product = await product_service.create_product(db, current_user, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"message": "商品创建成功，待管理员审核", "data": product}


@router.get("", response_model=APIResponse[list[ProductOut]], summary="获取商品列表")
async def list_products(
    keyword: str | None = Query(default=None, min_length=1, description="搜索关键词"),
    category_id: int | None = Query(default=None, gt=0, description="分类ID"),
    random: bool = Query(default=False, description="是否随机排序"),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    try:
        products = await product_service.list_products(
            db,
            current_user,
            keyword=keyword,
            category_id=category_id,
            random=random,
        )
    except ServiceError as exc:
        _handle_error(exc)
    return {"message": "商品列表获取成功", "data": products}


@router.get("/search", response_model=APIResponse[list[ProductOut]], summary="关键词搜索商品")
async def search_products(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    try:
        products = await product_service.search_products(db, current_user, keyword)
    except ServiceError as exc:
        _handle_error(exc)
    return {"message": f"关键词 '{keyword}' 搜索完成", "data": products}


@router.get("/{product_id}", response_model=APIResponse[ProductOut], summary="获取单个商品")
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    try:
        product = await product_service.get_product(db, current_user, product_id)
    except ServiceError as exc:
        _handle_error(exc)
    return {"message": "商品获取成功", "data": product}


@router.put("/{product_id}", response_model=APIResponse[ProductOut], summary="更新商品（商家）")
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        product = await product_service.update_product(db, current_user, product_id, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"message": "商品更新成功，已重新进入待审核状态", "data": product}


@router.patch("/{product_id}/audit", response_model=APIResponse[ProductOut], summary="审核商品（管理员）")
async def audit_product(
    product_id: int,
    payload: ProductAuditUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        product = await product_service.audit_product(db, current_user, product_id, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"message": "商品审核完成", "data": product}


@router.delete("/{product_id}", response_model=APIResponse[dict], summary="删除商品")
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await product_service.delete_product(db, current_user, product_id)
    except ServiceError as exc:
        _handle_error(exc)

    return {"message": "商品删除成功", "data": {"product_id": product_id}}
