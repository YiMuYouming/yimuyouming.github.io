#!/usr/bin/env python3
"""每日交付检查（H12，包2d）：数据页更新不等于手记和界面更新，三项分开核，任一不符报红。

1. 收益数据日期＝当天（data/pnl.json 的 summary.last_date 与 today_sh.data_date）；
2. 首页最新随笔日期＝当天（首页「每日手记」第一行与 WRITING_INDEX 里已发布的最新一篇）；
3. UI 版本＝已部署版本（本地 index.html 的 sha256 前 12 位，与公网实际返回的字节比；对不上＝没部署）。
只读：不写 Portal 文件、不提交、不推送。

用法：python3 tools/delivery_check.py --date YYYY-MM-DD [--url https://yimuyouming.github.io/]
退出码 0＝三项都绿，1＝有红。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Callable

PORTAL = Path(__file__).resolve().parent.parent
DEFAULT_URL = "https://yimuyouming.github.io/"


def _result(name: str, ok: bool, detail: str, **extra) -> dict:
    return {"name": name, "ok": ok, "detail": detail, **extra}


def ui_version(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:12]


def check_pnl_date(root: Path, day: str) -> dict:
    try:
        data = json.loads((Path(root) / "data" / "pnl.json").read_text(encoding="utf-8"))["data"]
        last = str((data.get("summary") or {}).get("last_date") or "")
        point = str((data.get("today_sh") or {}).get("data_date") or "")
    except (OSError, ValueError, KeyError, AttributeError):
        return _result("收益数据日期", False, "data/pnl.json 读不到或结构不对")
    ok = last == day and point == day
    return _result("收益数据日期", ok, f"期望 {day}；summary.last_date={last or '无'}，today_sh.data_date={point or '无'}")


def _latest_published_diary(html: str) -> str:
    match = re.search(r"var WRITING_INDEX = (\{.*?\});</script>", html, re.S)
    if not match:
        return ""
    try:
        entries = json.loads(match.group(1)).get("entries") or []
    except ValueError:
        return ""
    dates = [str(e.get("date")) for e in entries if e.get("kind") == "daily" and e.get("status") == "published"]
    return max(dates) if dates else ""


def check_latest_diary(root: Path, day: str) -> dict:
    try:
        html = (Path(root) / "index.html").read_text(encoding="utf-8")
    except OSError:
        return _result("首页最新随笔日期", False, "index.html 读不到")
    row = re.search(r'<h3>每日手记</h3>.*?<span class="writing-date">(\d{4}-\d{2}-\d{2})</span>', html, re.S)
    shown = row.group(1) if row else ""
    published = _latest_published_diary(html)
    ok = shown == day and published == day
    return _result("首页最新随笔日期", ok,
                   f"期望 {day}；首页第一行={shown or '无'}，已发布最新一篇={published or '无'}")


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=20) as response:  # noqa: S310 - 固定的公网站点
        return response.read()


def check_ui_version(root: Path, fetch: Callable[[str], bytes] = _fetch, url: str = DEFAULT_URL) -> dict:
    try:
        local = ui_version((Path(root) / "index.html").read_bytes())
    except OSError:
        return _result("UI版本", False, "本地 index.html 读不到")
    try:
        deployed = ui_version(fetch(url))
    except Exception as exc:  # 读不到公网也报红，不当作一致
        return _result("UI版本", False, f"公网 {url} 读不到：{type(exc).__name__}", local=local)
    ok = local == deployed
    return _result("UI版本", ok, f"本地 {local}，公网 {deployed}" + ("" if ok else "：本地界面未部署"),
                   local=local, deployed=deployed)


def run(root: Path, day: str, fetch: Callable[[str], bytes] = _fetch, url: str = DEFAULT_URL):
    results = [check_pnl_date(root, day), check_latest_diary(root, day), check_ui_version(root, fetch, url)]
    return results, (0 if all(r["ok"] for r in results) else 1)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Portal 每日交付检查（只读）")
    parser.add_argument("--date", required=True)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--root", type=Path, default=PORTAL)
    args = parser.parse_args(argv)
    results, code = run(args.root, args.date, url=args.url)
    for item in results:
        print(("[绿] " if item["ok"] else "[红] ") + f"{item['name']}：{item['detail']}")
    print("交付检查通过" if code == 0 else "交付检查有红：不得说「门户同步完成」")
    return code


if __name__ == "__main__":
    sys.exit(main())
