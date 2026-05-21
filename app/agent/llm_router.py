from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agent.handlers.utils import parse_json_object
from app.agent.llm_client import LLMClient
from app.shared.config import settings


ALLOWED_TOOLS = {
    "get_order_detail",
    "list_user_orders",
    "search_products",
    "get_product_detail",
    "search_after_sale_policy",
    "get_refund_status",
}

TOOL_ALIASES = {
    "get_order_details": "get_order_detail",
    "query_policy_kb": "search_after_sale_policy",
    "get_product_snapshot": "get_product_detail",
}


@dataclass
class RoutingDecision:
    route: str
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    answer: str = ""
    confidence: float = 0.0
    source: str = "llm"


class LLMRouter:
    def __init__(self, *, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    async def route(
        self,
        *,
        user_id: int,
        message: str,
        history: list[dict[str, str]],
    ) -> RoutingDecision:
        result = await self.llm_client.chat_messages(
            messages=[
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_prompt(message=message, history=history)},
            ]
        )
        payload = parse_json_object(result)
        decision = self._parse_payload(payload)
        decision.arguments = self._sanitize_arguments(
            user_id=user_id,
            route=decision.route,
            tool_name=decision.tool_name,
            arguments=decision.arguments,
            message=message,
        )
        return decision

    @staticmethod
    def _parse_payload(payload: dict[str, Any]) -> RoutingDecision:
        route = str(payload.get("route") or payload.get("intent") or "chitchat").strip()
        if route not in {"order_query", "product_inquiry", "policy_query", "refund_query", "chitchat"}:
            route = "chitchat"

        raw_tool = payload.get("tool_name") or payload.get("tool")
        tool_name = str(raw_tool).strip() if raw_tool else ""
        tool_name = TOOL_ALIASES.get(tool_name, tool_name)
        if not tool_name or tool_name == "none" or tool_name not in ALLOWED_TOOLS:
            tool_name = None

        raw_args = payload.get("arguments") or payload.get("tool_args") or {}
        arguments = raw_args if isinstance(raw_args, dict) else {}

        try:
            confidence = float(payload.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0

        return RoutingDecision(
            route=route,
            tool_name=tool_name,
            arguments=arguments,
            answer=str(payload.get("answer") or "").strip(),
            confidence=max(0.0, min(confidence, 1.0)),
        )

    @staticmethod
    def _sanitize_arguments(
        *,
        user_id: int,
        route: str,
        tool_name: str | None,
        arguments: dict[str, Any],
        message: str,
    ) -> dict[str, Any]:
        if tool_name is None:
            return {}

        if tool_name == "get_order_detail":
            order_id = str(arguments.get("order_id") or arguments.get("order_no") or "").strip()
            if not order_id:
                return {}
            return {"user_id": user_id, "user_role": "buyer", "order_id": order_id}

        if tool_name == "list_user_orders":
            return {"user_id": user_id, "user_role": "buyer", "limit": _bounded_int(arguments.get("limit"), 5, 1, 10)}

        if tool_name == "get_refund_status":
            refund_id = _optional_int(arguments.get("refund_id"))
            if refund_id is None:
                return {}
            return {"user_id": user_id, "user_role": "buyer", "refund_id": refund_id}

        if tool_name == "search_products":
            keyword = str(arguments.get("keyword") or arguments.get("query") or message).strip()
            return {"keyword": keyword, "limit": _bounded_int(arguments.get("limit"), 5, 1, 10)}

        if tool_name == "get_product_detail":
            product_id = _optional_int(arguments.get("product_id"))
            if product_id is None:
                return {}
            return {"product_id": product_id}

        if tool_name == "search_after_sale_policy":
            query = str(arguments.get("query") or message).strip()
            return {"query": query, "top_k": _bounded_int(arguments.get("top_k"), settings.support_retrieval_top_k, 1, 10)}

        return {}

    @staticmethod
    def _system_prompt() -> str:
        return """你是京选商城客服 Agent 的路由规划器。你只负责分析用户输入并选择是否调用工具，不直接编造业务事实。

必须只输出 JSON，不要输出 Markdown 或解释。格式：
{"route":"order_query|product_inquiry|policy_query|refund_query|chitchat","tool_name":"工具名或null","arguments":{},"answer":"","confidence":0.0}

可用工具：
- get_order_detail：查询一笔订单详情。arguments: {"order_id":"订单号"}
- list_user_orders：查询用户最近订单。arguments: {"limit":5}
- search_products：按关键词搜索商品。arguments: {"keyword":"关键词","limit":5}
- get_product_detail：查询商品详情。arguments: {"product_id":1}
- search_after_sale_policy：检索售后/发票/运费/平台规则。arguments: {"query":"问题","top_k":5}
- get_refund_status：查询退款单。arguments: {"refund_id":1}

规则：
1. 用户问订单、物流、发货、签收、支付状态：route=order_query。有明确订单号用 get_order_detail；问“我的订单/有哪些订单/最近订单”用 list_user_orders。
2. 用户问商品推荐、价格、库存、商品详情、商品对比：route=product_inquiry，优先 search_products，明确商品 ID 时用 get_product_detail。
3. 用户问退货、换货、发票、保修、运费、平台规则：route=policy_query，用 search_after_sale_policy。
4. 用户问退款单进度且有退款单号：route=refund_query，用 get_refund_status；没有退款单号但问退款政策时走 policy_query。
5. 闲聊或无法判断：route=chitchat，tool_name=null，可在 answer 给一句简短客服回复。
6. 不要输出 user_id/user_role，服务端会注入。
"""

    @staticmethod
    def _user_prompt(*, message: str, history: list[dict[str, str]]) -> str:
        recent = history[-6:]
        history_text = "\n".join(f"{item.get('role', '')}: {item.get('content', '')}" for item in recent) or "无"
        return f"历史对话：\n{history_text}\n\n用户最新输入：\n{message}"


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    parsed = _optional_int(value)
    if parsed is None:
        parsed = default
    return max(minimum, min(parsed, maximum))
