from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.address import UserAddress
from app.schemas.address import AddressCreate, AddressUpdate


async def list_addresses(db: AsyncSession, user_id: int) -> list[UserAddress]:
    result = await db.execute(
        select(UserAddress).where(UserAddress.user_id == user_id).order_by(UserAddress.is_default.desc(), UserAddress.id.desc())
    )
    return list(result.scalars().all())


async def get_address(db: AsyncSession, address_id: int) -> UserAddress | None:
    result = await db.execute(select(UserAddress).where(UserAddress.id == address_id))
    return result.scalar_one_or_none()


async def create_address(db: AsyncSession, user_id: int, payload: AddressCreate) -> UserAddress:
    if payload.is_default:
        result = await db.execute(select(UserAddress).where(UserAddress.user_id == user_id, UserAddress.is_default.is_(True)))
        for row in result.scalars().all():
            row.is_default = False

    address = UserAddress(user_id=user_id, **payload.model_dump())
    db.add(address)
    await db.commit()
    await db.refresh(address)
    return address


async def update_address(db: AsyncSession, address: UserAddress, payload: AddressUpdate) -> UserAddress:
    update_data = payload.model_dump(exclude_unset=True)
    if update_data.get("is_default"):
        result = await db.execute(
            select(UserAddress).where(UserAddress.user_id == address.user_id, UserAddress.is_default.is_(True), UserAddress.id != address.id)
        )
        for row in result.scalars().all():
            row.is_default = False

    for field, value in update_data.items():
        setattr(address, field, value)

    await db.commit()
    await db.refresh(address)
    return address


async def delete_address(db: AsyncSession, address: UserAddress) -> None:
    await db.delete(address)
    await db.commit()
