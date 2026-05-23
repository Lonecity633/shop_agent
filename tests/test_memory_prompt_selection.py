import json

from app.agent.llm_router import LLMRouter, select_prompt_history
from app.agent.response_generator import ResponseGenerator


def _long_history():
    return [{"role": "memory", "content": '关键实体：{"order_id":"SO12345678"}'}] + [
        {"role": "user" if idx % 2 == 0 else "assistant", "content": f"第{idx}条普通历史"}
        for idx in range(10)
    ]


def test_select_prompt_history_keeps_memory_when_history_is_long():
    selected = select_prompt_history(_long_history(), recent_limit=6)

    assert selected[0]["role"] == "memory"
    assert "SO12345678" in selected[0]["content"]
    assert len(selected) == 7
    assert selected[-1]["content"] == "第9条普通历史"


def test_llm_router_prompt_keeps_memory_when_history_is_long():
    prompt = LLMRouter._user_prompt(message="现在到哪了", history=_long_history())

    assert 'memory: 关键实体：{"order_id":"SO12345678"}' in prompt
    assert "第0条普通历史" not in prompt
    assert "第9条普通历史" in prompt


def test_response_generator_prompt_keeps_memory_when_history_is_long():
    prompt = ResponseGenerator._user_prompt(
        route="order_query",
        message="现在到哪了",
        tool_result=None,
        history=_long_history(),
        tool_calls=[],
    )
    payload = json.loads(prompt.removeprefix("请根据以下上下文生成最终客服回复：\n"))

    assert 'memory: 关键实体：{"order_id":"SO12345678"}' in payload["recent_history"]
    assert "第0条普通历史" not in payload["recent_history"]
    assert "第9条普通历史" in payload["recent_history"]
