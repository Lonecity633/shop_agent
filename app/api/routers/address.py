from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user
from app.core.errors import raise_error
from app.db.session import get_db
from app.models.user import User
from app.schemas.address import AddressCreate, AddressOut, AddressUpdate
from app.schemas.common import APIResponse
from app.services import address as address_service
from app.services.common import ServiceError

router = APIRouter(prefix="/addresses", tags=["Addresses"])


def _handle_error(exc: ServiceError):
    raise_error(exc.code, exc.message, status_code=exc.status_code)


@router.get("", response_model=APIResponse[list[AddressOut]])
async def list_addresses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await address_service.list_addresses(db, current_user)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "地址列表获取成功", "data": data}


@router.post("", response_model=APIResponse[AddressOut])
async def create_address(
    payload: AddressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await address_service.create_address(db, current_user, payload)
    except ServiceError as exc:
        _handle_error(exc)
    return {"code": "OK", "message": "地址创建成功", "data": data}


@router.put("/{address_id}", response_model=APIResponse[AddressOut])
async def update_address(
    address_id: int,
    payload: AddressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await address_service.update_address(db, current_user, address_id, payload)
    except ServiceError as exc:
        _handle_error(exc)

    return {"code": "OK", "message": "地址更新成功", "data": data}


@router.delete("/{address_id}", response_model=APIResponse[dict])
async def delete_address(
    address_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await address_service.delete_address(db, current_user, address_id)
    except ServiceError as exc:
        _handle_error(exc)

    return {"code": "OK", "message": "地址删除成功", "data": {"address_id": address_id}}
