from __future__ import annotations

import json
import re
from typing import Any

from app.agent.prompts import FALLBACKS


def history_to_text(history: list[dict]) -> str:
    if not history:
        return "（无）"
    lines = [f"{item.get('role', 'user')}: {item.get('content', '').strip()}" for item in history]
    return "\n".join(lines)


def build_messages(
    system_prompt: str,
    history: list[dict],
    content: str,
    *,
    allowed_roles: set[str] | None = None,
) -> list[dict[str, str]]:
    if allowed_roles is None:
        allowed_roles = {"system", "user", "assistant"}
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for item in history:
        role = item.get("role", "").strip()
        text = item.get("content", "").strip()
        if role in allowed_roles and text:
            messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": content.strip()})
    return messages


def parse_json_object(raw: str) -> dict[str, Any]:
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


def parse_intent_output(raw: str) -> str | None:
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


def fallback_order_answer(tool_result: dict[str, Any]) -> str:
    if tool_result.get("found"):
        latest_payment = tool_result.get("latest_payment") or {}
        refunds = tool_result.get("refunds") or []
        payment_text = ""
        if latest_payment:
            payment_text = f"，最近支付流水状态 {latest_payment.get('status')}"
            if latest_payment.get("failure_reason"):
                payment_text += f"，失败原因：{latest_payment.get('failure_reason')}"
        refund_text = ""
        if refunds:
            refund_text = f"，最近退款状态 {refunds[0].get('status')}"
        return FALLBACKS["order_fallback_template"].format(
            order_id=tool_result.get("order_id"),
            order_status=tool_result.get("order_status"),
            pay_status=tool_result.get("pay_status"),
            payment_text=payment_text,
            refund_text=refund_text,
            tracking_no=tool_result.get("tracking_no"),
            logistics_company=tool_result.get("logistics_company"),
        )
    if tool_result.get("error_code") == "INVALID_ARGUMENTS":
        return FALLBACKS["order_fallback_no_args"]
    return FALLBACKS["order_fallback_not_found"]
