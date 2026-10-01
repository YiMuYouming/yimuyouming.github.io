#!/usr/bin/env python3
"""第一阶段归档入口页（W8 S3）。

2026-03-23 至 09-30 的复盘页、手记页、周报、月报**冻结**：文件原样不动、URL 不变、
不再重新生成。这个脚本只做一件事——生成 `archive/phase1.html`，按周把这些页面列出来。

按周列而不是逐页平铺：234 个页面平铺没人会看；首页的手记与复盘列表也从此只显示
10 月以后的，第一阶段的入口收在这一个页面里。
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PHASE1_START = "2026-03-23"
PHASE1_END = "2026-09-30"
DAY_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.html$")

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>第一阶段归档（{start} 至 {end}） · 弈沐资本</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Noto+Serif+SC:wght@400;600&display=swap" rel="stylesheet">
<style>
body{{margin:0;background:#faf9f7;color:#1f2328;font-family:"Noto Serif SC",serif;line-height:1.7}}
.wrap{{max-width:820px;margin:0 auto;padding:28px 20px 60px}}
a.back{{color:#6b7280;text-decoration:none;font-size:14px}}
h1{{font-size:22px;margin:12px 0 4px}}
.stamp{{color:#6b7280;font-size:13px;margin-bottom:8px}}
.note{{color:#6b7280;font-size:13px;margin:0 0 24px}}
.week{{border:1px solid #e5e7eb;border-radius:12px;background:rgba(255,255,255,.9);padding:14px 16px;margin-bottom:12px}}
.week h2{{font-size:15px;margin:0 0 8px;display:flex;justify-content:space-between}}
.week h2 span{{color:#6b7280;font-family:"JetBrains Mono",monospace;font-size:12px}}
.week ul{{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:10px}}
.week a{{font-family:"JetBrains Mono",monospace;font-size:13px;color:#1f2328}}
footer{{margin-top:32px;border-top:1px solid #e5e7eb;padding-top:14px;color:#6b7280;font-size:12px}}
</style>
</head>
<body><div class="wrap">
<a class="back" href="../index.html">← 回首页</a>
<h1>第一阶段归档</h1>
<div class="stamp">{start} 至 {end} · {total} 个页面 · 已冻结，不再重新生成</div>
<p class="note">这一阶段的复盘页、手记页、周报与月报保持原样、URL 不变，只在这里留一个入口。
10 月以后的页面只出现在首页，不在这里。</p>
{weeks}
<footer>本页为公开口径，不构成任何收益承诺或投资建议。过往表现不代表未来结果。</footer>
</div></body>
</html>
"""


def week_label(day: date) -> str:
    iso_year, iso_week, _weekday = day.isocalendar()
    return f"{iso_year:04d}-W{iso_week:02d}"


def in_phase1(name: str) -> bool:
    """带不带 .html 都认：调用方有时拿到的是文件名，有时是日期。"""
    match = DAY_RE.match(name if name.endswith(".html") else name + ".html")
    if not match:
        return False
    day = "-".join(match.groups())
    return PHASE1_START <= day <= PHASE1_END


def group_by_week(pages) -> list[dict]:
    """按 ISO 周分组；组内按日期排序，最早的周在前。"""
    buckets: dict[str, list[tuple[str, str]]] = {}
    for path in pages:
        match = DAY_RE.match(path.name)
        if not match:
            continue
        if not match:
            continue
        day = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if day.isoformat() < PHASE1_START or day.isoformat() > PHASE1_END:
            continue
        buckets.setdefault(week_label(day), []).append(
            (day.isoformat(), day.strftime("%m-%d"), path.as_posix())
        )
    groups = []
    for label in sorted(buckets):
        entries = sorted(buckets[label], key=lambda item: item[0])
        groups.append({"label": label, "count": len(entries),
                       "pages": [(day, title, rel) for day, title, rel in entries]})
    return groups


def render(groups) -> str:
    weeks = "".join(
        f'<div class="week"><h2>{group["label"]}'
        f'<span>{group["count"]} 篇</span></h2><ul>'
        + "".join(f'<li><a href="../{rel}">{title}</a></li>'
                  for day, title, rel in group["pages"])
        + "</ul></div>"
        for group in groups
    )
    total = sum(group["count"] for group in groups)
    return PAGE.format(start=PHASE1_START, end=PHASE1_END, total=total, weeks=weeks)


def build(archive_root: Path | str | None = None) -> tuple[str, list[dict]]:
    root = Path(archive_root or PROJECT_ROOT)
    pages: list[Path] = []
    for sub in ("review-notes", "daily-notes"):
        pages.extend(sorted((root / sub).glob("*.html")))
    groups = group_by_week(pages)
    return render(groups), groups


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成第一阶段归档入口页（W8 S3）")
    parser.add_argument("--root", default=str(PROJECT_ROOT))
    parser.add_argument("--out", default=None)
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    page, groups = build(args.root)
    target = Path(args.out) if args.out else Path(args.root) / "archive" / "phase1.html"
    if args.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != page:
            print(f"archive_stale:{target}", file=sys.stderr)
            return 1
        print(f"archive up to date（{sum(g['count'] for g in groups)} 个页面）")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8")
    print(f"archive written: {target}（{sum(g['count'] for g in groups)} 个页面，"
          f"{len(groups)} 周）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
