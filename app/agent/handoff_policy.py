from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


TRIGGER_LABELS = {
    "auto_processing_failed": "自动处理失败",
    "dispute": "争议处理",
    "timeout": "处理超时",
    "complaint": "投诉处理",
    "explicit_human_request": "用户要求人工",
}


@dataclass(frozen=True)
class HandoffDecision:
    trigger_type: str
    category: str
    priority: str
    reason: str


class SupportHandoffPolicy:
    ticket_query_keywords = ("工单进度", "我的工单", "工单状态", "人工工单")
    complaint_keywords = ("投诉", "举报", "差评", "态度差", "太差了", "垃圾", "生气", "气死")
    dispute_keywords = ("争议", "纠纷", "平台介入", "介入", "仲裁", "赔偿", "不同意", "不认可", "商家拒绝")
    timeout_keywords = ("超时", "太久", "一直没", "还没发货", "没发货", "没退款", "没处理", "无物流更新", "物流不更新")
    human_keywords = ("转人工", "人工客服", "真人客服", "人工处理", "不要机器人", "找人工", "人工")

    def is_ticket_query(self, message: str) -> bool:
        text = message.strip()
        return any(keyword in text for keyword in self.ticket_query_keywords)

    def classify_initial(self, *, message: str, entities: dict[str, Any] | None = None) -> HandoffDecision | None:
        text = message.strip()
        entities = entities or {}
        if any(keyword in text for keyword in self.complaint_keywords):
            return HandoffDecision("complaint", "complaint", "high", "用户表达投诉或强烈不满")
        if any(keyword in text for keyword in self.dispute_keywords):
            return HandoffDecision("dispute", "platform_rule", "high", "用户表达争议、赔偿、仲裁或平台介入诉求")
        if any(keyword in text for keyword in self.timeout_keywords):
            return HandoffDecision("timeout", self._timeout_category(text), "high", "用户表达订单、退款、支付或物流处理超时")
        if any(keyword in text for keyword in self.human_keywords):
            return HandoffDecision(
                "explicit_human_request",
                self._explicit_category(text, entities),
                "normal",
                "用户明确要求人工客服处理",
            )
        return None

    def classify_auto_failure(
        self,
        *,
        route: str,
        message: str,
        tool_calls: list[dict[str, Any]],
    ) -> HandoffDecision | None:
        if route in {"chitchat", "product_inquiry", "support_ticket"}:
            return None
        if not tool_calls:
            return None
        last = tool_calls[-1]
        if last.get("name") in {"create_support_ticket", "list_support_tickets"}:
            return None
        result = last.get("result") if isinstance(last, dict) else None
        if not self._needs_handoff(result, str(last.get("name") or "")):
            return None
        return HandoffDecision(
            "auto_processing_failed",
            self._route_category(route, message),
            "normal",
            "智能客服自动处理失败或工具结果不足，转人工继续处理",
        )

    def build_ticket_arguments(
        self,
        *,
        user_id: int,
        message: str,
        decision: HandoffDecision,
        order_id: str | None = None,
        product_id: int | None = None,
        refund_id: int | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        title = f"[{TRIGGER_LABELS.get(decision.trigger_type, '转人工')}] {message.strip()[:60] or '需要人工处理'}"
        arguments: dict[str, Any] = {
            "user_id": user_id,
            "user_role": "buyer",
            "title": title[:200],
            "content": message.strip() or "需要人工处理",
            "category": decision.category,
            "priority": decision.priority,
            "source": "agent",
            "trigger_reason": f"{decision.trigger_type}: {decision.reason}; user_message={message.strip()[:500]}",
        }
        if order_id:
            arguments["order_id"] = order_id
        if product_id is not None:
            arguments["product_id"] = product_id
        if refund_id is not None:
            arguments["refund_id"] = refund_id
        if trace_id:
            arguments["ai_trace_id"] = trace_id
        return arguments

    @staticmethod
    def _needs_handoff(result: Any, tool_name: str) -> bool:
        if not isinstance(result, dict):
            return False
        if result.get("success") is False:
            return True
        data = result.get("data")
        if isinstance(data, dict) and data.get("found") is False:
            return True
        if data in (None, "", [], {}) and tool_name not in {"list_user_orders", "search_products", "list_support_tickets"}:
            return True
        return False

    @staticmethod
    def _timeout_category(text: str) -> str:
        if any(keyword in text for keyword in ("退款", "退货", "售后")):
            return "refund_issue"
        if any(keyword in text for keyword in ("支付", "付款", "扣款")):
            return "payment_issue"
        return "logistics_issue"

    @staticmethod
    def _explicit_category(text: str, entities: dict[str, Any]) -> str:
        if "refund_id" in entities or any(keyword in text for keyword in ("退款", "退货", "售后")):
            return "refund_issue"
        if any(keyword in text for keyword in ("支付", "付款", "扣款")):
            return "payment_issue"
        if "order_id" in entities or any(keyword in text for keyword in ("订单", "物流", "发货", "快递")):
            return "logistics_issue"
        if "product_id" in entities or any(keyword in text for keyword in ("商品", "质量", "库存")):
            return "product_consultation"
        return "other"

    @staticmethod
    def _route_category(route: str, message: str) -> str:
        if route == "refund_query":
            return "refund_issue"
        if route == "payment_query":
            return "payment_issue"
        if route == "policy_query":
            return "platform_rule"
        if route == "order_query":
            return "logistics_issue"
        if re.search(r"退款|退货|售后", message):
            return "refund_issue"
        return "other"
