from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_agent_session_debug_endpoint_requires_user_id():
    chat_api = (ROOT / "app/agent/api/chat.py").read_text(encoding="utf-8")

    assert 'from fastapi import APIRouter, Query' in chat_api
    assert 'user_id: int = Query(..., gt=0)' in chat_api
    assert 'get_history(user_id, session_id)' in chat_api
