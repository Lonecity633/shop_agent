from __future__ import annotations

from app.agent.handlers.base import HandlerContext, HandlerResult
from app.agent.response_generator import ResponseGenerator
from app.shared.config import settings


class ReactSupportAgent:
    async def handle(self, ctx: HandlerContext) -> HandlerResult:
        result = await ctx.mcp_client.call_tool(
            "search_after_sale_policy",
            {"query": ctx.content, "top_k": settings.support_retrieval_top_k},
        )
        return HandlerResult(
            answer=ResponseGenerator().generate(route="policy_query", message=ctx.content, tool_result=result),
            evidences=[{"tool": "search_after_sale_policy", "result": result}],
        )

