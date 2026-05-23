from __future__ import annotations

from fastapi import APIRouter, Query

from app.agent.service import AgentService
from app.shared.schemas.agent import AgentChatRequest, AgentChatResponse

router = APIRouter(prefix="/agent", tags=["Agent"])
agent_service = AgentService()


@router.post("/chat", response_model=AgentChatResponse)
async def chat(payload: AgentChatRequest) -> AgentChatResponse:
    return await agent_service.handle_message(
        user_id=payload.user_id,
        session_id=payload.session_id,
        message=payload.message,
    )


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user_id: int = Query(..., gt=0)):
    return {"session_id": session_id, "user_id": user_id, "messages": await agent_service.context_manager.get_history(user_id, session_id)}
