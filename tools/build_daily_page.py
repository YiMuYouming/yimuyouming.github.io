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
.badge-sample{{display:inline-block;background:#FEF3C7;border:1px solid #F59E0B;color:#92400E;
  border-radius:999px;padding:2px 10px;font-size:12px;margin-left:8px;vertical-align:middle}}
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
<div class="stamp">每日公开页 · 指标来自封存复盘原件（数据日 {data_date}） · 版本 {version}{sample_badge}</div>
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


# 指标的小数位：封存原件里情绪值是四位小数（47.6164），直接印在公开页上
# 像没写完。**只改展示，JSON 里的原值不动**——精度是数据的事，页面只负责
# 让人读得懂。与审计回复 3 第三节要求的「累计入金改两位小数」是同一类问题。
DECIMALS = {"情绪值": 1}


def _fmt_metric(key: str, value: Any) -> str:
    digits = DECIMALS.get(key)
    if digits is not None and isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{float(value):.{digits}f}"
    return _fmt(value)


def render_facts(index: dict[str, Any]) -> str:
    cells = []
    for key, label in INDEX_FIELDS:
        cells.append(
            f'<div class="fact"><span class="lbl">{label}</span>'
            f'<b>{_fmt_metric(key, (index or {}).get(key))}</b></div>'
        )
    return "".join(cells)


def render_article(writing: list[dict[str, Any]] | None, *, day: str = "") -> str:
    """有已发布写作才出正文；正文原样渲染，不改写、不删敏。"""
    if not writing:
        return ""
    item = writing[0]
    title = _fmt(item.get("title") or item.get("date"))
    # 去重的两个候选：文章标题，以及页面自己写过的页首标题（{day}）
    body = _drop_leading_h1(str(item.get("body") or ""), title, day)
    # 写作原文发布、不过红线（W8 S5）：整段包进 writing-body 标记里，
    # 红线扫描器据此整段跳过；事实部分照旧全查。
    return (
        '<article><h2>' + title
        + '</h2><div class="meta">弈沐写于 '
        + _fmt(item.get("published_at") or item.get("date"))
        + ' · 来源 ' + _fmt(item.get("path")) + '</div>'
        + '<div class="writing-body" data-public-writing="verbatim">' + body + '</div></article>'
    )


def _drop_leading_h1(body: str, *titles: str) -> str:
    """正文第一行的 H1 与页面已有的标题重复，去掉。

    页面自己已经写过两处标题：页首的 `<h1>{day}</h1>` 和文章的 `<h2>标题</h2>`。
    写作正文习惯以 `# 标题` 或 `# 日期` 起头，三选一命中就去掉**开头那一个**——
    只去开头，正文里别的标题照旧保留（写作原文发布，只做排版层面的去重，
    不改内容）。
    """
    wanted = {str(t).strip() for t in titles if str(t or "").strip()}
    stripped = body.lstrip()
    match = re.match(r"^<h1>(.*?)</h1>\s*", stripped, re.DOTALL)
    if not match:
        return body
    inner = re.sub(r"<[^>]+>", "", match.group(1)).strip()
    if inner not in wanted:
        return body
    return stripped[match.end():]


