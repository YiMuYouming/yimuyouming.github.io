#!/usr/bin/env python3
"""周报公开页（W8 S4，G3）。

事实区（hero、KPI、每日脉络、市场表）**从数据取**：PnL 摘要 +
Market_Watch 的 `review_index_fields(date)` 封存原件——**不解析周报 Markdown 的
表格**（铁律 1：一个事实一个出处，解析出来的表是第二份）。

叙述区看 `公开写作/` 里有没有 `kind: weekly`、`week` 对得上的已发布文件；有就原样
附上，没有就只出事实区。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")


def parse_week(week: str) -> tuple[int, int]:
    match = WEEK_RE.match(str(week).strip())
    if not match:
        raise ValueError(f"invalid week: {week!r}（要 2026-W40 这种形状）")
    year, iso = int(match.group(1)), int(match.group(2))
    if not 1 <= iso <= 53:
        raise ValueError(f"invalid iso week: {iso}")
    return year, iso


def week_label(year: int, iso: int) -> str:
    return f"{year:04d}-W{iso:02d}"


def days_of_week(year: int, iso: int) -> list[dict[str, Any]]:
    monday = date.fromisocalendar(year, iso, 1)
    return [{"date": (monday + timedelta(days=offset)).isoformat(), "index": {}}
            for offset in range(7)]


def _money(value: Any) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


def fact_section(days: list[dict[str, Any]], pnl: dict[str, Any]) -> str:
    """每日脉络 + 四项指标。缺数的那天不出行，不补 0。"""
    rows = []
    for day in days:
        index = day.get("index") or {}
        if not index:
            continue
        rows.append(
            "<tr>"
            f"<td>{day.get('date', '')}</td>"
            f"<td>{index.get('情绪值', '—')}</td>"
            f"<td>{index.get('上证涨幅', '—')}</td>"
            f"<td>{index.get('涨停家数', '—')}</td>"
            f"<td>{index.get('最高板', '—')}</td>"
            "</tr>"
        )
    if not rows:
        table = "<p class=\"empty\">这一周还没有封存的复盘数据。</p>"
    else:
        table = (
            "<table><thead><tr><th>日期</th><th>情绪</th><th>上证</th>"
            "<th>涨停</th><th>最高板</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>"
        )
    summary = (pnl or {}).get("summary") or {}
    meta = (pnl or {}).get("meta") or {}
    kpis = (
        '<div class="kpi"><span class="lbl">当前资产</span>'
        f"<b>{_money(meta.get('total_asset'))}</b></div>"
        '<div class="kpi"><span class="lbl">累计入金</span>'
        f"<b>{_money(meta.get('total_deposit'))}</b></div>"
        '<div class="kpi"><span class="lbl">本周 TWR</span>'
        f"<b>{summary.get('pnl_pct', '—')}</b></div>"
        '<div class="kpi"><span class="lbl">数据截至</span>'
        f"<b>{summary.get('last_date', '—')}</b></div>"
    )
    return f'<section id="facts"><h2>事实</h2><div class="kpis">{kpis}</div>{table}</section>'


def narrative_section(writing: list[dict[str, Any]], week: str) -> str:
    """本周的已发布写作；没有就出空字符串，不出占位。"""
    label = week_label(*parse_week(week))
    year = label[:4]
    # 写作里的 week 可能是 "W40" 也可能是 "2026-W40"（两种写法都出现过），
    # 归一成 ISO 形状再比，别因为写法不同就丢掉本週的稿。
    accepted = {label, f"W{label.split('-W')[1]}", f"{year}-W{label.split('-W')[1]}"}
    picked = [
        item for item in writing or []
        if isinstance(item, dict)
        and item.get("kind") == "weekly"
        and str(item.get("week") or "").strip() in accepted
        and item.get("status") == "published"
    ]
    if not picked:
        return ""
    item = picked[0]
    # 写作原文发布、不过红线（W8 S5）：整段包进 writing-body 标记里。
    return (
        '<section id="narrative"><h2>' + str(item.get("title") or label)
        + '</h2><div class="meta">弈沐写于 ' + str(item.get("published_at") or "") + '</div>'
        + '<div class="writing-body" data-public-writing="verbatim">'
        + str(item.get("body") or "") + '</div></section>'
    )


PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{label} 周报 · 弈沐资本</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Noto+Serif+SC:wght@400;600&display=swap" rel="stylesheet">
<style>
body{{margin:0;background:#faf9f7;color:#1f2328;font-family:"Noto Serif SC",serif;line-height:1.7}}
.wrap{{max-width:820px;margin:0 auto;padding:28px 20px 60px}}
a.back{{color:#6b7280;text-decoration:none;font-size:14px}}
h1{{font-size:22px;margin:12px 0 4px}}
.stamp{{color:#6b7280;font-size:13px;margin-bottom:22px}}
section{{border:1px solid #e5e7eb;border-radius:12px;background:rgba(255,255,255,.9);padding:16px 18px;margin-bottom:16px}}
section h2{{font-size:17px;margin:0 0 12px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px}}
.kpi .lbl{{display:block;color:#6b7280;font-size:12px}}
.kpi b{{display:block;font-family:"JetBrains Mono",monospace;font-size:19px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{padding:7px 8px;border-bottom:1px solid #e5e7eb;text-align:right}}
th:first-child,td:first-child{{text-align:left}}
.empty{{color:#6b7280;font-size:13px;margin:4px 0}}
.meta{{color:#6b7280;font-size:12px;margin-bottom:12px}}
footer{{margin-top:28px;border-top:1px solid #e5e7eb;padding-top:14px;color:#6b7280;font-size:12px}}
@media(max-width:720px){{.kpis{{grid-template-columns:repeat(2,1fr)}}}}
</style>
</head>
<body><div class="wrap">
<a class="back" href="../index.html">← 回首页</a>
<h1>{label} 周报</h1>
<div class="stamp">事实区来自封存数据 · 版本 {version}</div>
{facts}
{narrative}
<footer>本页为公开口径，不构成任何收益承诺或投资建议。过往表现不代表未来结果。</footer>
</div></body>
</html>
"""


