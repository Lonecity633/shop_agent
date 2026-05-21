from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.agent.llm_client import LLMClient


@dataclass
class HandlerContext:
    user_id: int
    user_role: str
    content: str
    history: list[dict]
    session_id: str
    order_id: str | None
    product_id: int | None
    llm_client: LLMClient
    mcp_client: Any = None


@dataclass
class HandlerResult:
    answer: str
    tool_records: list[str] = field(default_factory=list)
    evidences: list[dict] = field(default_factory=list)
    resolved_seller_id: int | None = None


class IntentHandler(ABC):
    @abstractmethod
    async def handle(self, ctx: HandlerContext) -> HandlerResult:
        ...
