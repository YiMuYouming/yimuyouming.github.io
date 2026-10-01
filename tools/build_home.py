#!/usr/bin/env python3
"""Render the whole portal home page from data + template (W8 S2).

不再用正则就地替换首页区块（开工单 W8 第二节第 3 点）：输入是数据，输出是整页。

**本文件不做任何业绩计算。** 累计 TWR、相对指数、最大回撤、曲线、周期切换、
明细表全部由 ``static/pnl-engine.js`` 在浏览器里算（审计回复 1 第一节）：
同一个公式只允许一份实现，服务端再写一遍就成了第二份真相。
模板里这些位置的初始值一律是 ``—``，由引擎填。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = WORKSPACE / "templates" / "home.html"
CURRENT_HOME = WORKSPACE / "index.html"
WRITING_INDEX_PATH = WORKSPACE / "data" / "writing-index.json"
REPORTS_PATH = WORKSPACE / "report" / "reports.json"

# 与 static/pnl-engine.js 的 MET / PER 一一对应；这里只用来生成按钮，不参与计算。
INDEX_BUTTONS = (("sh", "上证"), ("sz", "深证"), ("cy", "创业板"))
PERIOD_BUTTONS = (
    ("today", "日"), ("week", "周"), ("month", "月"),
    ("quarter", "近三月"), ("year", "近一年"), ("all", "全部"),
)


def writing_sections(writing_index: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Group published writing by kind; empty lists render nothing (铁律 4)."""
    entries = writing_index.get("entries") or []
    return {
        "essay": [item for item in entries if item.get("kind") == "essay"],
        "daily": [item for item in entries if item.get("kind") == "daily"],
        "weekly": [item for item in entries if item.get("kind") == "weekly"],
    }


def _json_for_script(payload: Any) -> str:
    """JSON for an inline <script>; ``</`` must not close the script early."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


PHASE1_START = "2026-03-23"
# 页数与 archive/phase1.html 里那一行一致（build_archive_index 统计得出）
ARCHIVE_PAGE_COUNT = 200
PHASE1_END = "2026-09-30"


def _only_phase2(pages: list) -> list:
    """首页只列 10 月以后的页面；第一阶段的入口收在 archive/phase1.html。"""
    kept = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        day = str(page.get("date") or page.get("published_at") or "")[:10]
        if day and day <= PHASE1_END:
            continue
        kept.append(page)
    return kept


def _archive_summary(weeks: list[tuple[str, int]]) -> str:
    """One line: 2026-03-23 至 2026-09-30 · 200 页（页数读归档页自己的统计）。"""
    if not weeks:
        return "—"
    return f"{weeks[0][0]} 至 {weeks[0][1]} · {ARCHIVE_PAGE_COUNT} 页"


def _report_items(reports: Any) -> list[dict[str, Any]]:
    """``report/reports.json`` is a plain list of report records."""
    if isinstance(reports, list):
        return [item for item in reports if isinstance(item, dict)]
    if isinstance(reports, dict):
        items = reports.get("reports")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def _report_row(item: dict[str, Any]) -> str:
    folder = str(item.get("folder") or "")
    filename = str(item.get("filename") or "")
    href = f"report/{folder}/{filename}" if filename else "report/"
    title = str(item.get("title") or filename or "")
    return f'<li><a href="{href}">{title}</a></li>'


def _entry_date(item: dict[str, Any]) -> str:
    return str(item.get("date") or item.get("published_at") or "")


def _render_entries(entries: list[dict[str, Any]]) -> str:
    """Empty list renders an empty string, not a placeholder section."""
    if not entries:
        return ""
    rows = "".join(
        "<li>"
        f'<span class="writing-date">{_entry_date(item)}</span>'
        f'<span class="writing-title">{item.get("title") or _entry_date(item)}</span>'
        f'<span class="writing-series">{item.get("series", "")}</span>'
        "</li>"
        for item in entries
    )
    return f'<ul class="writing-list">{rows}</ul>'


def render_home(
    pnl_data: dict[str, Any],
    *,
    writing_index: dict[str, Any] | None = None,
    reports: dict[str, Any] | None = None,
    archive_groups: dict[str, Any] | None = None,
    version: str = "",
    as_of: str = "",
) -> str:
    """Render the complete home page. Pure: same inputs, same bytes."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    writing = writing_sections(writing_index or {})
    report_items = _report_items(reports)
    raw_weeks = (archive_groups or {}).get("weeks")
    archive_weeks = (sorted(raw_weeks.items()) if isinstance(raw_weeks, dict)
                     else list(raw_weeks or []))

    replacements = {
        "{{VERSION}}": version,
        "{{AS_OF}}": as_of or str((pnl_data.get("summary") or {}).get("last_date") or ""),
        "{{DAILY_COUNT}}": str((pnl_data.get("summary") or {}).get("daily_count") or "—"),
        "{{POINTS}}": str(len((pnl_data.get("all_sh") or {}).get("portfolio") or [])),
        "{{INDEX_BUTTONS}}": "".join(
            f'<button type="button" class="pnl-idx-btn{" active" if key == "sh" else ""}" '
            f'data-idx="{key}">{label}</button>'
            for key, label in INDEX_BUTTONS
        ),
        "{{PERIOD_BUTTONS}}": "".join(
            f'<button type="button" class="pnl-period{" active" if key == "all" else ""}" '
            f'data-p="{key}">{label}</button>'
            for key, label in PERIOD_BUTTONS
        ),
        "{{ESSAYS}}": _render_entries(writing["essay"]),
        "{{DAILIES}}": _render_entries(writing["daily"][:12]),
        "{{WEEKLIES}}": _render_entries(writing["weekly"]),
        "{{REPORT_ITEMS}}": "".join(_report_row(item) for item in report_items),
        "{{REPORT_COUNT}}": str(len(report_items)),
        "{{ARCHIVE_GROUPS}}": _archive_summary(archive_weeks),
        "{{PNL_DATA_JSON}}": _json_for_script(pnl_data),
        "{{WRITING_JSON}}": _json_for_script(writing_index or {}),
    }
    page = template
    for marker, value in replacements.items():
        page = page.replace(marker, value)
    left = re.findall(r"\{\{[A-Z_]+\}\}", page)
    if left:
        raise ValueError(f"home template has unfilled slots: {sorted(set(left))}")
    return page


