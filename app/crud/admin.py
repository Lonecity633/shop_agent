import json

from sqlalchemy import String, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.order import Order, OrderItem, OrderStatus, PayStatus
from app.models.category import Category
from app.models.product import Product, ProductStatus
from app.models.refund import RefundStatus, RefundTicket
from app.models.seller_profile import SellerAuditStatus, SellerProfile
from app.models.user import User, UserRole


async def list_sellers_with_stats(db: AsyncSession) -> list[dict]:
    stmt = (
        select(
            User.id,
            User.email,
            SellerProfile.audit_status.label("shop_audit_status"),
            User.created_at,
            func.count(Product.id).label("total_products"),
            func.sum(case((Product.approval_status == ProductStatus.pending, 1), else_=0)).label(
                "pending_products"
            ),
        )
        .outerjoin(Product, Product.seller_id == User.id)
        .outerjoin(SellerProfile, SellerProfile.user_id == User.id)
        .where(User.role == UserRole.seller)
        .group_by(User.id, User.email, SellerProfile.audit_status, User.created_at)
        .order_by(User.id.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "id": row.id,
            "email": row.email,
            "shop_audit_status": row.shop_audit_status.value if row.shop_audit_status else "not_submitted",
            "created_at": row.created_at,
            "total_products": int(row.total_products or 0),
            "pending_products": int(row.pending_products or 0),
        }
        for row in rows
    ]


