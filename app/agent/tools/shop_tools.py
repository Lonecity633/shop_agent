from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.product import Product, ProductStatus
from app.models.user import User, UserRole

GET_ORDER_DETAILS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_order_details",
        "description": "当且仅当用户咨询订单进度、物流、签收、退款进度等订单问题，且你可明确提取订单号时调用。若无法确定订单号，请先自然追问，不要调用此工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "订单号原文，必填，例如'SO2026043018050300005002'。",
                }
            },
            "required": ["order_id"],
            "additionalProperties": False,
        },
    },
}


def _to_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return float(value)
    return value


def _order_tool_error(*, order_id: str, error_code: str, message: str) -> dict[str, Any]:
    return {
        "found": False,
        "order_id": order_id,
        "error_code": error_code,
        "message": message,
    }


async def execute_get_order_details(db: AsyncSession, *, current_user: User, order_id: str) -> dict[str, Any]:
    normalized_order_id = order_id.strip()
    if not normalized_order_id:
        return _order_tool_error(order_id="", error_code="INVALID_ARGUMENTS", message="缺少订单号参数")

    try:
        resolved_order = await _resolve_order_for_query(db, current_user, normalized_order_id)
        if resolved_order is None:
            return _order_tool_error(
                order_id=normalized_order_id,
                error_code="ORDER_NOT_FOUND",
                message="未找到订单或无权限查看",
            )

        order_pk, order_no = resolved_order
        snapshot = await fetch_order_snapshot(db, order_pk)
    except SQLAlchemyError:
        return _order_tool_error(
            order_id=normalized_order_id,
            error_code="DB_QUERY_FAILED",
            message="订单查询服务暂时不可用，请稍后重试",
        )
    except Exception:
        return {
            "found": False,
            "order_id": normalized_order_id,
            "error_code": "INTERNAL_TOOL_ERROR",
            "message": "订单查询暂时失败，请稍后重试",
        }

    if snapshot is None:
        return _order_tool_error(
            order_id=normalized_order_id,
            error_code="ORDER_NOT_FOUND",
            message="未找到订单或无权限查看",
        )

    safe_snapshot = _to_json_safe(snapshot)
    return {
        "found": True,
        "order_id": order_no,
        "order_pk": str(safe_snapshot.get("order_id", "")),
        "product_name": safe_snapshot.get("product_name"),
        "order_status": safe_snapshot.get("status"),
        "pay_status": safe_snapshot.get("pay_status"),
        "logistics_company": safe_snapshot.get("logistics_company"),
        "tracking_no": safe_snapshot.get("tracking_no"),
    }


def _base_order_lookup_stmt(current_user: User):
    stmt = select(Order.id, Order.order_no).join(Product, Product.id == Order.product_id)
    if current_user.role == UserRole.admin:
        return stmt
    if current_user.role == UserRole.buyer:
        return stmt.where(Order.user_id == current_user.id)
    if current_user.role == UserRole.seller:
        return stmt.where(Product.seller_id == current_user.id)
    return stmt.where(Order.id == -1)


async def _resolve_order_for_query(db: AsyncSession, current_user: User, order_query: str) -> tuple[int, str] | None:
    by_no_stmt = _base_order_lookup_stmt(current_user).where(Order.order_no == order_query).limit(1)
    row = (await db.execute(by_no_stmt)).first()
    if row is not None:
        return int(row[0]), str(row[1])

    if order_query.isdigit():
        by_id_stmt = _base_order_lookup_stmt(current_user).where(Order.id == int(order_query)).limit(1)
        row = (await db.execute(by_id_stmt)).first()
        if row is not None:
            return int(row[0]), str(row[1])
    return None


async def fetch_order_snapshot(db: AsyncSession, order_id: int) -> dict | None:
    result = await db.execute(
        select(Order, Product)
        .join(Product, Product.id == Order.product_id)
        .where(Order.id == order_id)
    )
    row = result.first()
    if row is None:
        return None
    order, product = row
    return {
        "order_id": order.id,
        "status": order.status.value,
        "pay_status": order.pay_status.value,
        "tracking_no": order.tracking_no,
        "logistics_company": order.logistics_company,
        "product_id": product.id,
        "product_name": product.name,
        "seller_id": product.seller_id,
    }


async def fetch_product_snapshot(db: AsyncSession, product_id: int) -> dict | None:
    result = await db.execute(select(Product).where(Product.id == product_id, Product.is_deleted.is_(False)))
    product = result.scalar_one_or_none()
    if product is None:
        return None
    return {
        "product_id": product.id,
        "name": product.name,
        "price": float(product.price),
        "stock": product.stock,
        "seller_id": product.seller_id,
        "approval_status": product.approval_status.value,
    }


async def search_products_by_keyword(db: AsyncSession, keyword: str, limit: int = 5) -> list[dict]:
    text = keyword.strip()
    if not text:
        return []

    pattern = f"%{text}%"
    stmt = (
        select(Product)
        .where(
            Product.is_deleted.is_(False),
            Product.approval_status == ProductStatus.approved,
            or_(Product.name.like(pattern), Product.description.like(pattern)),
        )
        .order_by(Product.id.desc())
        .limit(max(1, min(limit, 10)))
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "product_id": item.id,
            "name": item.name,
            "price": float(item.price),
            "stock": item.stock,
            "seller_id": item.seller_id,
            "approval_status": item.approval_status.value,
        }
        for item in rows
    ]
