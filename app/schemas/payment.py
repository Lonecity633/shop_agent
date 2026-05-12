from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PaymentInitiatePayload(BaseModel):
    channel: str = Field(default="mock_alipay", min_length=1, max_length=32)


class MockPaymentCallbackPayload(BaseModel):
    result: Literal["success", "failed"]
    failure_reason: str = Field(default="", max_length=2000)


class PaymentTransactionOut(BaseModel):
    id: int
    payment_no: str
    order_id: int
    order_no: str | None = None
    buyer_id: int
    channel: str
    amount: Decimal
    status: str
    provider_trade_no: str
    failure_reason: str
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
