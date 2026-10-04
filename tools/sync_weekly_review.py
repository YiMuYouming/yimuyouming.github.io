#!/usr/bin/env python3
"""Publish a curated weekly HTML page into the Portal archive index.

The weekly page is editorially reviewed before this script runs. Daily Markdown
converters cannot safely infer its public narrative or privacy boundary.

W8 S7b（审计回复 9 第二节、审计回复 10 第三节第 13 条）：本脚本**不再改首页**。
首页由 `build_home.py` 整页渲染（数据来自 `data/writing-index.json` 等），周报入口
由它按 `weekly/index.html` 是否存在决定指向 `weekly/` 还是第一阶段归档；这里只把
周报页登记进 `review-notes/index.html`（第一阶段归档索引）并同步计数，删掉了原来
"正则就地改首页 + 重建近期时间线"的那一段。
"""

from html import escape
from pathlib import Path
import argparse
import re

PORTAL = Path(__file__).resolve().parent.parent
REVIEW_NOTES = PORTAL / "review-notes"

WEEKLY_NAME_RE = re.compile(r"weekly-\d{4}-\d{2}-\d{2}_\d{2}-\d{2}\.html")


def replace_exact_once(content, old, new, label):
    count = content.count(old)
    if count != 1:
        raise ValueError(f"{label}: expected one match, got {count}")
    return content.replace(old, new, 1)


def read_weekly_page(page_path):
    """校验并抽出归档卡需要的字段；缺一项就报错，不猜。"""
    page_path = Path(page_path).resolve()
    if page_path.parent != REVIEW_NOTES.resolve() or not WEEKLY_NAME_RE.fullmatch(
        page_path.name
    ):
        raise ValueError("expected a weekly HTML file in review-notes/")
    if not page_path.is_file():
        raise FileNotFoundError(page_path)
    label = page_path.read_text(encoding="utf-8")
    summary = re.search(r'<meta name="weekly-summary" content="([^"]+)">', label)
    if not summary:
        raise ValueError("weekly page needs a concise archive summary")
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", label, re.S)
    if not h1 or "W" not in h1.group(1):
        raise ValueError("weekly page needs a visible week title")
    week = re.search(r"W(\d+)", h1.group(1))
    days = re.search(r'<span>交易日</span>\s*<strong[^>]*>(\d+)天</strong>', label)
    if not week or not days:
        raise ValueError("weekly page needs a week number and trading-day KPI")
    start = re.search(r"weekly-(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})", page_path.name)
    _, sm, sd, em, ed = start.groups()
    return {
        "page": page_path,
        "summary": summary.group(1),
        "week": int(week.group(1)),
        "days": days.group(1),
        "range": f"{int(sm)}/{int(sd)} – {int(em)}/{int(ed)}",
    }


def sync_weekly(page_path):
    info = read_weekly_page(page_path)
    archive_path = REVIEW_NOTES / "index.html"
    archive = archive_path.read_text(encoding="utf-8")

    # 计数只从归档列表本身推，避免两处漂移。
    weekly_pages = sorted(REVIEW_NOTES.glob("weekly-*.html"))
    count = len(weekly_pages)
    archive_card = (
        f'  <a href="{info["page"].name}" class="wk-card"><div class="wr">'
        f'{info["range"]}</div>'
        f'<div class="wm">第{info["week"]}周 · {info["days"]}天</div>'
        f'<div class="wt">{escape(info["summary"])}</div></a>\n'
    )
    if f'href="{info["page"].name}"' not in archive:
        archive = replace_exact_once(archive, '<div class="weekly-grid">\n',
                                     '<div class="weekly-grid">\n' + archive_card,
                                     "weekly archive grid")
    archive, n = re.subn(r'(<span><strong>)\d+(</strong> 份周度总结</span>)',
                         rf'\g<1>{count}\2', archive, count=1)
    if n != 1:
        raise ValueError("weekly archive count missing")
    archive = re.sub(r'(<span><strong>)\d+(</strong> 周覆盖</span>)',
                     rf'\g<1>{count}\2', archive, count=1)

    archive_path.write_text(archive, encoding="utf-8")
    print(f"weekly published locally: {info['page'].name}; archive count {count}")


def sync_weekly_dry(page_path) -> int:
    """只报告会改什么，不写盘（W8 S4）。

    S7b 起只写归档索引一个文件；首页由 `build_home.py` 渲染，本脚本不再碰。
    """
    try:
        info = read_weekly_page(page_path)
    except (OSError, ValueError) as exc:
        print(f"[dry-run] 不会执行：{exc}")
        return 1

    weekly_pages = sorted(REVIEW_NOTES.glob("weekly-*.html"))
    archive_path = REVIEW_NOTES / "index.html"
    print(f"[dry-run] 周报页：{info['page'].name}")
    print(f"[dry-run] 会写入：{archive_path}（归档计数 {len(weekly_pages)} → "
          f"{len(weekly_pages) + 1}；不动 index.html）")
    print("[dry-run] 未写盘；去掉 --dry-run 后执行")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="把周报页登记进门户归档索引")
    parser.add_argument("page", nargs="?", help="review-notes/weekly-*.html")
    parser.add_argument("--page", dest="page_opt", default=None,
                        help="同上，写成参数形式")
    parser.add_argument("--root", default=str(PORTAL),
                        help="门户根目录（测试用）")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    global PORTAL, REVIEW_NOTES
    if args.root and args.root != str(PORTAL):
        PORTAL = Path(args.root)
        REVIEW_NOTES = PORTAL / "review-notes"
    page = args.page_opt or args.page
    if not page:
        print("usage: sync_weekly_review.py review-notes/weekly-YYYY-MM-DD_MM-DD.html")
        return 2
    if args.dry_run:
        return sync_weekly_dry(page)
    sync_weekly(page)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
