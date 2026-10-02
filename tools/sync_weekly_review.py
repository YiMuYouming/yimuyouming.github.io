#!/usr/bin/env python3
"""Publish a curated weekly HTML page into the Portal home and archive indexes.

The weekly page is editorially reviewed before this script runs. Daily Markdown
converters cannot safely infer its public narrative or privacy boundary.
"""

from pathlib import Path
from html import escape
import re
import sys

from convert_review import (
    PORTAL,
    REVIEW_NOTES,
    build_period_review_card,
    extract_recent_daily_cards,
    rebuild_recent_review_timeline,
)


def replace_exact_once(content, old, new, label):
    count = content.count(old)
    if count != 1:
        raise ValueError(f"{label}: expected one match, got {count}")
    return content.replace(old, new, 1)


def sync_weekly(page_path):
    page_path = Path(page_path).resolve()
    if page_path.parent != REVIEW_NOTES.resolve() or not re.fullmatch(
        r"weekly-\d{4}-\d{2}-\d{2}_\d{2}-\d{2}\.html", page_path.name
    ):
        raise ValueError("expected a weekly HTML file in review-notes/")
    if not page_path.is_file():
        raise FileNotFoundError(page_path)
    card = build_period_review_card(page_path)
    if not card:
        raise ValueError("weekly page cannot form a homepage card")

    home_path = PORTAL / "index.html"
    archive_path = REVIEW_NOTES / "index.html"
    home = home_path.read_text(encoding="utf-8")
    archive = archive_path.read_text(encoding="utf-8")

    # Both counters derive from the same archive listing, avoiding drift.
    weekly_pages = sorted(REVIEW_NOTES.glob("weekly-*.html"))
    count = len(weekly_pages)
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
    archive_card = (
        f'  <a href="{page_path.name}" class="wk-card"><div class="wr">'
        f'{int(sm)}/{int(sd)} – {int(em)}/{int(ed)}</div>'
        f'<div class="wm">第{int(week.group(1))}周 · {days.group(1)}天</div>'
        f'<div class="wt">{escape(summary.group(1))}</div></a>\n'
    )
    if f'href="{page_path.name}"' not in archive:
        archive = replace_exact_once(archive, '<div class="weekly-grid">\n',
                                     '<div class="weekly-grid">\n' + archive_card, "weekly archive grid")
    archive, n = re.subn(r'(<span><strong>)\d+(</strong> 份周度总结</span>)',
                         rf'\g<1>{count}\2', archive, count=1)
    if n != 1:
        raise ValueError("weekly archive count missing")
    archive = re.sub(r'(<span><strong>)\d+(</strong> 周覆盖</span>)',
                     rf'\g<1>{count}\2', archive, count=1)

    home, n = re.subn(r'(<div class="archive-item"><span>周报归档</span><strong>)\d+(</strong><em>篇</em></div>)',
                      rf'\g<1>{count}\2', home, count=1)
    if n != 1:
        raise ValueError("home archive weekly count missing")
    home, n = re.subn(r'(<div class="review-stat"><span>周报归档</span><strong>)\d+(</strong><em>篇</em></div>)',
                      rf'\g<1>{count}\2', home, count=1)
    if n != 1:
        raise ValueError("home review weekly count missing")
    home, n = re.subn(r'(<a class="workspace-card" id="workspace-weekly-review" href="review-notes/)weekly-[^"]+("?)',
                      rf'\g<1>{page_path.name}\2', home, count=1)
    if n != 1:
        raise ValueError("home latest weekly link missing")
    daily_cards = extract_recent_daily_cards(home)
    if not daily_cards:
        raise ValueError("home recent daily cards missing")
    newest_daily = max(daily_cards, key=lambda c: c["date"])
    # Refresh this week's card from its source while preserving hand-edited
    # titles on other existing period cards.
    home = re.sub(
        rf'<a id="{re.escape(card["id"])}".*?</a>\s*',
        '', home, count=1, flags=re.S,
    )
    home = rebuild_recent_review_timeline(home, newest_daily["date"], newest_daily["html"])
    if card["id"] not in home:
        raise ValueError("new weekly card missing from recent timeline")

    archive_path.write_text(archive, encoding="utf-8")
    home_path.write_text(home, encoding="utf-8")
    print(f"weekly published locally: {page_path.name}; archive count {count}")


def sync_weekly_dry(page_path) -> int:
    """只报告会改什么，不写盘（W8 S4）。

    以前这个脚本只能直接写盘；跑之前看不出它会动 index.html 的哪几行。现在
    dry-run 把改动逐条列出来，确认后再真跑。
    """
    import argparse

    page_path = Path(page_path).resolve()
    try:
        if page_path.parent != REVIEW_NOTES.resolve() or not re.fullmatch(
            r"weekly-\d{4}-\d{2}-\d{2}_\d{2}-\d{2}\.html", page_path.name
        ):
            raise ValueError("expected a weekly HTML file in review-notes/")
        if not page_path.is_file():
            raise FileNotFoundError(page_path)
        card = build_period_review_card(page_path)
        if not card:
            raise ValueError("weekly page cannot form a homepage card")
    except (OSError, ValueError) as exc:
        print(f"[dry-run] 不会执行：{exc}")
        return 1

    weekly_pages = sorted(REVIEW_NOTES.glob("weekly-*.html"))
    home_path = PORTAL / "index.html"
    archive_path = REVIEW_NOTES / "index.html"
    print(f"[dry-run] 周报页：{page_path.name}")
    print(f"[dry-run] 会写入：{home_path}（替换周榜卡片 {card['id']}，重建近期时间线）")
    print(f"[dry-run] 会写入：{archive_path}（归档计数 {len(weekly_pages)} → "
          f"{len(weekly_pages) + 1}）")
    print("[dry-run] 未写盘；去掉 --dry-run 后执行")
    return 0


def build_parser() -> argparse.ArgumentParser:
    import argparse

    parser = argparse.ArgumentParser(description="把周报页发布进门户索引")
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
