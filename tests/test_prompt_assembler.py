from app.agent.prompt_assembler import PromptAssembler


def test_prompt_assembler_builds_layered_route_prompt():
    prompt = PromptAssembler().route_system_prompt(tools_section="- search_products: Search")

    assert "## 身份" in prompt
    assert "## 可用工具" in prompt
    assert "search_products" in prompt
    assert "create_support_ticket" in prompt
    assert "只输出 JSON" in prompt


def test_prompt_assembler_response_prompt_keeps_fact_boundary():
    prompt = PromptAssembler().response_system_prompt()

    assert "业务事实边界" in prompt
    assert "不要编造" in prompt
    assert "转人工" in prompt
