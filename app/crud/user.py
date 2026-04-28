from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.schemas.auth import UserProfileUpdate


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, email: str, password_hash: str, role: UserRole) -> User:
    user = User(email=email, password_hash=password_hash, role=role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user_profile(db: AsyncSession, user: User, payload: UserProfileUpdate) -> User:
    if "display_name" in payload.model_fields_set:
        user.display_name = payload.display_name
    if "phone" in payload.model_fields_set:
        user.phone = payload.phone
    if "avatar_url" in payload.model_fields_set:
        user.avatar_url = payload.avatar_url

    await db.commit()
    await db.refresh(user)
    return user
