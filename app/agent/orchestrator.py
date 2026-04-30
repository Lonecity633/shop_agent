from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.shop_tools import (
    GET_ORDER_DETAILS_TOOL,
    execute_get_order_details,
    fetch_product_snapshot,
    search_products_by_keyword,
)
from app.agent.llm_client import LLMClient
from app.models.order import Order
from app.models.product import Product
from app.models.support import SupportMessage, SupportSession
from app.models.user import User, UserRole

SENSITIVE_PATTERNS = [r"密码", r"银行卡", r"cvv", r"身份证"]
INTENT_LABELS = {"order_query", "policy_query", "product_inquiry", "chitchat"}
CHITCHAT_SYSTEM_PROMPT = """你是一个名为“京选商城”的官方智能客服助手。
【严格约束】：
语气必须专业、友好、简练，绝不能使用“亲”这种过度口语化的称呼。
每次回复请控制在 50 字以内，言简意赅。
绝对不能向用户做出任何关于发货时间、退款金额的虚假承诺。
当前处于闲聊或前置沟通模式，如果用户意图不明确，请引导用户提供订单号或商品信息。"""
INTENT_CLASSIFIER_PROMPT = """你是电商客服意图分类器。
请将用户请求严格分类为以下之一：
- order_query：订单进度、物流、签收、退款进度等订单相关问题
- policy_query：平台/商家规则、发票、运费、售后条款等政策规则问题
- product_inquiry：商品价格、库存、规格、推荐、商品对比等商品咨询
- chitchat：闲聊、上下文追问、意图不明或无法归入以上类别的问题

必须只输出 JSON，不要输出其他文本。格式：
{"intent":"order_query|policy_query|product_inquiry|chitchat","confidence":0.0,"reason":"..."}"""
PRODUCT_INQUIRY_SYSTEM_PROMPT = """你是“京选商城”官方智能客服助手，正在处理商品咨询。
请严格依据给定商品信息回答，不要编造不存在的商品、库存或价格。
如果商品信息不足，明确告知并引导用户补充商品名或商品ID。"""
POLICY_SYSTEM_PROMPT = """你是“京选商城”官方智能客服助手，正在处理平台或商家规则咨询。
请保持专业、友好、简练，不要编造未确认的具体规则条款。
如果信息不足，请明确告知并引导用户补充订单号、商家信息或具体规则点。"""
ORDER_QUERY_SYSTEM_PROMPT = """你是“京选商城”官方智能客服助手，正在处理订单查询问题。
你的职责：
1) 仅当你能从当前输入或最近对话中明确提取出订单号时，调用 get_order_details 工具；
2) 如果无法确定订单号，不要调用工具，直接自然追问用户提供订单号；
3) 拿到工具结果后，生成简洁、准确、自然的最终答复，不要暴露内部工具调用细节。"""


@dataclass
class AgentReplyResult:
    answer: str
    route: str
    resolved_seller_id: int | None
    evidences: list[dict]


