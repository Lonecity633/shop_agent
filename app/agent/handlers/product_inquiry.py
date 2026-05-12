from __future__ import annotations

from app.agent.handlers.base import HandlerContext, HandlerResult, IntentHandler
from app.agent.handlers.utils import history_to_text
from app.agent.mcp_client import McpToolClient
from app.agent.prompts import FALLBACKS, PRODUCT_INQUIRY
from app.agent.tools.shop_tools import fetch_product_snapshot, search_products_by_keyword
from app.core.config import settings


class ProductInquiryHandler(IntentHandler):
    def __init__(self):
        self.mcp_client = McpToolClient()

    async def handle(self, ctx: HandlerContext) -> HandlerResult:
        product_lines: list[str] = []
        evidences: list[dict] = []

        if ctx.product_id is not None:
            product = await self._get_product_snapshot(ctx, ctx.product_id, evidences)
            if product is not None:
                product_lines.append(
                    f"- 商品ID:{product['product_id']} 名称:{product['name']} 价格:¥{product['price']:.2f} 库存:{product['stock']}"
                )

        if not product_lines:
            candidates = await self._search_products(ctx, ctx.content, evidences)
            for item in candidates:
                product_lines.append(
                    f"- 商品ID:{item['product_id']} 名称:{item['name']} 价格:¥{item['price']:.2f} 库存:{item['stock']}"
                )

        tool_context = "\n".join(product_lines) if product_lines else "未检索到匹配商品。"
        user_prompt = (
            f"历史对话：\n{history_to_text(ctx.history)}\n\n"
            f"用户问题：{ctx.content}\n\n"
            f"商品工具结果：\n{tool_context}"
        )
        messages = [
            {"role": "system", "content": PRODUCT_INQUIRY},
            {"role": "user", "content": user_prompt},
        ]
        try:
            answer = await ctx.llm_client.chat_messages(messages=messages)
        except TimeoutError:
            answer = FALLBACKS["product_timeout"]
        except Exception:
            answer = FALLBACKS["product_no_input"]
        return HandlerResult(answer=answer, evidences=evidences)

    async def _get_product_snapshot(self, ctx: HandlerContext, product_id: int, evidences: list[dict]) -> dict | None:
        try:
            result = await self.mcp_client.call_tool(
                ctx.db,
                current_user=ctx.current_user,
                session_id=ctx.session_id,
                tool_name="get_product_snapshot",
                arguments={"product_id": product_id},
            )
            product = result.get("data")
            evidences.append({"tool": "get_product_snapshot", "source": "mcp", "product_id": product_id})
            return product if isinstance(product, dict) else None
        except Exception:
            if not settings.mcp_fallback_enabled:
                return None
            product = await fetch_product_snapshot(ctx.db, product_id)
            evidences.append({"tool": "get_product_snapshot", "source": "local_fallback", "product_id": product_id})
            return product

    async def _search_products(self, ctx: HandlerContext, keyword: str, evidences: list[dict]) -> list[dict]:
        try:
            result = await self.mcp_client.call_tool(
                ctx.db,
                current_user=ctx.current_user,
                session_id=ctx.session_id,
                tool_name="search_products",
                arguments={"keyword": keyword, "limit": 5},
            )
            candidates = result.get("data") or []
            evidences.append({"tool": "search_products", "source": "mcp", "count": len(candidates)})
            return candidates if isinstance(candidates, list) else []
        except Exception:
            if not settings.mcp_fallback_enabled:
                return []
            candidates = await search_products_by_keyword(ctx.db, keyword, limit=5)
            evidences.append({"tool": "search_products", "source": "local_fallback", "count": len(candidates)})
            return candidates