async def list_pending_products(db: AsyncSession) -> list[dict]:
    stmt = (
        select(
            Product.id,
            Product.seller_id,
            User.email.label("seller_email"),
            SellerProfile.audit_status.label("seller_shop_audit_status"),
            Product.name,
            Product.description,
            Product.image_urls,
            Product.stock,
            Product.price,
            Category.name.label("category_name"),
            Product.approval_status,
            Product.created_at,
        )
        .join(User, User.id == Product.seller_id)
        .outerjoin(Category, Category.id == Product.category_id)
        .outerjoin(SellerProfile, SellerProfile.user_id == User.id)
        .where(Product.approval_status == ProductStatus.pending)
        .order_by(Product.id.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    def parse_image_urls(raw: str | None) -> list[str]:
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if item]
        except json.JSONDecodeError:
            pass
        return []

    return [
        {
            "id": row.id,
            "seller_id": row.seller_id,
            "seller_email": row.seller_email,
            "seller_shop_audit_status": row.seller_shop_audit_status.value if row.seller_shop_audit_status else "not_submitted",
            "name": row.name,
            "description": row.description,
            "image_urls": parse_image_urls(row.image_urls),
            "stock": row.stock,
            "price": row.price,
            "category_name": row.category_name,
            "approval_status": row.approval_status.value,
            "created_at": row.created_at,
        }
        for row in rows
    ]


async def get_admin_overview(db: AsyncSession) -> dict:
    user_stats_stmt = select(
        func.count(User.id).label("total_users"),
        func.sum(case((User.role == UserRole.buyer, 1), else_=0)).label("total_buyers"),
        func.sum(case((User.role == UserRole.seller, 1), else_=0)).label("total_sellers"),
        func.sum(case((User.role == UserRole.admin, 1), else_=0)).label("total_admins"),
        func.sum(case((func.date(User.created_at) == func.current_date(), 1), else_=0)).label("today_new_users"),
    )
    user_stats = (await db.execute(user_stats_stmt)).one()

    pending_profiles_stmt = select(func.count(SellerProfile.id)).where(SellerProfile.audit_status == SellerAuditStatus.pending)
    pending_profiles_count = (await db.execute(pending_profiles_stmt)).scalar_one()
    pending_products_stmt = select(func.count(Product.id)).where(Product.approval_status == ProductStatus.pending)
    pending_products_count = (await db.execute(pending_products_stmt)).scalar_one()

    order_stats_stmt = select(
        func.count(Order.id).label("total_orders"),
        func.sum(case((Order.status == OrderStatus.pending_paid, 1), else_=0)).label("pending_paid_orders"),
        func.sum(case((Order.status == OrderStatus.paid, 1), else_=0)).label("paid_orders"),
        func.sum(case((Order.status == OrderStatus.shipped, 1), else_=0)).label("shipped_orders"),
        func.sum(case((Order.status == OrderStatus.completed, 1), else_=0)).label("completed_orders"),
        func.sum(case((Order.status.in_([OrderStatus.closed, OrderStatus.cancelled]), 1), else_=0)).label(
            "closed_or_cancelled_orders"
        ),
        func.sum(case((Order.pay_status == PayStatus.refunded, 1), else_=0)).label("refunded_orders"),
        func.sum(case((func.date(Order.created_at) == func.current_date(), 1), else_=0)).label("today_new_orders"),
        func.sum(case((Order.pay_status == PayStatus.paid, Order.pay_amount), else_=0)).label("gmv_paid_total"),
        func.sum(case((func.date(Order.paid_at) == func.current_date(), Order.pay_amount), else_=0)).label(
            "today_paid_amount"
        ),
    )
    order_stats = (await db.execute(order_stats_stmt)).one()

    refund_stats_stmt = select(
        func.sum(case((RefundTicket.status == RefundStatus.requested, 1), else_=0)).label("refund_requested_count"),
        func.sum(case((RefundTicket.status == RefundStatus.seller_rejected, 1), else_=0)).label(
            "refund_seller_rejected_count"
        ),
        func.sum(case((RefundTicket.status == RefundStatus.refunded, 1), else_=0)).label("refund_refunded_count"),
        func.sum(case((RefundTicket.status == RefundStatus.refunded, RefundTicket.amount), else_=0)).label(
            "gmv_refunded_total"
        ),
    )
    refund_stats = (await db.execute(refund_stats_stmt)).one()

    return {
        "total_users": int(user_stats.total_users or 0),
        "total_buyers": int(user_stats.total_buyers or 0),
        "total_sellers": int(user_stats.total_sellers or 0),
        "total_admins": int(user_stats.total_admins or 0),
        "today_new_users": int(user_stats.today_new_users or 0),
        "pending_seller_profiles": int(pending_profiles_count or 0),
        "pending_products": int(pending_products_count or 0),
        "total_orders": int(order_stats.total_orders or 0),
        "pending_paid_orders": int(order_stats.pending_paid_orders or 0),
        "paid_orders": int(order_stats.paid_orders or 0),
        "shipped_orders": int(order_stats.shipped_orders or 0),
        "completed_orders": int(order_stats.completed_orders or 0),
        "closed_or_cancelled_orders": int(order_stats.closed_or_cancelled_orders or 0),
        "refunded_orders": int(order_stats.refunded_orders or 0),
        "today_new_orders": int(order_stats.today_new_orders or 0),
        "gmv_paid_total": order_stats.gmv_paid_total or 0,
        "gmv_refunded_total": refund_stats.gmv_refunded_total or 0,
        "today_paid_amount": order_stats.today_paid_amount or 0,
        "refund_requested_count": int(refund_stats.refund_requested_count or 0),
        "refund_seller_rejected_count": int(refund_stats.refund_seller_rejected_count or 0),
        "refund_refunded_count": int(refund_stats.refund_refunded_count or 0),
    }


async def list_recent_orders(db: AsyncSession, limit: int = 20) -> list[dict]:
    buyer = aliased(User)
    seller = aliased(User)
    stmt = (
        select(
            Order.id,
            Order.user_id,
            buyer.email.label("buyer_email"),
            Product.seller_id.label("seller_id"),
            seller.email.label("seller_email"),
            Order.product_id,
            OrderItem.product_name_snapshot.label("product_name"),
            Order.status,
            Order.pay_status,
            Order.pay_amount,
            Order.created_at,
            Order.paid_at,
            Order.shipped_at,
        )
        .join(buyer, buyer.id == Order.user_id)
        .join(Product, Product.id == Order.product_id)
        .join(seller, seller.id == Product.seller_id)
        .outerjoin(OrderItem, OrderItem.order_id == Order.id)
        .order_by(Order.id.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "buyer_email": row.buyer_email,
            "seller_id": row.seller_id,
            "seller_email": row.seller_email,
            "product_id": row.product_id,
            "product_name": row.product_name or "",
            "status": row.status.value,
            "pay_status": row.pay_status.value,
            "pay_amount": row.pay_amount,
            "created_at": row.created_at,
            "paid_at": row.paid_at,
            "shipped_at": row.shipped_at,
        }
        for row in rows
    ]


async def list_refund_cases(db: AsyncSession, status: str | None = None, limit: int = 50) -> list[dict]:
    buyer_user = aliased(User)
    seller_user = aliased(User)
    stmt = (
        select(
            RefundTicket.id,
            RefundTicket.order_id,
            RefundTicket.buyer_id,
            RefundTicket.seller_id,
            RefundTicket.status,
            RefundTicket.amount,
            RefundTicket.reason,
            RefundTicket.buyer_note,
            RefundTicket.seller_note,
            RefundTicket.admin_note,
            RefundTicket.created_at,
            RefundTicket.updated_at,
            Order.status.label("order_status"),
            Order.pay_status.label("order_pay_status"),
            buyer_user.email.label("buyer_email"),
            seller_user.email.label("seller_email"),
        )
        .join(Order, Order.id == RefundTicket.order_id)
        .join(buyer_user, buyer_user.id == RefundTicket.buyer_id)
        .join(seller_user, seller_user.id == RefundTicket.seller_id)
    )
    if status and status != "all":
        try:
            status_enum = RefundStatus(status)
        except ValueError:
            status_enum = None
        if status_enum is not None:
            stmt = stmt.where(RefundTicket.status == status_enum)
    stmt = stmt.order_by(RefundTicket.id.desc()).limit(limit)
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": row.id,
            "order_id": row.order_id,
            "buyer_id": row.buyer_id,
            "buyer_email": row.buyer_email,
            "seller_id": row.seller_id,
            "seller_email": row.seller_email,
            "status": row.status.value,
            "amount": row.amount,
            "reason": row.reason,
            "buyer_note": row.buyer_note,
            "seller_note": row.seller_note,
            "admin_note": row.admin_note,
            "order_status": row.order_status.value,
            "order_pay_status": row.order_pay_status.value,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]