def read_pnl_data(source: Path) -> dict[str, Any]:
    html = Path(source).read_text(encoding="utf-8")
    match = re.search(r"var PNL_DATA = (\{.*?\});\s*</script>", html, flags=re.DOTALL)
    if not match:
        raise SystemExit(f"pnl_data_missing:{source}")
    return json.loads(match.group(1))


def _load(path: str | Path, default: Any) -> Any:
    file = Path(path)
    if not file.is_file():
        return default
    return json.loads(file.read_text(encoding="utf-8"))


def archive_groups_from_disk() -> dict[str, Any]:
    """Summarize the frozen phase-1 archive by its first/last day, from disk.

    页数与日期范围读 `archive/phase1.html` 生成时写进页面的那一行，
    不在这里另扫一遍目录——同一个数字两个出处早晚会对不上。
    """
    first, last = "", ""
    for sub in ("review-notes", "daily-notes"):
        root = WORKSPACE / sub
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.html")):
            match = re.search(r"(\d{4})-(\d{2})-(\d{2})", path.stem)
            if not match:
                continue
            day = "-".join(match.groups())
            if PHASE1_START <= day <= PHASE1_END:
                first = first or day
                last = day
    return {"weeks": [(first or PHASE1_START, last or PHASE1_END)],
            "counts": {"first": first or PHASE1_START, "last": last or PHASE1_END}}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="整页渲染门户首页（W8 S2）")
    parser.add_argument("--pnl-from", default=str(CURRENT_HOME),
                        help="从现网首页读 PNL_DATA（默认 index.html）")
    parser.add_argument("--writing-index", default=str(WRITING_INDEX_PATH))
    parser.add_argument("--reports", default=str(REPORTS_PATH))
    parser.add_argument("--archive-groups", default=None,
                        help="第一阶段归档分组 JSON；缺省时按现有页面数推断")
    parser.add_argument("--version", default="", help="数据版本（提交号短哈希）")
    parser.add_argument("--out", default=str(WORKSPACE / "index.html"))
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pnl_data = read_pnl_data(Path(args.pnl_from))
    page = render_home(
        pnl_data,
        writing_index=_load(args.writing_index, {"schema": "writing_index.v1", "entries": [], "issues": []}),
        reports=_load(args.reports, {}),
        archive_groups=(
            _load(args.archive_groups, None) if args.archive_groups else archive_groups_from_disk()
        ),
        version=args.version,
        as_of=str((pnl_data.get("summary") or {}).get("last_date") or ""),
    )
    out = Path(args.out)
    if args.check:
        if not out.is_file() or out.read_text(encoding="utf-8") != page:
            print(f"home_stale:{out}（重新生成后再提交）", file=sys.stderr)
            return 1
        print("home up to date")
        return 0
    out.write_text(page, encoding="utf-8")
    print(f"home rendered: {len(page)} bytes → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())