def build_daily_page(
    index: dict[str, Any],
    *,
    day: str,
    data_date: str | None = None,
    sample: bool = False,
    writing: list[dict[str, Any]] | None = None,
    out_dir: Path | str | None = None,
    version: str = "",
) -> str:
    if not ISO_DAY_RE.match(str(day)):
        raise ValueError(f"invalid day: {day!r}")
    if day < PHASE2_START:
        raise ValueError(f"phase1_frozen:{day}（第一阶段的页面冻结，不重新生成）")
    # 页面日期和指标日期必须对得上。根因在源头：review_index_fields 只回
    # MARKET_INDEX_FIELDS，`date` 不在里面，指标 JSON 本身不自带日期——
    # 不显式收口的话，"10-08 的页面"可以挂着 9-30 的数发出去。
    if not data_date:
        if not sample:
            raise ValueError(f"data_date_required:{day}（正式出页必须给出指标的数据日）")
        data_date = day
    elif not ISO_DAY_RE.match(str(data_date)):
        raise ValueError(f"invalid data_date: {data_date!r}")
    elif str(data_date) != str(day) and not sample:
        raise ValueError(f"data_date_mismatch:{data_date}!={day}（页面日期与指标日期不一致）")
    # 第二道防线：指标 JSON **自己**报它是谁的日期（MW 侧 v6 路径输出
    # ``date = review_facts.trading_date``，见 Market_Watch 7fdd120）。
    #
    # 上面那道 ``data_date_mismatch`` 是**同义反复**：``sync_portal.py:374``
    # 传的就是 ``--data-date target_day``，与 ``day`` 同一个变量，
    # 两个值永远相等 —— 「拿 9-30 的指标出 10-08 的页」照常出页。
    # 这里读的是**指标自己的日期**，与调用方传什么无关。
    #
    # 没有 ``date`` 就维持现状、不新增阻断：v5 路径的指标 JSON 不带日期，
    # 堵死它等于把 v5 的页面全打死。格式非法同样不当不一致（沿用现状）。
    index_date = str((index or {}).get("date") or "").strip()
    if index_date and ISO_DAY_RE.match(index_date):
        if index_date != str(day) and not sample:
            raise ValueError(
                f"index_date_mismatch:{index_date}!={day}"
                "（指标 JSON 自带的日期与页面日期不一致，拒绝出页）"
            )
    return PAGE.format(
        day=day,
        data_date=data_date,
        version=version or "dev",
        sample_badge=(
            '<span class="badge-sample" data-sample="1">示例（预演数据，未发布）</span>'
            if sample else ""
        ),
        facts=render_facts(index),
        article=render_article(writing, day=day),
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


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_INLINE_RE = re.compile(
    r"(?P<code>`[^`]+`)"
    r"|(?P<bold>\*\*[^*]+\*\*)"
    r"|(?P<italic>\*[^*\n]+\*)"
)


def _render_inline(text: str) -> str:
    """行内标记：**粗体**、*斜体*、`代码`。

    写作原文发布——这里只把标记换成对应的 HTML 标签，文字一个字不改。
    """
    out, pos = [], 0
    for m in _INLINE_RE.finditer(text):
        out.append(_escape(text[pos:m.start()]))
        if m.group("code"):
            out.append("<code>" + _escape(m.group("code")[1:-1]) + "</code>")
        elif m.group("bold"):
            out.append("<strong>" + _escape(m.group("bold")[2:-2]) + "</strong>")
        else:
            out.append("<em>" + _escape(m.group("italic")[1:-1]) + "</em>")
        pos = m.end()
    out.append(_escape(text[pos:]))
    return "".join(out)


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
            out.append(_escape(line))
            continue
        if not line.strip():
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            out.append(f"<h{level}>{_render_inline(heading.group(2))}</h{level}>")
            continue
        if line.startswith("- "):
            out.append("<li>" + _render_inline(line[2:]) + "</li>")
            continue
        out.append("<p>" + _render_inline(line) + "</p>")
    if in_code:
        out.append("</code></pre>")
    return "".join(out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成每个交易日的公开页（W8 S3）")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="生成一天的公开页")
    build.add_argument("--day", required=True)
    build.add_argument("--index", required=True, help="review_index_fields 的 JSON 输出")
    build.add_argument("--data-date", default=None,
                       help="指标所属交易日（YYYY-MM-DD）；与 --day 不一致就拒绝出页")
    build.add_argument("--sample", action="store_true",
                       help="预演数据：允许日期不一致，但页面上会带「示例」徽标")
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
            index, day=args.day, data_date=args.data_date, sample=args.sample,
            writing=_load_writing(args.writing_index, args.day, args.writing_root),
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
