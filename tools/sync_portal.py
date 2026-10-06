#!/usr/bin/env python3
"""Portal 同步唯一入口：首页数据 → 每日公开页 → 首页整页渲染。

Portal 有三条互不相干的生成链，顺序固定：

1. ``sync_pnl_data.py``    ``data/pnl.json`` 等数据文件（收益曲线、市场卡片；只写数据）
2. ``build_daily_page.py`` ``daily/<date>.html``（10 月起每个交易日一张公开页）
3. ``build_home.py``       整页渲染 ``index.html``（不再用正则就地改首页）

W8 S7a 起 ②③ 走上面这两个生成器；S7b（2026-10-05）把
``convert_review.py`` / ``convert_daily_note.py``（逐词替换脱敏、读复盘笔记
``### 公开稿``、正则就地改首页、两套重复模板）连同守着它们的测试一起删掉了。
≤2026-09-30 的第一阶段页面已冻结，不再重新生成。

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
``--allow-missing-reading``；4 复盘详情页失败；5 手记失败；6 隐私红线命中
（不推送，本次生成的页面不进入发布）。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
PORTAL = TOOLS.parent
REVIEW_ROOT = Path(
    "/Users/yimu/Documents/YouMingVault/10_⚡Now/01_💰弈沐资本/复盘笔记"
)
MARKET_WATCH_ROOT = Path(
    os.environ.get("MARKET_WATCH_ROOT") or PORTAL.parent / "Market_Watch"
)
# Vault 公开写作目录（W8 弈沐 10-01 定）：写作发布源，门户只读它的索引。
WRITING_ROOT = Path(
    os.environ.get("PORTAL_WRITING_ROOT")
    or "/Users/yimu/Documents/YouMingVault/10_⚡Now/01_💰弈沐资本/公开写作"
)
WRITING_INDEX = PORTAL / "data" / "writing-index.json"
PNL_DATA_FILE = PORTAL / "data" / "pnl.json"
# 第一阶段（2026-03-23 至 09-30）冻结：老的复盘页/手记页不再重新生成，
# 与 build_daily_page.PHASE2_START 用同一个日子。
PHASE2_START = "2026-10-01"


def find_review_note(day: str) -> Path | None:
    """按交易日定位 Vault 里的 ReviewNote。

    Vault 里有**两种**命名写法：W40 之前是 ``2026_9_30_Wednesday_…``（不补零），
    W41 起是 ``2026_10_08_Thursday_…``（补零）。以前只按不补零拼 glob，
    于是 10-08 这天根本找不到笔记、发布链会静默跳过——单看"同步成功"发现不了。
    两种都试，按修改时间取最新的那份。
    """
    year, month, daynum = (int(part) for part in day.split("-"))
    patterns = [
        f"W*_第*周/{year}_{month}_{daynum}_*ReviewNote.md",
        f"W*_第*周/{year}_{month:02d}_{daynum:02d}_*ReviewNote.md",
    ]
    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(p for p in REVIEW_ROOT.glob(pattern) if p not in matches)
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


class ReadingDiscoveryError(ValueError):
    """An indexed projection cannot be safely consumed."""


def find_reading_sidecar(note: Path, day: str) -> Path | None:
    """Return the optional sidecar bound to the resolved ReviewNote bytes."""
    try:
        note_bytes = note.read_bytes()
        source_path = note
        if re.search(rb"(?m)^daily_bundle_ref\s*:\s*\S", note_bytes):
            try:
                from daily_bundle_input import resolve_bundle_reading
            except ImportError:
                return None
            try:
                source = resolve_bundle_reading(note)
            except (OSError, UnicodeError, ValueError):
                return None
            source_path = Path(source.get("review_path") or note)
        revision = hashlib.sha256(source_path.read_bytes()).hexdigest()
    except OSError:
        return None
    # Contract §6: version selection is explicit (via the index), never by
    # guessing the legacy file name.  Fall back to the bare legacy product only
    # when no index exists yet.
    folder = (
        MARKET_WATCH_ROOT / "artifacts" / "review-reading" / day[:4] / day
    )
    legacy = folder / f"{revision}.review_reading.v1.json"
    index_file = folder / "_index.json"
    if not index_file.exists() and not index_file.is_symlink():
        return legacy if legacy.is_file() else None
    try:
        import importlib.util
        import pathlib as _pl
        module_path = (
            _pl.Path(__file__).resolve().parents[2] / "Market_Watch"
            / "scripts" / "review_reading_index.py"
        )
        spec = importlib.util.spec_from_file_location("_sidecar_index", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        version = module.resolve_current_version(MARKET_WATCH_ROOT, day, revision)
    except Exception as exc:
        raise ReadingDiscoveryError('review_reading_index_unavailable') from exc
    candidate = MARKET_WATCH_ROOT / version["path"]
    if candidate.is_symlink() or not candidate.is_file():
        raise ReadingDiscoveryError('review_reading_index_target_missing')
    try:
        candidate.resolve(strict=True).relative_to(folder.resolve())
    except ValueError as exc:
        raise ReadingDiscoveryError('review_reading_index_target_outside_day') from exc
    return candidate


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


def daily_public_page(day: str) -> Path:
    """10 月起每个交易日一张公开页（复盘页与手记页合并成这一种）。"""
    return PORTAL / "daily" / f"{day}.html"


def home_page() -> Path:
    return PORTAL / "index.html"


def load_review_index_fields(day: str) -> dict:
    """进程内调 Market_Watch 的 ``review_index_fields`` 取封存市场指标。

    门户**不解析复盘笔记正文**——它只要那四个数和它们是哪天的。指标自带 date
    （审计回复 8 第 9 条），门户那侧还有 ``--data-date`` 作第二道校验。

    这里刻意**不shell 调 CLI**：``export_daily_bundle.py --print-review-index``
    在 W3 改成 daily bundle 导出时已被删（现在只收
    ``--review/--market-watch-root/--dashboard-root/--out-root``），
    留着调法会让 ``sync_portal`` 在②a 直接退出码 2（W9 S9 实测）。

    ★ 用**普通 import** 而不是 ``spec_from_file_location``：该模块顶层
    ``from scripts.export_decision_plan import ...``，别名加载时它所在仓的
    ``scripts`` 包没被注册，import 失败报 ``No module named
    'scripts.export_decision_plan'``（W9 S9 确认跑实测）。仓根必须在
    ``sys.path`` 且``scripts`` 解析到那个仓——所以先插路径再 import。
    """
    root = str(MARKET_WATCH_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    scripts_pkg = sys.modules.get("scripts")
    if scripts_pkg is not None:
        paths = list(getattr(scripts_pkg, "__path__", []) or [])
        want = str(MARKET_WATCH_ROOT / "scripts")
        if want not in paths:
            # 命名空间包已缓存：把目标仓的 scripts 目录补进去，别动已有项
            try:
                scripts_pkg.__path__.append(want)
            except AttributeError:
                pass
    from scripts import export_daily_bundle as module

    return module.review_index_fields(day)


def review_index_json(day: str, out_path: Path) -> list[str]:
    """取该交易日的封存市场指标（review_index_fields），落到 out_path。"""
    return []


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
    capture_stdout: bool = False,
    no_dry_run_flag: bool = False,
) -> bool:
    """跑一个子步骤。

    ``supports_dry_run=False`` 的步骤在预演时只打印它将做什么，不执行——
    预演绝不能写盘。``capture_stdout=True`` 时不返回 bool，而是返回子进程的
    stdout 文本（供下一步把它落成 JSON）；失败返回空串。
    """
    print(f"── {label} ──", flush=True)
    if dry_run and not supports_dry_run:
        print(f"[dry-run] {dry_run_note or ' '.join(argv)}", flush=True)
        return "" if capture_stdout else True
    command = [sys.executable, *argv]
    if dry_run and "--dry-run" not in command and not no_dry_run_flag:
        command.append("--dry-run")
    if capture_stdout:
        completed = subprocess.run(
            command, cwd=str(PORTAL), capture_output=True, text=True
        )
        if completed.returncode != 0:
            print(f"FAIL {label}（退出码 {completed.returncode}）", flush=True)
            if completed.stderr:
                print(completed.stderr.strip()[-400:], flush=True)
            return ""
        return completed.stdout
    completed = subprocess.run(command, cwd=str(PORTAL))
    if completed.returncode != 0:
        print(f"FAIL {label}（退出码 {completed.returncode}）", flush=True)
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Portal 同步：首页数据 → 每日公开页 → 整页首页"
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

    # 阅读投影的可用性仍然要查（复盘终稿没封存就不能出页），但新链不消费它——
    # 指标走封存原件、正文走已发布写作。老脚本用 --reading-sidecar，S7b 才删。
    try:
        find_reading_sidecar(note, target_day)
    except ReadingDiscoveryError as exc:
        print(f"FAIL 阅读投影不可用: {exc}", flush=True)
        return 4

    # ② 每日公开页（W8 S7a）：四个指标取自封存原件，正文只取已发布的「每日/」写作。
    # 不解析复盘笔记、不逐词脱敏——S7b 已把那条老路径连同它的函数与测试删掉。
    public_page = daily_public_page(target_day)
    index_json = PORTAL / "out" / f"review-index-{target_day}.json"
    # 进程内调函数而非 shell 调 CLI：旧的 `--print-review-index` 已被删。
    try:
        fetch_index = json.dumps(
            load_review_index_fields(target_day), ensure_ascii=False, indent=2
        )
        print("②a 取封存市场指标（review_index_fields）[ok]")
    except Exception as exc:
        print(f"FAIL ②a 取封存市场指标（review_index_fields）：{exc}", flush=True)
        return 2
    # 预演不往仓库里写盘，但 ②b 要读这份指标，所以落到**仓库外的临时文件**，
    # 用完即删——预演不能留下任何痕迹，也不能因为"没写"就让下一步失败。
    scratch: Path | None = None
    if args.dry_run:
        scratch = Path(tempfile.mkdtemp(prefix="portal-sync-dry-")) / "review-index.json"
        scratch.write_text(fetch_index, encoding="utf-8")
        index_json = scratch
    else:
        index_json.parent.mkdir(parents=True, exist_ok=True)
        index_json.write_text(fetch_index, encoding="utf-8")
    # 第一阶段（≤2026-09-30）的页面已冻结，不再重新生成——对冻结日期来说
    # "不出页" 是正确行为，不是失败。跳过要说清楚，不能让人以为漏跑了。
    phase1_frozen = target_day < PHASE2_START
    if phase1_frozen:
        print(f"[skip] {target_day} 属第一阶段，页面已冻结，不重新生成"
              "（W8 弈沐 10-01 决定）")
    if not args.skip_review and not phase1_frozen:
        daily_argv = [
            str(TOOLS / "build_daily_page.py"), "build",
            "--day", target_day,
            "--data-date", target_day,
            "--index", str(index_json),
            "--writing-index", str(WRITING_INDEX),
            "--writing-root", str(WRITING_ROOT),
            "--out", str(public_page.parent),
        ]
        if not run_step(
            f"②b 每日公开页（{target_day}）", daily_argv, args.dry_run,
        ):
            print("已完成: " + " → ".join(done))
            return 4
        if not args.dry_run and not public_page.is_file():
            print(f"FAIL 每日公开页未生成: {display(public_page)}", flush=True)
            print("已完成: " + " → ".join(done))
            return 4
        done.append("② 每日公开页")
    if scratch is not None:
        shutil.rmtree(scratch.parent, ignore_errors=True)

    # ③ 首页整页渲染（W8 S2/S7a）：不再用正则就地改首页，也就没有「谁先谁后
    # 都行」的默契——整页只有一个渲染器（public约定：业绩只算一处）。
    home_argv = [
        str(TOOLS / "build_home.py"),
        "--pnl-from", str(PNL_DATA_FILE),
        "--writing-index", str(WRITING_INDEX),
        "--out", str(home_page()),
    ]
    # build_home 没有 --dry-run（它只做渲染，没有 --check 之外的预演模式），
    # 预演时只打印它将做什么。
    if not run_step("③ 首页整页渲染（build_home）", home_argv, args.dry_run,
                    supports_dry_run=False,
                    dry_run_note=f"将整页渲染 {display(home_page())}（build_home 无 --dry-run）"):
        print("已完成: " + " → ".join(done))
        return 5
    done.append("③ 首页")

    # ④ 隐私红线门禁（2026-09-28）：只检查本次生成/修改的文件。
    # 只查本次真正改动的页面：第一阶段（≤09-30）的页面已冻结，不再重新生成。
    redline_files = [home_page(), public_page]
    existing = [path for path in redline_files if path.is_file()]
    if not run_step(
        "④ 隐私红线检查（本次生成/修改的页面）",
        [str(TOOLS / "portal_check.py"), "--redline",
         *([] if args.source is None else ["--redline-source", args.source]),
         "--review-note", str(note),
         *[str(path) for path in existing]],
        args.dry_run,
        supports_dry_run=False,
        dry_run_note=(
            f"将对 {len(existing)} 个本次页面跑隐私红线门禁"
            "（portal_check.py 无 --dry-run）"
        ),
    ):
        print("已完成: " + " → ".join(done))
        print("FAIL 隐私红线命中：本次页面不推送", flush=True)
        return 6
    done.append("④ 隐私红线")

    print("完成: " + " → ".join(done))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
