from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OrderCreate(BaseModel):
    product_id: int = Field(..., gt=0, description="商品ID")
    address_id: int = Field(..., gt=0, description="地址ID")
    quantity: int = Field(default=1, ge=1, le=99, description="购买数量")


class OrderPayPayload(BaseModel):
    pay_channel: str = Field(default="simulated", min_length=1, max_length=32)


class OrderClosePayload(BaseModel):
    reason: str = Field(default="订单超时未支付", max_length=255)


class OrderStatusUpdate(BaseModel):
    status: Literal["cancelled"] = Field(..., description="买家仅可取消订单")


class ShipOrderPayload(BaseModel):
    tracking_no: str = Field(..., min_length=1, max_length=64)
    logistics_company: str = Field(..., min_length=1, max_length=120)


class ReceiveOrderPayload(BaseModel):
    reason: str = Field(default="买家确认收货", max_length=500)


class OrderCommentCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    content: str = Field(default="", max_length=2000)


class OrderItemOut(BaseModel):
    id: int
    order_id: int
    product_id: int
    product_name_snapshot: str
    unit_price_snapshot: Decimal
    quantity: int
    subtotal: Decimal

    model_config = ConfigDict(from_attributes=True)


class OrderOut(BaseModel):
    id: int
    user_id: int
    product_id: int
    status: str
    pay_status: str
    total_price: Decimal
    pay_amount: Decimal
    pay_channel: str
    paid_at: datetime | None
    close_reason: str
    address_snapshot: str

    tracking_no: str
    logistics_company: str
    shipped_at: datetime | None
    received_at: datetime | None
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemOut] = []

    model_config = ConfigDict(from_attributes=True)


class OrderStatusOut(BaseModel):
    order_id: int
    status: str


class OrderStatusLogOut(BaseModel):
    id: int
    order_id: int
    from_status: str
    to_status: str
    actor_id: int
    actor_role: str
    reason: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderCommentOut(BaseModel):
    id: int
    order_id: int
    product_id: int
    user_id: int
    rating: int
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
