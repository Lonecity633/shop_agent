from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SupportOverviewOut(BaseModel):
    user_id: int
    email: str
    role: str
    recent_orders: list[dict[str, Any]]
    recent_refunds: list[dict[str, Any]]
    recent_comments: list[dict[str, Any]]


class SupportTimelineOut(BaseModel):
    order_id: int
    payment_event: dict[str, Any]
    status_logs: list[dict[str, Any]]
    refund_events: list[dict[str, Any]]


class SupportSessionCreate(BaseModel):
    user_id: int = Field(..., gt=0)
    question: str = Field(default="", max_length=4000)
    answer: str = Field(default="", max_length=4000)
    queried_entities: list[dict[str, Any]] = Field(default_factory=list)


class SupportSessionOut(BaseModel):
    id: int
    operator_id: int
    user_id: int
    question: str
    answer: str
    queried_entities: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
