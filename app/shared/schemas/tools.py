from typing import Any

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    success: bool
    data: Any = None
    error: str | None = None


class ToolCallRecord(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None

