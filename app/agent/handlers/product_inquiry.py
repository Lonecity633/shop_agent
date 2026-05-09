from __future__ import annotations

from app.agent.handlers.base import HandlerContext, HandlerResult, IntentHandler
from app.agent.handlers.utils import history_to_text
from app.agent.prompts import FALLBACKS, PRODUCT_INQUIRY
from app.agent.tools.shop_tools import fetch_product_snapshot, search_products_by_keyword


class ProductInquiryHandler(IntentHandler):
    async def handle(self, ctx: HandlerContext) -> HandlerResult:
        product_lines: list[str] = []

        if ctx.product_id is not None:
            product = await fetch_product_snapshot(ctx.db, ctx.product_id)
            if product is not None:
                product_lines.append(
                    f"- 商品ID:{product['product_id']} 名称:{product['name']} 价格:¥{product['price']:.2f} 库存:{product['stock']}"
                )

        if not product_lines:
            candidates = await search_products_by_keyword(ctx.db, ctx.content, limit=5)
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
        return HandlerResult(answer=answer)
