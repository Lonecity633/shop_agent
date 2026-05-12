from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.handlers.base import HandlerContext, HandlerResult, IntentHandler
from app.agent.handlers.utils import history_to_text
from app.agent.mcp_client import McpToolClient
from app.agent.prompts import FALLBACKS, POLICY
from app.agent.retrieval import retrieve
from app.core.config import settings
from app.models.order import Order
from app.models.product import Product


class PolicyHandler(IntentHandler):
    def __init__(self):
        self.mcp_client = McpToolClient()

    async def handle(self, ctx: HandlerContext) -> HandlerResult:
        seller_id = await self._resolve_seller_id(ctx.db, order_id=ctx.order_id, product_id=ctx.product_id)

        chunks, tool_source = await self._query_policy_kb(ctx)
        evidences = [
            {
                "tool": "query_policy_kb",
                "source": tool_source,
                "chunk_id": c["chunk_id"],
                "document_title": c["document_title"],
                "score": c["score"],
            }
            for c in chunks
        ]

        if chunks:
            rag_context = "\n".join(f"- {c['content']}" for c in chunks)
        else:
            rag_context = "未检索到相关政策文档。"

        user_prompt = (
            f"历史对话：\n{history_to_text(ctx.history)}\n\n"
            f"用户问题：{ctx.content}\n\n"
            f"政策文档检索结果：\n{rag_context}"
        )
        messages = [
            {"role": "system", "content": POLICY},
            {"role": "user", "content": user_prompt},
        ]
        try:
            answer = await ctx.llm_client.chat_messages(messages=messages)
        except TimeoutError:
            answer = FALLBACKS["policy_timeout"]
        except Exception:
            answer = FALLBACKS["policy_no_input"]
        return HandlerResult(answer=answer, resolved_seller_id=seller_id, evidences=evidences)

    async def _query_policy_kb(self, ctx: HandlerContext) -> tuple[list[dict], str]:
        try:
            result = await self.mcp_client.call_tool(
                ctx.db,
                current_user=ctx.current_user,
                session_id=ctx.session_id,
                tool_name="query_policy_kb",
                arguments={"question": ctx.content, "top_k": settings.support_retrieval_top_k},
            )
            chunks = result.get("data") or []
            return (chunks if isinstance(chunks, list) else []), "mcp"
        except Exception:
            if not settings.mcp_fallback_enabled:
                return [], "mcp_failed"
            return await retrieve(ctx.db, ctx.content, top_k=settings.support_retrieval_top_k), "local_fallback"

    @staticmethod
    async def _resolve_seller_id(db: AsyncSession, *, order_id: int | None, product_id: int | None) -> int | None:
        if order_id is not None:
            result = await db.execute(
                select(Product.seller_id).join(Order, Order.product_id == Product.id).where(Order.id == order_id)
            )
            value = result.scalar_one_or_none()
            if value is not None:
                return value
        if product_id is not None:
            result = await db.execute(select(Product.seller_id).where(Product.id == product_id))
            return result.scalar_one_or_none()
        return None
