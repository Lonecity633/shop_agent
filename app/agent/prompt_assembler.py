from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.shared.config import settings


@dataclass(frozen=True)
class PromptLayer:
    name: str
    content: str


@dataclass
class PromptAssembler:
    """Build layered support prompts without scattering policy text."""

    brand_identity: str = "你是京选商城的智能客服 Agent。"
    business_boundary: str = (
        "所有订单、物流、退款、支付、商品、库存、工单和平台规则事实必须来自工具结果或历史上下文；"
        "没有工具事实时要说明无法确认，不要编造。"
    )
    response_style: str = "用自然、简洁、礼貌的中文客服口吻回答，不输出内部工具名、trace、raw schema 或调试信息。"
    risk_boundary: str = "涉及投诉、支付异常、退款争议、政策不确定、工具失败或用户要求人工时，应建议转人工或创建工单。"
    extra_layers: list[PromptLayer] = field(default_factory=list)

    def route_system_prompt(self, *, tools_section: str) -> str:
        layers = self._base_layers()
        layers.extend(
            [
                PromptLayer("当前任务", "分析用户输入并选择是否调用一个可用工具；只输出 JSON，不要输出 Markdown 或解释。"),
                PromptLayer("输出格式", self._route_schema()),
                PromptLayer("可用工具", tools_section),
                PromptLayer("路由规则", self._route_rules()),
            ]
        )
        return self._render(layers)

    def response_system_prompt(self) -> str:
        layers = self._base_layers()
        layers.extend(
            [
                PromptLayer("当前任务", "根据用户问题、历史对话、工具结果和工具调用摘要生成最终客服回复。"),
                PromptLayer("回复规范", self.response_style),
                PromptLayer(
                    "结果边界",
                    "工具结果失败、为空或没有查到时，礼貌说明无法确认，并建议用户核对信息或转人工；候选商品或订单最多列 5 项。",
                ),
            ]
        )
        return self._render(layers)

    def memory_summary_prompt(
        self,
        *,
        previous_summary: str,
        messages_text: str,
        entity_text: str,
    ) -> str:
        layers = self._base_layers()
        layers.extend(
            [
                PromptLayer("当前任务", "为京选商城智能客服压缩会话短期记忆。"),
                PromptLayer(
                    "压缩规则",
                    (
                        "只总结用户诉求、已确认上下文、待处理事项和必要追问线索；"
                        "不要编造订单、物流、退款、商品、库存或政策事实；"
                        "保留订单号、商品 ID、退款单号、支付流水号等关键实体；"
                        f"控制在 {settings.support_memory_summary_max_chars} 字以内。"
                    ),
                ),
                PromptLayer("上一版摘要", previous_summary or "无"),
                PromptLayer("关键实体", entity_text or "无"),
                PromptLayer("本次需要压缩的较早对话", messages_text or "无"),
            ]
        )
        return self._render(layers)

    @staticmethod
    def route_user_prompt(*, message: str, history: list[dict[str, str]]) -> str:
        history_text = "\n".join(f"{item.get('role', '')}: {item.get('content', '')}" for item in history) or "无"
        return f"历史对话：\n{history_text}\n\n用户最新输入：\n{message}"

    @staticmethod
    def response_user_prompt(
        *,
        route: str,
        message: str,
        tool_result: dict[str, Any] | None,
        history: list[dict[str, str]],
        tool_calls: list[dict[str, Any]],
    ) -> str:
        history_text = "\n".join(f"{item.get('role', '')}: {item.get('content', '')}" for item in history) or "无"
        payload = {
            "route": route,
            "user_message": message,
            "recent_history": history_text,
            "tool_result": tool_result,
            "tool_calls_summary": [
                {
                    "name": item.get("name"),
                    "arguments": item.get("arguments"),
                    "step": item.get("step"),
                    "routing_source": item.get("routing_source"),
                    "error_type": item.get("error_type"),
                }
                for item in tool_calls[-3:]
                if isinstance(item, dict)
            ],
        }
        return "请根据以下上下文生成最终客服回复：\n" + _compact_json(payload)

    def _base_layers(self) -> list[PromptLayer]:
        return [
            PromptLayer("身份", self.brand_identity),
            PromptLayer("业务事实边界", self.business_boundary),
            PromptLayer("风险边界", self.risk_boundary),
            *self.extra_layers,
        ]

    @staticmethod
    def _route_schema() -> str:
        return (
            '{"route":"order_query|product_inquiry|policy_query|refund_query|payment_query|support_ticket|chitchat",'
            '"tool_name":"工具名或null","arguments":{},"answer":"","confidence":0.0}'
        )

    @staticmethod
    def _route_rules() -> str:
        return """1. 用户问订单、物流、发货、签收：route=order_query。有明确订单号用 get_order_detail；问最近订单用 list_user_orders。
2. 用户问商品推荐、价格、库存、商品详情、商品对比：route=product_inquiry，优先 search_products，明确商品 ID 时用 get_product_detail。
3. 用户问退货、换货、发票、保修、运费、平台规则：route=policy_query，用 search_after_sale_policy。
4. 用户问退款单进度且有退款单号：route=refund_query，用 get_refund_status；没有退款单号但问退款政策时走 policy_query。
5. 用户问支付状态、支付失败、付款流水：route=payment_query，用 get_payment_status。
6. 用户要求人工、投诉、争议升级，或工具多次失败无法处理：route=support_ticket，用 create_support_ticket。
7. 用户问已有工单进度：route=support_ticket，用 list_support_tickets。
8. 闲聊或无法判断：route=chitchat，tool_name=null，可在 answer 给一句简短客服回复。
9. 不要输出 user_id/user_role，服务端会注入。"""

    @staticmethod
    def _render(layers: list[PromptLayer]) -> str:
        return "\n\n".join(f"## {layer.name}\n{layer.content.strip()}" for layer in layers if layer.content.strip())


def _compact_json(value: Any) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        return "{}"
    return text[:6000]