def render(days, pnl, *, writing=None, week="2026-W40", version="dev") -> str:
    year, iso = parse_week(week)
    stats = {day["date"]: day.get("index") or {} for day in days or []}
    ordered = [{"date": day["date"], "index": stats.get(day["date"], {})}
               for day in days_of_week(year, iso)]
    return PAGE.format(
        label=week_label(year, iso),
        version=version,
        facts=fact_section(ordered, pnl or {}),
        narrative=narrative_section(writing or [], week),
    )


def _load_index(path: str | Path) -> tuple[list, dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    days = payload.get("days") if isinstance(payload, dict) else payload
    pnl = payload.get("pnl") if isinstance(payload, dict) else {}
    return list(days or []), pnl or {}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成周报公开页（W8 S4）")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--week", required=True)
    build.add_argument("--index", required=True, help="含 days 与 pnl 的 JSON")
    build.add_argument("--writing-index", default=None)
    build.add_argument("--out", default=str(PROJECT_ROOT / "weekly"))
    build.add_argument("--version", default="")
    build.add_argument("--check", action="store_true")
    build.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        days, pnl = _load_index(args.index)
        week = week_label(*parse_week(args.week))
        writing = []
        if args.writing_index:
            payload = json.loads(Path(args.writing_index).read_text(encoding="utf-8"))
            writing = payload.get("entries") if isinstance(payload, dict) else payload
        page = render(days or [], pnl, writing=writing or [], week=week, version=args.version)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.dry_run:
        print(f"[dry-run] {week} 周报 {len(page)} 字节，"
              f"{sum(1 for d in days if d.get('index'))} 天有封存数据")
        return 0
    target = Path(args.out) / f"{week}.html"
    if args.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != page:
            print(f"weekly_page_stale:{target}", file=sys.stderr)
            return 1
        print("weekly page up to date")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8")
    print(f"weekly page written: {target} ({len(page)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