async def list_orders_paged(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    status: str | None,
    pay_status: str | None,
    keyword: str | None,
) -> dict:
    buyer = aliased(User)
    seller = aliased(User)
    pattern = f"%{(keyword or '').strip()}%"

    count_stmt = (
        select(func.count(func.distinct(Order.id)))
        .select_from(Order)
        .join(buyer, buyer.id == Order.user_id)
        .join(Product, Product.id == Order.product_id)
        .join(seller, seller.id == Product.seller_id)
        .outerjoin(OrderItem, OrderItem.order_id == Order.id)
    )
    data_stmt = (
        select(
            Order.id,
            Order.user_id,
            buyer.email.label("buyer_email"),
            Product.seller_id.label("seller_id"),
            seller.email.label("seller_email"),
            Order.product_id,
            OrderItem.product_name_snapshot.label("product_name"),
            Order.status,
            Order.pay_status,
            Order.pay_amount,
            Order.inventory_reverted,
            Order.created_at,
            Order.paid_at,
            Order.shipped_at,
            Order.updated_at,
        )
        .join(buyer, buyer.id == Order.user_id)
        .join(Product, Product.id == Order.product_id)
        .join(seller, seller.id == Product.seller_id)
        .outerjoin(OrderItem, OrderItem.order_id == Order.id)
    )
    if status:
        try:
            status_enum = OrderStatus(status)
            count_stmt = count_stmt.where(Order.status == status_enum)
            data_stmt = data_stmt.where(Order.status == status_enum)
        except ValueError:
            pass
    if pay_status:
        try:
            pay_status_enum = PayStatus(pay_status)
            count_stmt = count_stmt.where(Order.pay_status == pay_status_enum)
            data_stmt = data_stmt.where(Order.pay_status == pay_status_enum)
        except ValueError:
            pass
    if keyword and keyword.strip():
        cond = or_(buyer.email.like(pattern), seller.email.like(pattern), OrderItem.product_name_snapshot.like(pattern))
        count_stmt = count_stmt.where(cond)
        data_stmt = data_stmt.where(cond)

    total = int((await db.execute(count_stmt)).scalar_one() or 0)
    rows = (
        await db.execute(
            data_stmt.order_by(Order.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items = [
        {
            "id": row.id,
            "user_id": row.user_id,
            "buyer_email": row.buyer_email,
            "seller_id": row.seller_id,
            "seller_email": row.seller_email,
            "product_id": row.product_id,
            "product_name": row.product_name or "",
            "status": row.status.value,
            "pay_status": row.pay_status.value,
            "pay_amount": row.pay_amount,
            "inventory_reverted": bool(row.inventory_reverted),
            "created_at": row.created_at,
            "paid_at": row.paid_at,
            "shipped_at": row.shipped_at,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def list_refund_cases_paged(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    status: str | None,
    keyword: str | None,
) -> dict:
    buyer_user = aliased(User)
    seller_user = aliased(User)
    pattern = f"%{(keyword or '').strip()}%"

    count_stmt = (
        select(func.count(RefundTicket.id))
        .select_from(RefundTicket)
        .join(Order, Order.id == RefundTicket.order_id)
        .join(buyer_user, buyer_user.id == RefundTicket.buyer_id)
        .join(seller_user, seller_user.id == RefundTicket.seller_id)
    )
    data_stmt = (
        select(
            RefundTicket.id,
            RefundTicket.order_id,
            RefundTicket.buyer_id,
            RefundTicket.seller_id,
            RefundTicket.status,
            RefundTicket.amount,
            RefundTicket.reason,
            RefundTicket.buyer_note,
            RefundTicket.seller_note,
            RefundTicket.admin_note,
            RefundTicket.created_at,
            RefundTicket.updated_at,
            Order.status.label("order_status"),
            Order.pay_status.label("order_pay_status"),
            buyer_user.email.label("buyer_email"),
            seller_user.email.label("seller_email"),
        )
        .join(Order, Order.id == RefundTicket.order_id)
        .join(buyer_user, buyer_user.id == RefundTicket.buyer_id)
        .join(seller_user, seller_user.id == RefundTicket.seller_id)
    )
    if status and status != "all":
        try:
            status_enum = RefundStatus(status)
            count_stmt = count_stmt.where(RefundTicket.status == status_enum)
            data_stmt = data_stmt.where(RefundTicket.status == status_enum)
        except ValueError:
            pass
    if keyword and keyword.strip():
        cond = or_(
            buyer_user.email.like(pattern),
            seller_user.email.like(pattern),
            cast(RefundTicket.order_id, String).like(pattern),
        )
        count_stmt = count_stmt.where(cond)
        data_stmt = data_stmt.where(cond)

    total = int((await db.execute(count_stmt)).scalar_one() or 0)
    rows = (
        await db.execute(
            data_stmt.order_by(RefundTicket.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items = [
        {
            "id": row.id,
            "order_id": row.order_id,
            "buyer_id": row.buyer_id,
            "buyer_email": row.buyer_email,
            "seller_id": row.seller_id,
            "seller_email": row.seller_email,
            "status": row.status.value,
            "amount": row.amount,
            "reason": row.reason,
            "buyer_note": row.buyer_note,
            "seller_note": row.seller_note,
            "admin_note": row.admin_note,
            "order_status": row.order_status.value,
            "order_pay_status": row.order_pay_status.value,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}
