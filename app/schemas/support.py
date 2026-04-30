from datetime import datetime
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class SupportMySessionCreate(BaseModel):
    question: str = Field(default="", max_length=4000)
    queried_entities: list[dict[str, Any]] = Field(default_factory=list)


class SupportSessionOut(BaseModel):
    id: int
    operator_id: int
    user_id: int
    question: str
    answer: str
    queried_entities: list[dict[str, Any]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("queried_entities", mode="before")
    @classmethod
    def parse_queried_entities(cls, value):
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return []
            return parsed if isinstance(parsed, list) else []
        return []


class SupportMessageCreate(BaseModel):
    role: Literal["user", "assistant", "system", "tool"] = "user"
    content: str = Field(..., min_length=1, max_length=8000)
    retrieval_query: str = Field(default="", max_length=4000)


class SupportMessageOut(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    retrieval_query: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupportMessageRecordOut(BaseModel):
    message: SupportMessageOut


class SupportAutoReplyRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)
    order_id: int | None = Field(default=None, gt=0)
    product_id: int | None = Field(default=None, gt=0)


class SupportAutoReplyOut(BaseModel):
    answer: str
    route: str
    resolved_seller_id: int | None
