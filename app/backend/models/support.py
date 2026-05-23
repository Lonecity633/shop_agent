from datetime import datetime
from decimal import Decimal

import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.backend.db.base import Base


class SupportSession(Base):
    __tablename__ = "support_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(Text, default="")
    answer: Mapped[str] = mapped_column(Text, default="")
    queried_entities: Mapped[str] = mapped_column(Text, default="[]")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("support_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    retrieval_query: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SupportRetrievalLog(Base):
    __tablename__ = "support_retrieval_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("support_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("support_messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("kb_documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    chunk_id: Mapped[int | None] = mapped_column(
        ForeignKey("kb_chunks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    is_cited: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SupportTicketStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    replied = "replied"
    escalated = "escalated"
    closed = "closed"
    cancelled = "cancelled"


class SupportTicketCategory(str, enum.Enum):
    product_consultation = "product_consultation"
    logistics_issue = "logistics_issue"
    refund_issue = "refund_issue"
    quality_issue = "quality_issue"
    complaint = "complaint"
    payment_issue = "payment_issue"
    platform_rule = "platform_rule"
    other = "other"


class SupportTicketSource(str, enum.Enum):
    user = "user"
    agent = "agent"
    guardrail = "guardrail"
    seller_escalation = "seller_escalation"


class SupportTicketPriority(str, enum.Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class SupportTicketAssignedRole(str, enum.Enum):
    seller = "seller"
    admin = "admin"


class SupportAgentMemory(Base):
    __tablename__ = "support_agent_memories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    entities_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    recent_messages_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    last_route: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    last_tool_calls_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SupportFollowupStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class SupportFollowup(Base):
    __tablename__ = "support_followups"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(120), default="", nullable=False, index=True)
    business_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    business_id: Mapped[str] = mapped_column(String(120), default="", nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[SupportFollowupStatus] = mapped_column(
        Enum(SupportFollowupStatus, native_enum=False),
        default=SupportFollowupStatus.pending,
        nullable=False,
        index=True,
    )
    payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class MessageOutboxStatus(str, enum.Enum):
    pending = "pending"
    sending = "sending"
    sent = "sent"
    failed = "failed"
    dead = "dead"


class MessageOutbox(Base):
    __tablename__ = "message_outbox"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(64), default="in_app", nullable=False, index=True)
    recipient_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id: Mapped[str] = mapped_column(String(120), default="", nullable=False, index=True)
    message_type: Mapped[str] = mapped_column(String(64), default="support_reply", nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    status: Mapped[MessageOutboxStatus] = mapped_column(
        Enum(MessageOutboxStatus, native_enum=False),
        default=MessageOutboxStatus.pending,
        nullable=False,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    source_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("support_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    seller_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_role: Mapped[SupportTicketAssignedRole] = mapped_column(
        Enum(SupportTicketAssignedRole, native_enum=False),
        nullable=False,
        index=True,
    )
    assigned_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[SupportTicketStatus] = mapped_column(
        Enum(SupportTicketStatus, native_enum=False),
        default=SupportTicketStatus.pending,
        nullable=False,
        index=True,
    )
    category: Mapped[SupportTicketCategory] = mapped_column(
        Enum(SupportTicketCategory, native_enum=False),
        default=SupportTicketCategory.other,
        nullable=False,
        index=True,
    )
    priority: Mapped[SupportTicketPriority] = mapped_column(
        Enum(SupportTicketPriority, native_enum=False),
        default=SupportTicketPriority.normal,
        nullable=False,
        index=True,
    )
    source: Mapped[SupportTicketSource] = mapped_column(
        Enum(SupportTicketSource, native_enum=False),
        default=SupportTicketSource.user,
        nullable=False,
        index=True,
    )
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    refund_id: Mapped[int | None] = mapped_column(
        ForeignKey("refund_tickets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    ai_summary: Mapped[str] = mapped_column(Text, default="")
    ai_trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    trigger_reason: Mapped[str] = mapped_column(Text, default="")
    guardrail_flags: Mapped[str] = mapped_column(Text, default="[]")
    reply_content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
