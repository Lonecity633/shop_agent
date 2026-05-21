import asyncio
from types import SimpleNamespace

import pytest

from app.backend.clients.agent_client import AgentAPIClient, AgentAPIClientError
from app.backend.models.user import UserRole
from app.backend.services import support as support_service
from app.backend.services.common import ServiceError
from app.backend.services.rate_limit import RateLimitResult


class FakeRateLimitService:
    async def check_support_reply(self, user_id):
        return RateLimitResult(
            allowed=True,
            window="",
            retry_after_seconds=0,
            short_count=1,
            long_count=1,
        )


def test_auto_reply_persists_user_and_assistant_messages(monkeypatch):
    saved_messages = []

    async def fake_get_support_session(db, session_id):
        return SimpleNamespace(id=session_id, user_id=7)

    async def fake_create_support_message(db, session_id, payload):
        message = SimpleNamespace(
            id=len(saved_messages) + 1,
            session_id=session_id,
            role=payload.role,
            content=payload.content,
        )
        saved_messages.append(message)
        return {"message": message}

    async def fake_agent_chat(self, *, user_id, session_id, message):
        return {
            "answer": "订单正在配送中。",
            "route": "order_query",
            "tool_calls": [{"name": "get_order_detail"}],
        }

    monkeypatch.setattr(support_service.support_crud, "get_support_session", fake_get_support_session)
    monkeypatch.setattr(support_service.support_crud, "create_support_message", fake_create_support_message)
    monkeypatch.setattr(support_service, "rate_limit_service", FakeRateLimitService())
    monkeypatch.setattr(AgentAPIClient, "chat", fake_agent_chat)

    result = asyncio.run(
        support_service.auto_reply(
            db=None,
            current_user=SimpleNamespace(id=7, role=UserRole.buyer),
            session_id=123,
            payload=SimpleNamespace(content="我的订单 123 到哪了"),
        )
    )

    assert result["answer"] == "订单正在配送中。"
    assert result["route"] == "order_query"
    assert [item.role for item in saved_messages] == ["user", "assistant"]
    assert saved_messages[0].content == "我的订单 123 到哪了"
    assert saved_messages[1].content == "订单正在配送中。"


def test_auto_reply_keeps_user_message_when_agent_fails(monkeypatch):
    saved_messages = []

    async def fake_get_support_session(db, session_id):
        return SimpleNamespace(id=session_id, user_id=7)

    async def fake_create_support_message(db, session_id, payload):
        message = SimpleNamespace(
            id=len(saved_messages) + 1,
            session_id=session_id,
            role=payload.role,
            content=payload.content,
        )
        saved_messages.append(message)
        return {"message": message}

    async def fake_agent_chat(self, *, user_id, session_id, message):
        raise AgentAPIClientError("智能客服服务暂不可用")

    monkeypatch.setattr(support_service.support_crud, "get_support_session", fake_get_support_session)
    monkeypatch.setattr(support_service.support_crud, "create_support_message", fake_create_support_message)
    monkeypatch.setattr(support_service, "rate_limit_service", FakeRateLimitService())
    monkeypatch.setattr(AgentAPIClient, "chat", fake_agent_chat)

    with pytest.raises(ServiceError) as exc:
        asyncio.run(
            support_service.auto_reply(
                db=None,
                current_user=SimpleNamespace(id=7, role=UserRole.buyer),
                session_id=123,
                payload=SimpleNamespace(content="推荐一下商品"),
            )
        )

    assert exc.value.code == "AGENT_SERVICE_UNAVAILABLE"
    assert "暂不可用" in exc.value.message
    assert [item.role for item in saved_messages] == ["user"]
