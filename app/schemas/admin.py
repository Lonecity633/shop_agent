from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SellerInfoOut(BaseModel):
    id: int
    email: str
    shop_audit_status: str
    created_at: datetime
    total_products: int
    pending_products: int


class PendingProductOut(BaseModel):
    id: int
    seller_id: int
    seller_email: str
    seller_shop_audit_status: str
    name: str
    description: str
    image_urls: list[str]
    stock: int
    price: Decimal
    category_name: str | None
    approval_status: str
    created_at: datetime


class SellerProfileAuditUpdate(BaseModel):
    approval_status: Literal["approved", "rejected"] = Field(..., description="审核状态")


class PendingSellerProfileOut(BaseModel):
    id: int
    user_id: int
    shop_name: str
    shop_description: str
    audit_status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminOverviewOut(BaseModel):
    total_users: int
    total_buyers: int
    total_sellers: int
    total_admins: int
    today_new_users: int
    pending_seller_profiles: int
    pending_products: int

    total_orders: int
    pending_paid_orders: int
    paid_orders: int
    shipped_orders: int
    completed_orders: int
    closed_or_cancelled_orders: int
    refunded_orders: int
    today_new_orders: int

    gmv_paid_total: Decimal
    gmv_refunded_total: Decimal
    today_paid_amount: Decimal

    refund_requested_count: int
    refund_seller_rejected_count: int
    refund_refunded_count: int


class AdminRecentOrderOut(BaseModel):
    id: int
    user_id: int
    buyer_email: str
    seller_id: int
    seller_email: str
    product_id: int
    product_name: str
    status: str
    pay_status: str
    pay_amount: Decimal
    created_at: datetime
    paid_at: datetime | None
    shipped_at: datetime | None


class AdminRefundCaseOut(BaseModel):
    id: int
    order_id: int
    buyer_id: int
    buyer_email: str
    seller_id: int
    seller_email: str
    status: str
    amount: Decimal
    reason: str
    buyer_note: str
    seller_note: str
    admin_note: str
    order_status: str
    order_pay_status: str
    created_at: datetime
    updated_at: datetime


class AdminOrderOut(BaseModel):
    id: int
    user_id: int
    buyer_email: str
    seller_id: int
    seller_email: str
    product_id: int
    product_name: str
    status: str
    pay_status: str
    pay_amount: Decimal
    inventory_reverted: bool
    created_at: datetime
    paid_at: datetime | None
    shipped_at: datetime | None
    updated_at: datetime


class OperationTimelineItemOut(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    action: str
    actor_id: int
    actor_role: str
    before_state: str
    after_state: str
    reason: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
