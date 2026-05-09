import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user
from app.core.errors import raise_error
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.seller import (
    SellerProductCreate,
    SellerProductOut,
    SellerProductUpdate,
    SellerProfileOut,
    SellerProfileUpsert,
)
from app.services import seller as seller_service
from app.services.common import ServiceError

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "uploads" / "products"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

router = APIRouter(prefix="/seller", tags=["Seller"])


def _handle_error(exc: ServiceError):
    raise_error(exc.code, exc.message, status_code=exc.status_code)


@router.post("/upload/image", summary="上传商品图片")
async def upload_product_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if current_user.role.value != "seller":
        raise_error("ROLE_DENIED", "仅卖家可上传商品图片", status_code=403)

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise_error("INVALID_FORMAT", f"仅支持 {', '.join(ALLOWED_EXTENSIONS)} 格式", status_code=400)

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise_error("FILE_TOO_LARGE", "图片大小不能超过 5MB", status_code=400)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = UPLOAD_DIR / filename
    filepath.write_bytes(content)

    return {"code": "OK", "message": "上传成功", "data": {"url": f"/uploads/products/{filename}"}}


@router.get("/profile", response_model=APIResponse[SellerProfileOut | None], summary="获取商家店铺资料")
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        profile = await seller_service.get_profile(db, current_user)
    except ServiceError as exc:
        _handle_error(exc)
    return {"message": "商家资料获取成功", "data": profile}


@router.put("/profile", response_model=APIResponse[SellerProfileOut], summary="创建/更新商家店铺资料")
async def put_profile(
    payload: SellerProfileUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        profile = await seller_service.put_profile(db, current_user, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"message": "商家资料保存成功", "data": profile}


@router.post("/products", response_model=APIResponse[SellerProductOut], summary="商家创建商品")
async def create_my_product(
    payload: SellerProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        product = await seller_service.create_my_product(db, current_user, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"message": "商品创建成功，待审核", "data": product}


@router.get("/products", response_model=APIResponse[list[SellerProductOut]], summary="商家查看我的商品")
async def list_my_products(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        products = await seller_service.list_my_products(db, current_user)
    except ServiceError as exc:
        _handle_error(exc)
    return {"message": "我的商品列表获取成功", "data": products}


@router.put("/products/{product_id}", response_model=APIResponse[SellerProductOut], summary="商家更新我的商品")
async def update_my_product(
    product_id: int,
    payload: SellerProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        product = await seller_service.update_my_product(db, current_user, product_id, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"message": "商品更新成功，已重新进入待审核", "data": product}


@router.delete("/products/{product_id}", response_model=APIResponse[dict], summary="商家删除我的商品")
async def delete_my_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await seller_service.delete_my_product(db, current_user, product_id)
    except ServiceError as exc:
        _handle_error(exc)
    return {"message": "商品删除成功", "data": {"product_id": product_id}}
