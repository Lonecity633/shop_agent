from app.db.base import Base
from app.db.session import engine
from app.models import address, cart, category, comment, favorite, operation_audit, order, payment, product, refund, seller_profile, support, user  # noqa: F401


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
