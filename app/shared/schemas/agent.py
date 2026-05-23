from typing import Any

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    user_id: int = Field(..., gt=0)
    session_id: str = Field(..., min_length=1, max_length=120)
    message: str = Field(..., min_length=1, max_length=8000)


class AgentChatResponse(BaseModel):
    answer: str
    session_id: str
    route: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    context: list[dict[str, Any]] = Field(default_factory=list)
    trace_id: str = ""
    routing_source: str = ""
    latency_ms: int = 0
    fallback_reason: str = ""
    ticket_id: int | None = None
