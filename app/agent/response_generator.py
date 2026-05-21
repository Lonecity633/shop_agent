from __future__ import annotations

from typing import Any


class ResponseGenerator:
    def generate(self, *, route: str, message: str, tool_result: dict[str, Any] | None) -> str:
        if tool_result is not None and tool_result.get("success") is False:
            return "查询服务暂时不可用，请稍后再试，或转人工客服继续处理。"
        data = (tool_result or {}).get("data")
        if route == "order_query":
            return self._order_answer(data)
        if route == "product_inquiry":
            return self._product_answer(data)
        if route == "policy_query":
            return self._policy_answer(data)
        if route == "refund_query":
            return self._refund_answer(data)
        return "我可以帮你查询订单、商品、退款和售后政策。请把订单号、商品关键词或问题发给我。"

    @staticmethod
    def _order_answer(data: Any) -> str:
        if isinstance(data, list):
            if not data:
                return "暂时没有查到你的订单记录。"
            lines = []
            for item in data[:5]:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    f"{item.get('order_id')}（订单状态：{item.get('status', '未知')}，支付状态：{item.get('pay_status', '未知')}）"
                )
            if lines:
                return "我查到你最近的订单：" + "；".join(lines) + "。"
            return "暂时没有查到你的订单记录。"
        if not isinstance(data, dict) or not data.get("found", True):
            return "暂时没有查到这笔订单，请确认订单号是否正确。"
        product = data.get("product") or {}
        status = data.get("status") or "未知"
        pay_status = data.get("pay_status") or "未知"
        logistics = data.get("logistics_company") or "暂无物流公司"
        tracking = data.get("tracking_no") or "暂无运单号"
        return (
            f"订单 {data.get('order_id')} 当前状态是 {status}，支付状态是 {pay_status}。"
            f"商品：{product.get('name', '未知商品')}。物流：{logistics}，运单号：{tracking}。"
        )

    @staticmethod
    def _product_answer(data: Any) -> str:
        items = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        if not items:
            return "暂时没有找到匹配商品，可以换个关键词再问我。"
        lines = []
        for item in items[:3]:
            lines.append(f"{item.get('name')}，价格 {item.get('price')}，库存 {item.get('stock')}")
        return "我找到了这些商品：" + "；".join(lines) + "。"

    @staticmethod
    def _policy_answer(data: Any) -> str:
        chunks = data if isinstance(data, list) else []
        if not chunks:
            return "暂时没有检索到相关售后政策，我建议联系人工客服进一步确认。"
        summary = "；".join(str(item.get("content", ""))[:120] for item in chunks[:2] if isinstance(item, dict))
        return f"根据平台售后政策：{summary}"

    @staticmethod
    def _refund_answer(data: Any) -> str:
        if not isinstance(data, dict):
            return "暂时没有查到这条退款记录，请确认退款单号是否正确。"
        return f"退款单 {data.get('refund_id')} 当前状态是 {data.get('status')}，金额 {data.get('amount')}。"
