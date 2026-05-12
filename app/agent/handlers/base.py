from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm_client import LLMClient
from app.models.user import User


@dataclass
class HandlerContext:
    db: AsyncSession
    current_user: User
    content: str
    history: list[dict]
    session_id: int
    order_id: int | None
    product_id: int | None
    llm_client: LLMClient


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
