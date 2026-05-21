from __future__ import annotations

from app.agent.handlers.base import HandlerContext, HandlerResult, IntentHandler
from app.agent.response_generator import ResponseGenerator


class ProductInquiryHandler(IntentHandler):
    async def handle(self, ctx: HandlerContext) -> HandlerResult:
        if ctx.product_id is not None:
            result = await ctx.mcp_client.call_tool("get_product_detail", {"product_id": ctx.product_id})
            tool = "get_product_detail"
        else:
            result = await ctx.mcp_client.call_tool("search_products", {"keyword": ctx.content, "limit": 5})
            tool = "search_products"
        return HandlerResult(
            answer=ResponseGenerator().generate(route="product_inquiry", message=ctx.content, tool_result=result),
            evidences=[{"tool": tool, "result": result}],
        )

