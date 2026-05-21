from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.knowledge import retrieve
from app.backend.core.errors import raise_error
from app.backend.db.session import get_db
from app.backend.models.order import Order
from app.backend.models.payment import PaymentTransaction
from app.backend.models.product import Product, ProductStatus
from app.backend.models.refund import RefundTicket
from app.shared.config import settings
from app.shared.constants import INTERNAL_SECRET_HEADER

router = APIRouter(prefix="/internal/tools", tags=["Internal Tools"])


def verify_internal_secret(x_internal_secret: str = Header(default="", alias=INTERNAL_SECRET_HEADER)) -> None:
    if not x_internal_secret or x_internal_secret != settings.mcp_internal_secret:
        raise_error("INTERNAL_UNAUTHORIZED", "内部工具接口鉴权失败", status_code=401)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return float(value)
    return value


def _tool_response(data: Any, *, success: bool = True, error: str | None = None) -> dict:
    return {"code": "OK" if success else "ERROR", "message": error or "", "data": _json_safe(data)}


def _order_lookup_stmt(user_id: int, user_role: str):
    stmt = select(Order.id, Order.order_no).join(Product, Product.id == Order.product_id)
    if user_role == "admin":
        return stmt
    if user_role == "buyer":
        return stmt.where(Order.user_id == user_id)
    if user_role == "seller":
        return stmt.where(Product.seller_id == user_id)
    return stmt.where(Order.id == -1)


async def _resolve_order(db: AsyncSession, *, user_id: int, user_role: str, order_id: str) -> tuple[int, str] | None:
    by_no = _order_lookup_stmt(user_id, user_role).where(Order.order_no == order_id).limit(1)
    row = (await db.execute(by_no)).first()
    if row is not None:
        return int(row[0]), str(row[1])
    if order_id.isdigit():
        by_id = _order_lookup_stmt(user_id, user_role).where(Order.id == int(order_id)).limit(1)
        row = (await db.execute(by_id)).first()
        if row is not None:
            return int(row[0]), str(row[1])
    return None


async def _order_snapshot(db: AsyncSession, order_pk: int) -> dict | None:
    row = (
        await db.execute(select(Order, Product).join(Product, Product.id == Order.product_id).where(Order.id == order_pk))
    ).first()
    if row is None:
        return None
    order, product = row
    latest_payment = (
        await db.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.order_id == order.id)
            .order_by(PaymentTransaction.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    refunds = (
        await db.execute(select(RefundTicket).where(RefundTicket.order_id == order.id).order_by(RefundTicket.id.desc()).limit(3))
    ).scalars().all()
    return {
        "order_id": order.order_no,
        "order_pk": order.id,
        "status": order.status.value,
        "pay_status": order.pay_status.value,
        "paid_amount": order.pay_amount,
        "pay_channel": order.pay_channel,
        "paid_at": order.paid_at,
        "logistics_company": order.logistics_company,
        "tracking_no": order.tracking_no,
        "product": {
            "product_id": product.id,
            "name": product.name,
            "seller_id": product.seller_id,
        },
        "latest_payment": (
            {
                "payment_no": latest_payment.payment_no,
                "status": latest_payment.status.value,
                "channel": latest_payment.channel,
                "amount": latest_payment.amount,
                "failure_reason": latest_payment.failure_reason,
                "paid_at": latest_payment.paid_at,
            }
            if latest_payment is not None
            else None
        ),
        "refunds": [
            {
                "refund_id": item.id,
                "status": item.status.value,
                "amount": item.amount,
                "reason": item.reason,
                "fail_reason": item.fail_reason,
                "processed_at": item.processed_at,
            }
            for item in refunds
        ],
    }


@router.get("/orders/{order_id}")
async def get_order_detail(
    order_id: str,
    user_id: int = Query(..., gt=0),
    user_role: str = Query(default="buyer"),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_secret),
):
    resolved = await _resolve_order(db, user_id=user_id, user_role=user_role, order_id=order_id.strip())
    if resolved is None:
        return _tool_response({"found": False, "order_id": order_id}, success=False, error="ORDER_NOT_FOUND")
    order_pk, _ = resolved
    data = await _order_snapshot(db, order_pk)
    if data is None:
        return _tool_response({"found": False, "order_id": order_id}, success=False, error="ORDER_NOT_FOUND")
    data["found"] = True
    return _tool_response(data)


@router.get("/users/{user_id}/orders")
async def list_user_orders(
    user_id: int,
    user_role: str = Query(default="buyer"),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_secret),
):
    stmt = select(Order).join(Product, Product.id == Order.product_id).order_by(Order.id.desc()).limit(limit)
    if user_role == "buyer":
        stmt = stmt.where(Order.user_id == user_id)
    elif user_role == "seller":
        stmt = stmt.where(Product.seller_id == user_id)
    elif user_role != "admin":
        stmt = stmt.where(Order.id == -1)
    rows = (await db.execute(stmt)).scalars().all()
    return _tool_response([
        {"order_id": item.order_no, "order_pk": item.id, "status": item.status.value, "pay_status": item.pay_status.value}
        for item in rows
    ])


@router.get("/products/search")
async def search_products(
    keyword: str = Query(..., min_length=1),
    limit: int = Query(default=5, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_secret),
):
    pattern = f"%{keyword.strip()}%"
    stmt = (
        select(Product)
        .where(
            Product.is_deleted.is_(False),
            Product.approval_status == ProductStatus.approved,
            or_(Product.name.like(pattern), Product.description.like(pattern)),
        )
        .order_by(Product.id.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return _tool_response([
        {
            "product_id": item.id,
            "name": item.name,
            "price": item.price,
            "stock": item.stock,
            "seller_id": item.seller_id,
            "approval_status": item.approval_status.value,
        }
        for item in rows
    ])


@router.get("/products/{product_id}")
async def get_product_detail(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_secret),
):
    product = (
        await db.execute(select(Product).where(Product.id == product_id, Product.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if product is None:
        return _tool_response(None, success=False, error="PRODUCT_NOT_FOUND")
    return _tool_response(
        {
            "product_id": product.id,
            "name": product.name,
            "description": product.description,
            "price": product.price,
            "stock": product.stock,
            "seller_id": product.seller_id,
            "approval_status": product.approval_status.value,
        }
    )


@router.get("/refunds/{refund_id}")
async def get_refund_status(
    refund_id: int,
    user_id: int = Query(..., gt=0),
    user_role: str = Query(default="buyer"),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_secret),
):
    stmt = select(RefundTicket).where(RefundTicket.id == refund_id)
    if user_role == "buyer":
        stmt = stmt.where(RefundTicket.buyer_id == user_id)
    elif user_role == "seller":
        stmt = stmt.where(RefundTicket.seller_id == user_id)
    elif user_role != "admin":
        stmt = stmt.where(RefundTicket.id == -1)
    refund = (await db.execute(stmt)).scalar_one_or_none()
    if refund is None:
        return _tool_response(None, success=False, error="REFUND_NOT_FOUND")
    return _tool_response(
        {
            "refund_id": refund.id,
            "order_id": refund.order_id,
            "status": refund.status.value,
            "amount": refund.amount,
            "reason": refund.reason,
            "fail_reason": refund.fail_reason,
            "processed_at": refund.processed_at,
        }
    )


@router.get("/knowledge/policies/search")
async def search_after_sale_policy(
    query: str = Query(..., min_length=1),
    top_k: int = Query(default=5, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_secret),
):
    return _tool_response(await retrieve(db, query, top_k=top_k))

