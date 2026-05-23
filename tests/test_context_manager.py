import asyncio

from app.agent.context_manager import ContextManager
from app.agent.memory_store import InMemoryMemoryStore


async def _summary(previous_summary, messages, entities):
    return f"{previous_summary} 已压缩{len(messages)}条，订单{entities.get('order_id', '')}".strip()


async def _failing_summary(previous_summary, messages, entities):
    raise RuntimeError("summary failed")


def test_context_memory_isolated_by_user_and_session():
    context = ContextManager()

    asyncio.run(context.append(1, "same-session", role="user", content="我的订单 123 到哪了"))
    asyncio.run(context.append(2, "same-session", role="user", content="我的订单 456 到哪了"))

    user_one_history = asyncio.run(context.get_history(1, "same-session"))
    user_two_history = asyncio.run(context.get_history(2, "same-session"))

    assert user_one_history == [{"role": "user", "content": "我的订单 123 到哪了"}]
    assert user_two_history == [{"role": "user", "content": "我的订单 456 到哪了"}]


def test_context_memory_compacts_to_summary_and_recent_messages():
    context = ContextManager(recent_messages=12, summary_trigger_messages=16, summary_max_chars=800)
    for idx in range(18):
        asyncio.run(context.append(1, "s1", role="user", content=f"第{idx}条，订单 123"))

    asyncio.run(
        context.compact_if_needed(
            1,
            "s1",
            _summary,
            tool_calls=[{"arguments": {"order_id": "SO12345678", "product_id": 9, "refund_id": 3}}],
            route="order_query",
        )
    )

    state = context.get_state(1, "s1")
    history = asyncio.run(context.get_history(1, "s1"))

    assert len(state.recent_messages) == 12
    assert state.summary
    assert state.entities["order_id"] == "SO12345678"
    assert state.entities["product_id"] == 9
    assert state.entities["refund_id"] == 3
    assert state.entities["last_route"] == "order_query"
    assert history[0]["role"] == "memory"
    assert "会话摘要" in history[0]["content"]
    assert "关键实体" in history[0]["content"]
    assert len(history) == 13


def test_context_memory_summary_failure_still_trims_window():
    context = ContextManager(recent_messages=2, summary_trigger_messages=3)
    for idx in range(5):
        asyncio.run(context.append(1, "s1", role="user", content=f"第{idx}条，订单 123"))

    asyncio.run(context.compact_if_needed(1, "s1", _failing_summary, route="order_query"))

    state = context.get_state(1, "s1")
    history = asyncio.run(context.get_history(1, "s1"))

    assert state.summary == ""
    assert len(state.recent_messages) == 2
    assert state.entities["order_id"] == "123"
    assert history[0]["role"] == "memory"
    assert "order_id" in history[0]["content"]


def test_context_memory_does_not_summarize_under_threshold():
    context = ContextManager(recent_messages=2, summary_trigger_messages=4)
    for idx in range(4):
        asyncio.run(context.append(1, "s1", role="user", content=f"第{idx}条"))

    asyncio.run(context.compact_if_needed(1, "s1", _summary))

    state = context.get_state(1, "s1")
    assert state.summary == ""
    assert len(state.recent_messages) == 4


def test_context_memory_can_use_persistent_store_adapter():
    store = InMemoryMemoryStore()
    context = ContextManager(memory_store=store)

    asyncio.run(context.append(1, "s1", role="user", content="我的订单 SO12345678 到哪了"))
    asyncio.run(context.compact_if_needed(1, "s1", _summary, route="order_query"))

    reloaded = ContextManager(memory_store=store)
    history = asyncio.run(reloaded.get_history(1, "s1"))

    assert history[0]["role"] == "memory"
    assert "SO12345678" in history[0]["content"]
