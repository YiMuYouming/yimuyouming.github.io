#!/usr/bin/env python3
"""每个交易日一张公开页（W8 S3）。

四项指标来自**封存原件**——Market_Watch 的 `review_index_fields(date)` 读的是
daily bundle 里的复盘笔记快照，不解析公开稿、不重新计算。当天有已发布的
「每日/」写作就附在页面上（正文原样渲染），没有就只出事实区。

不重新生成第一阶段的页面：`--from` 之后的日期才允许出页。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PHASE2_START = "2026-10-01"          # 第一阶段（03-23 至 09-30）冻结，不再出页
ISO_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 只出四项；其余字段不进公开页（红线只管机器生成的事实部分）
INDEX_FIELDS = (
    ("情绪值", "情绪"),
    ("上证涨幅", "上证"),
    ("涨停家数", "涨停"),
    ("最高板", "最高板"),
)

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{day} · 每日公开页 · 弈沐资本</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Noto+Serif+SC:wght@400;600&display=swap" rel="stylesheet">
<style>
body{{margin:0;background:#faf9f7;color:#1f2328;font-family:"Noto Serif SC",serif;line-height:1.7}}
.wrap{{max-width:760px;margin:0 auto;padding:28px 20px 60px}}
a.back{{color:#6b7280;text-decoration:none;font-size:14px}}
h1{{font-size:22px;margin:12px 0 4px}}
.stamp{{color:#6b7280;font-size:13px;margin-bottom:24px}}
.facts{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.fact{{background:rgba(255,255,255,.9);border:1px solid #e5e7eb;border-radius:12px;padding:14px}}
.fact .lbl{{display:block;color:#6b7280;font-size:12px}}
.fact b{{display:block;font-family:"JetBrains Mono",monospace;font-size:22px;margin-top:4px}}
.note{{color:#6b7280;font-size:12px;margin-top:10px}}
article{{margin-top:28px;border-top:1px solid #e5e7eb;padding-top:20px}}
article h2{{font-size:18px;margin:0 0 8px}}
article .meta{{color:#6b7280;font-size:12px;margin-bottom:14px}}
article .body img{{max-width:100%}}
footer{{margin-top:36px;border-top:1px solid #e5e7eb;padding-top:14px;color:#6b7280;font-size:12px}}
@media(max-width:720px){{.facts{{grid-template-columns:repeat(2,1fr)}}}}
</style>
</head>
<body><div class="wrap">
<a class="back" href="../index.html">← 回首页</a>
<h1>{day}</h1>
<div class="stamp">每日公开页 · 指标来自封存复盘原件 · 版本 {version}</div>
<div class="facts">{facts}</div>
<div class="note">口径与复盘笔记一致；个股与交易明细不公开。</div>
{article}
<footer>本页为公开口径，不构成任何收益承诺或投资建议。过往表现不代表未来结果。</footer>
</div></body>
</html>
"""


def _fmt(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value)


def render_facts(index: dict[str, Any]) -> str:
    cells = []
    for key, label in INDEX_FIELDS:
        cells.append(
            f'<div class="fact"><span class="lbl">{label}</span>'
            f'<b>{_fmt((index or {}).get(key))}</b></div>'
        )
    return "".join(cells)


def render_article(writing: list[dict[str, Any]] | None) -> str:
    """有已发布写作才出正文；正文原样渲染，不改写、不删敏。"""
    if not writing:
        return ""
    item = writing[0]
    body = str(item.get("body") or "")
    # 写作原文发布、不过红线（W8 S5）：整段包进 writing-body 标记里，
    # 红线扫描器据此整段跳过；事实部分照旧全查。
    return (
        '<article><h2>' + _fmt(item.get("title") or item.get("date"))
        + '</h2><div class="meta">弈沐写于 '
        + _fmt(item.get("published_at") or item.get("date"))
        + ' · 来源 ' + _fmt(item.get("path")) + '</div>'
        + '<div class="writing-body" data-public-writing="verbatim">' + body + '</div></article>'
    )


def build_daily_page(
    index: dict[str, Any],
    *,
    day: str,
    writing: list[dict[str, Any]] | None = None,
    out_dir: Path | str | None = None,
    version: str = "",
) -> str:
    if not ISO_DAY_RE.match(str(day)):
        raise ValueError(f"invalid day: {day!r}")
    if day < PHASE2_START:
        raise ValueError(f"phase1_frozen:{day}（第一阶段的页面冻结，不重新生成）")
    return PAGE.format(
        day=day,
        version=version or "dev",
        facts=render_facts(index),
        article=render_article(writing),
    )


def _load_index(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "fields" in payload and isinstance(payload["fields"], dict):
        return payload["fields"]
    return payload if isinstance(payload, dict) else {}


def _load_writing(path: str | Path | None, day: str,
                  writing_root: Path | str | None = None) -> list[dict[str, Any]]:
    if not path:
        return []
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else payload
    picked = []
    for entry in entries or []:
        if not isinstance(entry, dict) or entry.get("status") != "published":
            continue
        if str(entry.get("date") or entry.get("published_at") or "")[:10] != day:
            continue
        base = Path(writing_root) if writing_root else PROJECT_ROOT / "vault-writing"
        source = base / entry["path"]
        body = ""
        if source.is_file():
            body = _markdown_to_html(source.read_text(encoding="utf-8"))
        picked.append({**entry, "body": body})
    return picked


def _markdown_to_html(text: str) -> str:
    """Minimal Markdown subset for published writing: headings, paragraphs, code.

    正文原样渲染——不删敏、不改写；这里只做格式转换。
    """
    body = text
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n?", body, re.DOTALL)
    if match:
        body = body[match.end():]
    lines, out, in_code = body.splitlines(), [], False
    for line in lines:
        if line.startswith("```"):
            out.append("</code></pre>" if in_code else "<pre><code>")
            in_code = not in_code
            continue
        if in_code:
            out.append(line.replace("&", "&amp;").replace("<", "&lt;"))
            continue
        if not line.strip():
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            out.append(f"<h{level}>{heading.group(2)}</h{level}>")
            continue
        if line.startswith("- "):
            out.append(f"<li>{line[2:]}</li>")
            continue
        out.append(f"<p>{line}</p>")
    if in_code:
        out.append("</code></pre>")
    return "".join(out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成每个交易日的公开页（W8 S3）")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="生成一天的公开页")
    build.add_argument("--day", required=True)
    build.add_argument("--index", required=True, help="review_index_fields 的 JSON 输出")
    build.add_argument("--writing-index", default=None)
    build.add_argument("--writing-root", default=None,
                       help="公开写作所在目录；缺省用 vault-writing/")
    build.add_argument("--out", default=str(PROJECT_ROOT / "daily"))
    build.add_argument("--version", default="")
    build.add_argument("--check", action="store_true")
    build.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        index = _load_index(args.index)
        page = build_daily_page(
            index, day=args.day, writing=_load_writing(args.writing_index, args.day, args.writing_root),
            out_dir=args.out, version=args.version,
        )
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.dry_run:
        print(f"[dry-run] {args.day} 公开页 {len(page)} 字节，指标 "
              f"{ {k: index.get(k) for k, _ in INDEX_FIELDS} }")
        return 0
    target = Path(args.out) / f"{args.day}.html"
    if args.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != page:
            print(f"daily_page_stale:{target}", file=sys.stderr)
            return 1
        print("daily page up to date")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8")
    print(f"daily page written: {target} ({len(page)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
