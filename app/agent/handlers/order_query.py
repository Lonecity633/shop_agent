from __future__ import annotations

from app.agent.handlers.base import HandlerContext, HandlerResult, IntentHandler
from app.agent.response_generator import ResponseGenerator


class OrderQueryHandler(IntentHandler):
    async def handle(self, ctx: HandlerContext) -> HandlerResult:
        if not ctx.order_id:
            return HandlerResult(answer="请提供订单号，我来帮你查询订单进度。")
        result = await ctx.mcp_client.call_tool(
            "get_order_detail",
            {"user_id": ctx.user_id, "user_role": ctx.user_role, "order_id": ctx.order_id},
        )
        return HandlerResult(
            answer=ResponseGenerator().generate(route="order_query", message=ctx.content, tool_result=result),
            evidences=[{"tool": "get_order_detail", "result": result}],
        )

