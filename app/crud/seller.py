from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.seller_profile import SellerAuditStatus, SellerProfile
from app.schemas.seller import SellerProfileUpsert


async def get_seller_profile_by_user_id(db: AsyncSession, user_id: int) -> SellerProfile | None:
    result = await db.execute(select(SellerProfile).where(SellerProfile.user_id == user_id))
    return result.scalar_one_or_none()


async def upsert_seller_profile(db: AsyncSession, user_id: int, payload: SellerProfileUpsert) -> SellerProfile:
    profile = await get_seller_profile_by_user_id(db, user_id)
    if profile is None:
        profile = SellerProfile(
            user_id=user_id,
            shop_name=payload.shop_name,
            shop_description=payload.shop_description,
        )
        db.add(profile)
    else:
        profile.shop_name = payload.shop_name
        profile.shop_description = payload.shop_description
        profile.audit_status = SellerAuditStatus.pending

    await db.commit()
    await db.refresh(profile)
    return profile


async def list_pending_seller_profiles(db: AsyncSession) -> list[SellerProfile]:
    result = await db.execute(
        select(SellerProfile)
        .where(SellerProfile.audit_status == SellerAuditStatus.pending)
        .order_by(SellerProfile.id.desc())
    )
    return list(result.scalars().all())


async def get_seller_profile_by_id(db: AsyncSession, profile_id: int) -> SellerProfile | None:
    result = await db.execute(select(SellerProfile).where(SellerProfile.id == profile_id))
    return result.scalar_one_or_none()


async def audit_seller_profile(
    db: AsyncSession,
    profile: SellerProfile,
    approval_status: str,
) -> SellerProfile:
    profile.audit_status = SellerAuditStatus(approval_status)
    await db.commit()
    await db.refresh(profile)
    return profile
