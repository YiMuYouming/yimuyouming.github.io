#!/usr/bin/env python3
"""Portal 同步唯一入口：首页数据 → 复盘详情页 → 每日市场手记。

Portal 有三条互不相干的生成链，顺序固定：

1. ``sync_pnl_data.py``   首页 ``PNL_DATA`` + ``MARKET_SNAPSHOT``（收益曲线、市场卡片）
2. ``convert_review.py``  ``review-notes/<date>.html`` + 复盘索引 + 首页复盘区块
3. ``convert_daily_note.py`` ``daily-notes/<date>.html`` + 手记索引 + 首页手记卡片

顺序理由：首页数据承载「当日账户事实」，后面两条的正文与卡片都引用它，先刷事实
再出阅读层，同一次同步内才不会出现两套事实。2 与 3 都写 ``index.html``，用固定
次序代替「谁先谁后都行」的默契。

这个入口存在的理由是漏过两次：收益曲线漏同步过一次（手记已到 9/15 而收益曲线停
在 9/14），复盘详情页漏过一次（9/15 手记已上线，而首页「阅读最新复盘」仍指向
9/14）。两条链当时都没有统一入口，谁都不报错。

用法::

    python3 tools/sync_portal.py                      # 今天，云端数据源
    python3 tools/sync_portal.py --date 2026-09-15
    python3 tools/sync_portal.py --dry-run            # 三步都只预演
    python3 tools/sync_portal.py --source local       # 走本地 8088
    python3 tools/sync_portal.py --skip-review        # 不出复盘详情页
    python3 tools/sync_portal.py --skip-reading       # 只到复盘详情页

退出码：0 成功；1 参数错；2 首页数据失败；3 缺 ReviewNote 且未加
``--allow-missing-reading``；4 复盘详情页失败；5 手记失败。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
PORTAL = TOOLS.parent
REVIEW_ROOT = Path(
    "/Users/yimu/Documents/YouMingVault/10_⚡Now/01_💰弈沐资本/复盘笔记"
)


def find_review_note(day: str) -> Path | None:
    """按交易日定位 Vault 里的 ReviewNote（文件名形如 2026_9_15_Tuesday_...）。"""
    year, month, daynum = (int(part) for part in day.split("-"))
    stamp = f"{year}_{month}_{daynum}_"
    matches = sorted(REVIEW_ROOT.glob(f"W*_第*周/{stamp}*ReviewNote.md"))
    return matches[0] if matches else None


def read_pnl_last_date() -> str | None:
    """回读首页内嵌 PNL_DATA 的最新日期，用于确认第一步真的生效。"""
    index = PORTAL / "index.html"
    if not index.is_file():
        return None
    match = re.search(
        r"var PNL_DATA = (\{.*?\});", index.read_text(encoding="utf-8"), re.S
    )
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return None
    return (data.get("summary") or {}).get("last_date")


def review_page(day: str) -> Path:
    return PORTAL / "review-notes" / f"{day}.html"


def daily_note_page(day: str) -> Path:
    return PORTAL / "daily-notes" / f"{day}.html"


def display(path: Path) -> str:
    """日志里优先用仓库内相对路径，落在仓库外时退回绝对路径。"""
    try:
        return str(path.relative_to(PORTAL))
    except ValueError:
        return str(path)


def run_step(
    label: str,
    argv: list[str],
    dry_run: bool,
    *,
    supports_dry_run: bool = True,
    dry_run_note: str | None = None,
) -> bool:
    """跑一个子步骤。

    ``supports_dry_run=False`` 的步骤（``convert_review.py`` 没有 ``--dry-run``）
    在预演时只打印它将做什么，不执行——预演绝不能写盘。
    """
    print(f"── {label} ──", flush=True)
    if dry_run and not supports_dry_run:
        print(f"[dry-run] {dry_run_note or ' '.join(argv)}", flush=True)
        return True
    command = [sys.executable, *argv]
    if dry_run and "--dry-run" not in command:
        command.append("--dry-run")
    completed = subprocess.run(command, cwd=str(PORTAL))
    if completed.returncode != 0:
        print(f"FAIL {label}（退出码 {completed.returncode}）", flush=True)
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Portal 同步：首页数据 → 复盘详情页 → 每日市场手记"
    )
    parser.add_argument("--date", help="目标交易日 YYYY-MM-DD，默认今天")
    parser.add_argument(
        "--dry-run", action="store_true", help="三步都只预演，不落盘"
    )
    parser.add_argument(
        "--source",
        choices=["cloud", "local"],
        help="首页数据源；不给则沿用 sync_pnl_data.py 的默认值",
    )
    parser.add_argument(
        "--skip-review", action="store_true", help="不出复盘详情页"
    )
    parser.add_argument(
        "--skip-reading", action="store_true", help="只同步首页数据"
    )
    parser.add_argument(
        "--allow-missing-reading",
        action="store_true",
        help="当日还没有 ReviewNote 时不视为失败（定时任务用）",
    )
    args = parser.parse_args(argv)

    target_day = args.date or date.today().isoformat()
    try:
        datetime.strptime(target_day, "%Y-%m-%d")
    except ValueError:
        print(f"FAIL --date 需为 YYYY-MM-DD: {target_day}")
        return 1

    done: list[str] = []

    # 第一步必须是首页数据：收益曲线是当日账户事实，后面两条正文都引用它。
    pnl_argv = [str(TOOLS / "sync_pnl_data.py")]
    if args.source:
        pnl_argv += ["--source", args.source]
    if not run_step("① 首页数据（收益曲线 + 市场快照）", pnl_argv, args.dry_run):
        return 2
    done.append("① 首页数据")

    if not args.dry_run:
        last_date = read_pnl_last_date()
        if last_date != target_day:
            print(
                f"WARN 首页数据 last_date={last_date}，目标日 {target_day}"
                "；云端当日 PnL 可能尚未就绪",
                flush=True,
            )

    if args.skip_reading:
        print("跳过复盘详情页与手记（--skip-reading）")
        print("完成: " + " → ".join(done))
        return 0

    note = find_review_note(target_day)
    if note is None:
        print(f"未找到 {target_day} 的 ReviewNote，跳过复盘详情页与手记")
        print("完成: " + " → ".join(done))
        return 0 if args.allow_missing_reading else 3

    if not args.skip_review:
        page = review_page(target_day)
        if not run_step(
            f"② 复盘详情页（{note.name}）",
            [str(TOOLS / "convert_review.py"), str(note)],
            args.dry_run,
            supports_dry_run=False,
            dry_run_note=(
                f"将生成 {display(page)}，并更新 review-notes/index.html "
                "与首页复盘区块（该脚本无 --dry-run）"
            ),
        ):
            print("已完成: " + " → ".join(done))
            return 4
        # 子进程退出码不够：页面没落盘就等于这一步没做。
        if not args.dry_run and not page.is_file():
            print(f"FAIL 复盘详情页未生成: {display(page)}", flush=True)
            print("已完成: " + " → ".join(done))
            return 4
        done.append("② 复盘详情页")

    if not run_step(
        f"③ 每日市场手记（{note.name}）",
        [str(TOOLS / "convert_daily_note.py"), str(note)],
        args.dry_run,
    ):
        print("已完成: " + " → ".join(done))
        return 5
    if not args.dry_run and not daily_note_page(target_day).is_file():
        print(
            f"FAIL 手记未生成: {display(daily_note_page(target_day))}", flush=True
        )
        print("已完成: " + " → ".join(done))
        return 5
    done.append("③ 每日市场手记")

    print("完成: " + " → ".join(done))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
