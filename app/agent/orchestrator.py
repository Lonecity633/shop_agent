from __future__ import annotations

from dataclasses import dataclass

from app.agent.service import AgentService


@dataclass
class AgentReplyResult:
    answer: str
    route: str
    resolved_seller_id: int | None
    evidences: list[dict]
    support_ticket: dict | None = None


class SupportAgentOrchestrator:
    """Compatibility wrapper around the standalone AgentService."""

    def __init__(self) -> None:
        self.service = AgentService()

    async def reply(
        self,
        _legacy_context,
        *,
        current_user,
        session_id: int,
        content: str,
        order_id: int | None,
        product_id: int | None,
    ) -> AgentReplyResult:
        response = await self.service.handle_message(
            user_id=int(current_user.id),
            session_id=str(session_id),
            message=content,
        )
        return AgentReplyResult(
            answer=response.answer,
            route=response.route,
            resolved_seller_id=None,
            evidences=response.tool_calls,
            support_ticket=None,
        )