class SupportAgentOrchestrator:
    def __init__(self):
        self.llm_client = LLMClient()

    async def reply(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        session_id: int,
        content: str,
        order_id: int | None,
        product_id: int | None,
    ) -> AgentReplyResult:
        session = await self._get_session(db, session_id)
        self._ensure_session_access(current_user, session)

        blocked_answer = self._guardrail_answer(content)
        evidences: list[dict] = []
        resolved_seller_id: int | None = None
        route = "chitchat"
        answer = ""
        tool_records: list[str] = []

        if blocked_answer is not None:
            route = "guardrail_blocked"
            answer = blocked_answer
        else:
            history = await self._get_recent_history(db, session_id=session_id)
            route = await self._classify_intent(content=content, history=history)

            if route == "order_query":
                answer, tool_records, evidences = await self._compose_order_query_answer(
                    db,
                    current_user=current_user,
                    content=content,
                    history=history,
                )
            elif route == "policy_query":
                resolved_seller_id = await self._resolve_seller_id(db, order_id=order_id, product_id=product_id)
                answer = await self._compose_policy_answer(content=content, history=history)
            elif route == "product_inquiry":
                answer = await self._compose_product_inquiry_answer(
                    db,
                    content=content,
                    history=history,
                    product_id=product_id,
                )
            else:
                route = "chitchat"
                answer = await self._compose_chitchat_answer(content=content, history=history)

        user_msg = SupportMessage(session_id=session_id, role="user", content=content, retrieval_query=content)
        db.add(user_msg)
        for item in tool_records:
            db.add(SupportMessage(session_id=session_id, role="tool", content=item, retrieval_query=""))
        assistant_msg = SupportMessage(session_id=session_id, role="assistant", content=answer, retrieval_query=content)
        db.add(assistant_msg)

        await db.commit()
        return AgentReplyResult(answer=answer, route=route, resolved_seller_id=resolved_seller_id, evidences=evidences)

    async def _resolve_seller_id(self, db: AsyncSession, *, order_id: int | None, product_id: int | None) -> int | None:
        if order_id is not None:
            result = await db.execute(select(Product.seller_id).join(Order, Order.product_id == Product.id).where(Order.id == order_id))
            value = result.scalar_one_or_none()
            if value is not None:
                return value
        if product_id is not None:
            result = await db.execute(select(Product.seller_id).where(Product.id == product_id))
            return result.scalar_one_or_none()
        return None

    @staticmethod
    def _guardrail_answer(content: str) -> str | None:
        text = content.lower()
        if any(re.search(pattern, text) for pattern in SENSITIVE_PATTERNS):
            return "该问题涉及敏感信息，请通过安全渠道处理，当前客服无法直接提供此类信息。"
        return None

    async def _classify_intent(self, *, content: str, history: list[dict]) -> str:
        user_prompt = (
            f"历史对话（最近5轮）：\n{self._history_to_text(history)}\n\n"
            f"用户当前输入：{content}\n\n"
            "请输出 JSON。"
        )
        messages = [
            {"role": "system", "content": INTENT_CLASSIFIER_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        try:
            raw = await self.llm_client.chat_messages(messages=messages)
        except Exception:
            return "chitchat"

        intent = self._parse_intent_output(raw)
        return intent if intent in INTENT_LABELS else "chitchat"

    async def _compose_order_query_answer(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        content: str,
        history: list[dict],
    ) -> tuple[str, list[str], list[dict]]:
        messages = self._build_order_query_messages(history=history, content=content)
        try:
            first_pass = await self.llm_client.chat_completion(
                messages=messages,
                tools=[GET_ORDER_DETAILS_TOOL],
                tool_choice="auto",
            )
        except TimeoutError:
            return "订单查询请求较多，请稍后再试。", [], []
        except Exception:
            return "请提供订单号，我来帮你查询订单进度。", [], []

        if not first_pass.tool_calls:
            if first_pass.content:
                return first_pass.content, [], []
            return "请提供订单号，我来帮你查询订单进度。", [], []

        tool_call = next((item for item in first_pass.tool_calls if item.name == "get_order_details"), first_pass.tool_calls[0])
        args = self._parse_json_object(tool_call.arguments)
        raw_order_id = args.get("order_id")
        order_id = str(raw_order_id).strip() if raw_order_id is not None else ""

        tool_result = await execute_get_order_details(db, current_user=current_user, order_id=order_id)
        tool_payload = json.dumps(tool_result, ensure_ascii=False)
        evidences = [
            {
                "tool": "get_order_details",
                "args": {"order_id": order_id},
                "result": tool_result,
            }
        ]

        assistant_tool_message: dict[str, Any] = {
            "role": "assistant",
            "content": first_pass.content or "",
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": "get_order_details",
                        "arguments": tool_call.arguments,
                    },
                }
            ],
        }
        second_pass_messages = [
            *messages,
            assistant_tool_message,
            {"role": "tool", "tool_call_id": tool_call.id, "content": tool_payload},
        ]
        try:
            second_pass = await self.llm_client.chat_completion(
                messages=second_pass_messages,
                tools=[GET_ORDER_DETAILS_TOOL],
                tool_choice="none",
            )
            if second_pass.content:
                return second_pass.content, [tool_payload], evidences
        except TimeoutError:
            pass
        except Exception:
            pass

        fallback = self._fallback_order_answer_from_tool(tool_result)
        return fallback, [tool_payload], evidences

    @staticmethod
    def _parse_intent_output(raw: str) -> str | None:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                return None
            try:
                payload = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        if not isinstance(payload, dict):
            return None
        intent = str(payload.get("intent", "")).strip()
        return intent or None

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any]:
        text = raw.strip()
        if not text:
            return {}
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
        try:
            payload = json.loads(text)
            return payload if isinstance(payload, dict) else {}
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                return {}
            try:
                payload = json.loads(match.group(0))
                return payload if isinstance(payload, dict) else {}
            except json.JSONDecodeError:
                return {}

    async def _compose_product_inquiry_answer(
        self,
        db: AsyncSession,
        *,
        content: str,
        history: list[dict],
        product_id: int | None,
    ) -> str:
        product_lines: list[str] = []

        if product_id is not None:
            product = await fetch_product_snapshot(db, product_id)
            if product is not None:
                product_lines.append(
                    f"- 商品ID:{product['product_id']} 名称:{product['name']} 价格:¥{product['price']:.2f} 库存:{product['stock']}"
                )

        if not product_lines:
            candidates = await search_products_by_keyword(db, content, limit=5)
            for item in candidates:
                product_lines.append(
                    f"- 商品ID:{item['product_id']} 名称:{item['name']} 价格:¥{item['price']:.2f} 库存:{item['stock']}"
                )

        tool_context = "\n".join(product_lines) if product_lines else "未检索到匹配商品。"
        user_prompt = (
            f"历史对话：\n{self._history_to_text(history)}\n\n"
            f"用户问题：{content}\n\n"
            f"商品工具结果：\n{tool_context}"
        )
        messages = [
            {"role": "system", "content": PRODUCT_INQUIRY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        try:
            return await self.llm_client.chat_messages(messages=messages)
        except TimeoutError:
            return "商品咨询请求较多，请稍后再试，或补充更具体的商品信息。"
        except Exception:
            return "请补充商品名称或商品ID，我来帮你查询价格和库存。"

    async def _compose_policy_answer(self, *, content: str, history: list[dict]) -> str:
        user_prompt = (
            f"历史对话：\n{self._history_to_text(history)}\n\n"
            f"用户问题：{content}"
        )
        messages = [
            {"role": "system", "content": POLICY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        try:
            return await self.llm_client.chat_messages(messages=messages)
        except TimeoutError:
            return "规则咨询请求较多，请稍后再试，或补充更具体的问题。"
        except Exception:
            return "请补充你关心的具体规则点，我来继续协助你。"

    async def _compose_chitchat_answer(self, *, content: str, history: list[dict]) -> str:
        messages = self._build_chitchat_messages(history=history, content=content)
        try:
            return await self.llm_client.chat_messages(messages=messages)
        except TimeoutError:
            return "当前咨询较多，请稍后再试，或提供订单号/商品信息。"
        except Exception:
            return "你好，请提供订单号或商品信息，我来继续协助你。"

    @staticmethod
    async def _get_recent_history(db: AsyncSession, *, session_id: int, limit: int = 10) -> list[dict]:
        stmt = (
            select(SupportMessage)
            .where(SupportMessage.session_id == session_id)
            .order_by(SupportMessage.created_at.desc(), SupportMessage.id.desc())
            .limit(limit)
        )
        rows = list((await db.execute(stmt)).scalars().all())
        rows.reverse()
        allowed_roles = {"system", "user", "assistant"}
        return [{"role": item.role, "content": item.content} for item in rows if item.role in allowed_roles]

    @staticmethod
    def _build_chitchat_messages(*, history: list[dict], content: str) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": CHITCHAT_SYSTEM_PROMPT}]
        for item in history:
            role = item.get("role", "").strip()
            text = item.get("content", "").strip()
            if role in {"system", "user", "assistant"} and text:
                messages.append({"role": role, "content": text})
        messages.append({"role": "user", "content": content.strip()})
        return messages

    @staticmethod
    def _build_order_query_messages(*, history: list[dict], content: str) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": ORDER_QUERY_SYSTEM_PROMPT}]
        for item in history:
            role = item.get("role", "").strip()
            text = item.get("content", "").strip()
            if role in {"user", "assistant"} and text:
                messages.append({"role": role, "content": text})
        messages.append({"role": "user", "content": content.strip()})
        return messages

    @staticmethod
    def _history_to_text(history: list[dict]) -> str:
        if not history:
            return "（无）"
        lines = [f"{item.get('role', 'user')}: {item.get('content', '').strip()}" for item in history]
        return "\n".join(lines)

    @staticmethod
    def _fallback_order_answer_from_tool(tool_result: dict[str, Any]) -> str:
        if tool_result.get("found"):
            return (
                f"订单 {tool_result.get('order_id')} 当前状态 {tool_result.get('order_status')}，"
                f"物流单号 {tool_result.get('tracking_no')}（{tool_result.get('logistics_company')}）。"
            )
        if tool_result.get("error_code") == "INVALID_ARGUMENTS":
            return "请问您的订单号是多少？"
        return "未查到该订单信息，请核对订单号后重试。"

    @staticmethod
    async def _get_session(db: AsyncSession, session_id: int) -> SupportSession:
        result = await db.execute(select(SupportSession).where(SupportSession.id == session_id))
        session = result.scalar_one_or_none()
        if session is None:
            raise ValueError("会话不存在")
        return session

    @staticmethod
    def _ensure_session_access(current_user: User, session: SupportSession) -> None:
        if current_user.role == UserRole.admin:
            return
        if current_user.role == UserRole.buyer and session.user_id == current_user.id:
            return
        raise PermissionError("当前用户无权访问该会话")
