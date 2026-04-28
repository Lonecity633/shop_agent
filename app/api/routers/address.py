from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import get_current_user
from app.core.errors import raise_error
from app.crud import address as address_crud
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.address import AddressCreate, AddressOut, AddressUpdate
from app.schemas.common import APIResponse

router = APIRouter(prefix="/addresses", tags=["Addresses"])


def ensure_buyer(user: User) -> None:
    if user.role != UserRole.buyer:
        raise_error("ROLE_DENIED", "仅买家可管理收货地址", status_code=403)


@router.get("", response_model=APIResponse[list[AddressOut]])
async def list_addresses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_buyer(current_user)
    data = await address_crud.list_addresses(db, current_user.id)
    return {"code": "OK", "message": "地址列表获取成功", "data": data}


@router.post("", response_model=APIResponse[AddressOut])
async def create_address(
    payload: AddressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_buyer(current_user)
    data = await address_crud.create_address(db, current_user.id, payload)
    return {"code": "OK", "message": "地址创建成功", "data": data}


@router.put("/{address_id}", response_model=APIResponse[AddressOut])
async def update_address(
    address_id: int,
    payload: AddressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_buyer(current_user)
    address = await address_crud.get_address(db, address_id)
    if not address or address.user_id != current_user.id:
        raise_error("ADDRESS_NOT_FOUND", "地址不存在", status_code=404)

    data = await address_crud.update_address(db, address, payload)
    return {"code": "OK", "message": "地址更新成功", "data": data}


@router.delete("/{address_id}", response_model=APIResponse[dict])
async def delete_address(
    address_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_buyer(current_user)
    address = await address_crud.get_address(db, address_id)
    if not address or address.user_id != current_user.id:
        raise_error("ADDRESS_NOT_FOUND", "地址不存在", status_code=404)

    await address_crud.delete_address(db, address)
    return {"code": "OK", "message": "地址删除成功", "data": {"address_id": address_id}}
