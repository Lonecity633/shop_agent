from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RefundCreate(BaseModel):
    order_id: int = Field(..., gt=0)
    reason: str = Field(..., min_length=1, max_length=2000)
    buyer_note: str = Field(default="", max_length=2000)


class RefundSellerReview(BaseModel):
    action: Literal["approve", "reject"]
    seller_note: str = Field(default="", max_length=2000)


class RefundAdminReview(BaseModel):
    action: Literal["approve", "reject"]
    admin_note: str = Field(default="", max_length=2000)


class RefundExecutePayload(BaseModel):
    result: Literal["success", "failed"] = Field(..., description="模拟退款执行结果")
    fail_reason: str = Field(default="", max_length=2000)


class RefundOut(BaseModel):
    id: int
    order_id: int
    buyer_id: int
    seller_id: int
    status: str
    amount: Decimal
    reason: str
    buyer_note: str
    seller_note: str
    admin_note: str
    fail_reason: str
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
