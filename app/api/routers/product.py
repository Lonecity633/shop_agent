from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user, get_current_user_optional
from app.crud import product as product_crud
from app.crud.seller import get_seller_profile_by_user_id
from app.db.session import get_db
from app.models.seller_profile import SellerAuditStatus
from app.models.user import User, UserRole
from app.schemas.common import APIResponse
from app.schemas.product import ProductAuditUpdate, ProductCreate, ProductOut, ProductUpdate

router = APIRouter(prefix="/products", tags=["Products"])


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


@router.post("", response_model=APIResponse[ProductOut], summary="创建商品（商家）")
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.seller:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅商家可创建商品")
    profile = await get_seller_profile_by_user_id(db, current_user.id)
    if profile is None:
        raise HTTPException(status_code=400, detail="请先完善店铺资料并通过审核")
    if profile.audit_status != SellerAuditStatus.approved:
        raise HTTPException(status_code=403, detail="店铺资料未通过审核，暂不可上架")
    if not profile.is_active:
        raise HTTPException(status_code=403, detail="店铺已停用，暂不可上架")

    try:
        product = await product_crud.create_product(db, payload, seller_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "商品创建成功，待管理员审核", "data": product}


@router.get("", response_model=APIResponse[list[ProductOut]], summary="获取商品列表")
async def list_products(
    keyword: str | None = Query(default=None, min_length=1, description="搜索关键词"),
    category_id: int | None = Query(default=None, gt=0, description="分类ID"),
    random: bool = Query(default=False, description="是否随机排序"),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    if current_user and current_user.role == UserRole.admin:
        raise HTTPException(status_code=403, detail="管理员请在管理后台查看商品")

    products = await product_crud.list_products(
        db,
        current_user=current_user,
        keyword=keyword,
        category_id=category_id,
        random_order=random,
    )
    return {"message": "商品列表获取成功", "data": products}


@router.get("/search", response_model=APIResponse[list[ProductOut]], summary="关键词搜索商品")
async def search_products(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    if current_user and current_user.role == UserRole.admin:
        raise HTTPException(status_code=403, detail="管理员请在管理后台查看商品")
    products = await product_crud.search_products_by_role(db, keyword, current_user)
    return {"message": f"关键词 '{keyword}' 搜索完成", "data": products}


@router.get("/{product_id}", response_model=APIResponse[ProductOut], summary="获取单个商品")
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    if current_user and current_user.role == UserRole.admin:
        raise HTTPException(status_code=403, detail="管理员请在管理后台查看商品")
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    if not _can_read_product(current_user, product.seller_id, product.approval_status.value):
        raise HTTPException(status_code=403, detail="无权限查看该商品")
    return {"message": "商品获取成功", "data": product}


@router.put("/{product_id}", response_model=APIResponse[ProductOut], summary="更新商品（商家）")
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    if current_user.role != UserRole.seller or product.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="仅商品所属商家可修改")

    try:
        product = await product_crud.update_product(db, product, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "商品更新成功，已重新进入待审核状态", "data": product}


@router.patch("/{product_id}/audit", response_model=APIResponse[ProductOut], summary="审核商品（管理员）")
async def audit_product(
    product_id: int,
    payload: ProductAuditUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="仅管理员可审核商品")

    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    product = await product_crud.audit_product(db, product, payload)
    return {"message": "商品审核完成", "data": product}


@router.delete("/{product_id}", response_model=APIResponse[dict], summary="删除商品")
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    if current_user.role != UserRole.admin and (current_user.role != UserRole.seller or product.seller_id != current_user.id):
        raise HTTPException(status_code=403, detail="无权限删除该商品")

    await product_crud.delete_product(db, product)
    return {"message": "商品删除成功", "data": {"product_id": product_id}}
