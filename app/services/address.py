from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import address as address_crud
from app.models.user import User, UserRole
from app.schemas.address import AddressCreate, AddressUpdate
from app.services.common import ensure


def _ensure_buyer(user: User) -> None:
    ensure(user.role == UserRole.buyer, "ROLE_DENIED", "仅买家可管理收货地址", 403)


async def list_addresses(db: AsyncSession, current_user: User):
    _ensure_buyer(current_user)
    return await address_crud.list_addresses(db, current_user.id)


async def create_address(db: AsyncSession, current_user: User, payload: AddressCreate):
    _ensure_buyer(current_user)
    return await address_crud.create_address(db, current_user.id, payload)


async def update_address(db: AsyncSession, current_user: User, address_id: int, payload: AddressUpdate):
    _ensure_buyer(current_user)
    address = await address_crud.get_address(db, address_id)
    ensure(address is not None and address.user_id == current_user.id, "ADDRESS_NOT_FOUND", "地址不存在", 404)
    return await address_crud.update_address(db, address, payload)


async def delete_address(db: AsyncSession, current_user: User, address_id: int):
    _ensure_buyer(current_user)
    address = await address_crud.get_address(db, address_id)
    ensure(address is not None and address.user_id == current_user.id, "ADDRESS_NOT_FOUND", "地址不存在", 404)
    await address_crud.delete_address(db, address)
