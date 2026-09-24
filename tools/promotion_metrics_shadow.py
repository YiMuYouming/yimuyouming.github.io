"""Small public projection of the optional P4 promotion comparison."""

import json
from datetime import date
from html import escape
from pathlib import Path


SCHEMA = "market-watch.promotion-metrics.v1"
TIERS = (("one_to_two", "一进二"), ("two_to_three", "二进三"),
         ("three_to_four_plus", "三进四及以上"))


def render(path, review_date):
    """Render whitelisted comparison fields; never serialize the source object."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA:
        raise ValueError("promotion_metrics_schema_unsupported")
    authority = payload.get("authority")
    if authority != {"mode": "shadow_only", "active": False}:
        raise ValueError("promotion_metrics_authority_invalid")
    trade_date = payload.get("trade_date")
    try:
        if date.fromisoformat(trade_date).isoformat() != review_date:
            raise ValueError("promotion_metrics_date_mismatch")
    except (TypeError, ValueError) as exc:
        raise ValueError("promotion_metrics_date_mismatch") from exc
    status = payload.get("status")
    if status not in {"ready", "partial", "blocked"}:
        raise ValueError("promotion_metrics_status_invalid")
    gate = payload.get("validation_gate")
    if not isinstance(gate, dict) or gate.get("authority_switch") not in {"blocked", "allowed"}:
        raise ValueError("promotion_metrics_gate_invalid")
    if gate["authority_switch"] == "allowed":
        days = gate.get("reliable_history_days")
        if not isinstance(days, int) or isinstance(days, bool) or days < 10 or gate.get("unexplained_differences") != 0:
            raise ValueError("promotion_metrics_gate_inconsistent")

    label = {"ready": "可对照", "partial": "来源待补齐", "blocked": "暂不可用"}[status]
    header = (
        '<section class="section" id="promotion-shadow">'
        '<div class="sh">逐股晋级率对照（影子数据）</div><div class="sb">'
        f'<div class="sbx warn">{escape(review_date)} · {label}。'
        '仅供新旧口径对照，不参与计划或交易判断。</div>'
    )
    if status != "ready":
        return header + "</div></section>"

    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("promotion_metrics_missing")
    cards = []
    for key, title in TIERS:
        item = metrics.get(key)
        if not isinstance(item, dict):
            raise ValueError("promotion_metrics_tier_missing")
        numerator, denominator, pct = (item.get(name) for name in ("numerator", "denominator", "pct"))
        if not isinstance(numerator, int) or isinstance(numerator, bool) or not isinstance(denominator, int) or isinstance(denominator, bool) or numerator < 0 or denominator < 0 or numerator > denominator:
            raise ValueError("promotion_metrics_tier_invalid")
        if denominator == 0:
            if pct is not None:
                raise ValueError("promotion_metrics_zero_denominator")
            value = "不可用"
        else:
            if not isinstance(pct, (int, float)) or isinstance(pct, bool) or abs(pct - numerator / denominator * 100) > 0.11:
                raise ValueError("promotion_metrics_pct_invalid")
            value = f"{pct:g}%（{numerator}/{denominator}）"
        cards.append(f'<div class="stat-card"><div class="val">{value}</div><div class="lbl">{title}</div></div>')
    return header + '<div class="stats-grid">' + "".join(cards) + "</div></div></section>"
