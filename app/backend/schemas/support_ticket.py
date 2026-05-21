from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


TicketStatus = Literal["pending", "processing", "replied", "escalated", "closed", "cancelled"]
TicketCategory = Literal[
    "product_consultation",
    "logistics_issue",
    "refund_issue",
    "quality_issue",
    "complaint",
    "payment_issue",
    "platform_rule",
    "other",
]
TicketPriority = Literal["low", "normal", "high", "urgent"]
TicketSource = Literal["user", "agent", "guardrail", "seller_escalation"]
TicketAssignedRole = Literal["seller", "admin"]


class SupportTicketCreate(BaseModel):
    source_session_id: int | None = Field(default=None, gt=0)
    order_id: int | None = Field(default=None, gt=0)
    product_id: int | None = Field(default=None, gt=0)
    refund_id: int | None = Field(default=None, gt=0)
    category: TicketCategory = "other"
    priority: TicketPriority = "normal"
    source: TicketSource = "user"
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=8000)
    ai_summary: str = Field(default="", max_length=4000)
    ai_trace_id: str | None = Field(default=None, max_length=120)
    trigger_reason: str = Field(default="", max_length=2000)
    guardrail_flags: list[str] = Field(default_factory=list)


class SupportTicketResolve(BaseModel):
    reply_content: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        validation_alias=AliasChoices("reply_content", "resolution"),
    )


class SupportTicketReject(BaseModel):
    reply_content: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        validation_alias=AliasChoices("reply_content", "resolution"),
    )


class SupportTicketClose(BaseModel):
    reply_content: str = Field(
        default="",
        max_length=8000,
        validation_alias=AliasChoices("reply_content", "resolution"),
    )


class SupportTicketEscalate(BaseModel):
    reason: str = Field(..., min_length=1, max_length=4000)


class SupportTicketOut(BaseModel):
    id: int
    source_session_id: int | None
    buyer_id: int
    seller_id: int | None
    admin_id: int | None
    assigned_role: str
    assigned_id: int | None
    status: str
    category: str
    priority: str
    source: str
    order_id: int | None
    product_id: int | None
    refund_id: int | None
    title: str
    content: str
    ai_summary: str
    ai_trace_id: str | None
    trigger_reason: str
    guardrail_flags: str
    reply_content: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    escalated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
