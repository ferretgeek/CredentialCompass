from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

_AUTH_RULES = (
    ("revoked", ("invalidated", "revoked", "token_invalidated"), "登录态失效", "Sign-in revoked"),
    ("expired", ("expired", "token_expired", "session expired"), "认证已过期", "Authentication expired"),
    ("malformed", ("malformed", "could not parse", "invalid bearer"), "凭证格式异常", "Malformed credential"),
    (
        "verification",
        ("verification required", "mfa required", "security check"),
        "需要额外验证",
        "Verification required",
    ),
)


def _mapping(body: Any) -> dict[str, Any]:
    if isinstance(body, dict):
        return body
    if isinstance(body, str) and len(body) <= 262_144:
        try:
            parsed = json.loads(body)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _text(body: Any) -> str:
    if isinstance(body, str):
        return body[:262_144].lower()
    try:
        return json.dumps(body, ensure_ascii=False, separators=(",", ":"))[:262_144].lower()
    except (TypeError, ValueError):
        return ""


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _reset_value(mapping: dict[str, Any]) -> str:
    raw = next(
        (mapping[key] for key in ("reset_at", "resets_at", "resetAt", "resetsAt") if mapping.get(key)),
        None,
    )
    if raw is None:
        return ""
    if isinstance(raw, (int, float)):
        number = float(raw)
        if number > 1_000_000_000_000:
            number /= 1000
        try:
            return datetime.fromtimestamp(number, timezone.utc).isoformat().replace("+00:00", "Z")
        except (OverflowError, OSError, ValueError):
            return ""
    text = str(raw).strip()
    return text[:40] if len(text) <= 40 else ""


def quota_summary(body: Any) -> dict[str, Any]:
    data = _mapping(body)
    rate = data.get("rate_limit")
    if not isinstance(rate, dict):
        return {"state": "unknown", "plan": "", "used_percent": None, "resets_at": ""}
    plan_raw = str(data.get("plan_type") or "").strip().lower()
    plan = next((item for item in ("free", "plus", "pro", "team") if item in plan_raw), "")
    allowed = rate.get("allowed")
    limited = rate.get("limit_reached")
    if limited is True or allowed is False:
        state = "limited"
    elif limited is False and allowed is True:
        state = "available"
    else:
        state = "unknown"
    window = rate.get("primary_window")
    if not isinstance(window, dict):
        window = rate
    used = _number(window.get("used_percent") if isinstance(window, dict) else None)
    if used is None and isinstance(window, dict):
        current = _number(window.get("used"))
        limit = _number(window.get("limit"))
        if current is not None and limit and limit > 0:
            used = current / limit * 100
    if used is not None:
        used = round(max(0.0, min(100.0, used)), 1)
    return {
        "state": state,
        "plan": plan,
        "used_percent": used,
        "resets_at": _reset_value(window if isinstance(window, dict) else rate),
    }


def classify(status_code: int, body: Any) -> dict[str, Any]:
    if status_code == 200:
        quota = quota_summary(body)
        if quota["state"] == "limited":
            return {"key": "quota_limited", "label": "额度已满", "tone": "warn", "quota": quota}
        return {"key": "healthy", "label": "状态正常", "tone": "good", "quota": quota}
    if status_code == 401:
        haystack = _text(body)
        for key, needles, zh_label, en_label in _AUTH_RULES:
            if any(needle in haystack for needle in needles):
                return {
                    "key": key,
                    "label": zh_label,
                    "label_en": en_label,
                    "tone": "bad",
                    "quota": quota_summary(None),
                }
        return {
            "key": "unauthorized",
            "label": "认证未通过",
            "label_en": "Unauthorized",
            "tone": "bad",
            "quota": quota_summary(None),
        }
    fixed = {
        402: ("billing", "套餐或额度受限", "warn"),
        403: ("forbidden", "访问受限", "bad"),
        404: ("missing", "资源不可用", "warn"),
        408: ("timeout", "请求超时", "warn"),
        429: ("rate_limited", "请求过于频繁", "warn"),
        500: ("upstream_error", "上游暂时异常", "warn"),
        502: ("upstream_error", "上游暂时异常", "warn"),
        503: ("upstream_error", "上游暂时异常", "warn"),
        504: ("upstream_error", "上游暂时异常", "warn"),
    }
    key, label, tone = fixed.get(status_code, ("unknown", "状态待确认", "neutral"))
    if status_code <= 0:
        key, label, tone = "network", "连接未完成", "warn"
    return {"key": key, "label": label, "tone": tone, "quota": quota_summary(None)}
