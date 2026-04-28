from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user
from app.crud import product as product_crud
from app.crud.seller import get_seller_profile_by_user_id, upsert_seller_profile
from app.db.session import get_db
from app.models.seller_profile import SellerAuditStatus
from app.models.user import User, UserRole
from app.schemas.common import APIResponse
from app.schemas.seller import (
    SellerProductCreate,
    SellerProductOut,
    SellerProductUpdate,
    SellerProfileOut,
    SellerProfileUpsert,
)

router = APIRouter(prefix="/seller", tags=["Seller"])


def ensure_seller(current_user: User) -> None:
    if current_user.role != UserRole.seller:
        raise HTTPException(status_code=403, detail="仅商家可访问")


@router.get("/profile", response_model=APIResponse[SellerProfileOut | None], summary="获取商家店铺资料")
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_seller(current_user)
    profile = await get_seller_profile_by_user_id(db, current_user.id)
    return {"message": "商家资料获取成功", "data": profile}


@router.put("/profile", response_model=APIResponse[SellerProfileOut], summary="创建/更新商家店铺资料")
async def put_profile(
    payload: SellerProfileUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_seller(current_user)
    profile = await upsert_seller_profile(db, current_user.id, payload)
    return {"message": "商家资料保存成功", "data": profile}


@router.post("/products", response_model=APIResponse[SellerProductOut], summary="商家创建商品")
async def create_my_product(
    payload: SellerProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_seller(current_user)
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
    return {"message": "商品创建成功，待审核", "data": product}


@router.get("/products", response_model=APIResponse[list[SellerProductOut]], summary="商家查看我的商品")
async def list_my_products(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_seller(current_user)
    products = await product_crud.list_products_by_role(db, current_user)
    return {"message": "我的商品列表获取成功", "data": products}


@router.put("/products/{product_id}", response_model=APIResponse[SellerProductOut], summary="商家更新我的商品")
async def update_my_product(
    product_id: int,
    payload: SellerProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_seller(current_user)
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    if product.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="只能更新自己的商品")
    try:
        product = await product_crud.update_product(db, product, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "商品更新成功，已重新进入待审核", "data": product}


@router.delete("/products/{product_id}", response_model=APIResponse[dict], summary="商家删除我的商品")
async def delete_my_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_seller(current_user)
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    if product.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="只能删除自己的商品")
    await product_crud.delete_product(db, product)
    return {"message": "商品删除成功", "data": {"product_id": product_id}}
