#!/usr/bin/env python3
"""Sync PnL from bridge API → portal/data/pnl.json（**不碰 index.html**）

Usage: python3 tools/sync_pnl_data.py
Default source is cloud Hermes via SSH, so local bridge is not required.
Use --source local only when intentionally syncing from a local bridge.
"""

import argparse, json, math, os, re, shlex, subprocess, sys, time, urllib.request
from datetime import datetime
from pathlib import Path

PORTAL = Path(__file__).resolve().parent.parent
# 审计回复 10 第二节第 12 条：本脚本只写这个数据文件，不再碰 index.html。
DATA_OUT = PORTAL / "data" / "pnl.json"
# 上一版的首页（1.0）只作为"旧入金本金/历史净值"的兜底来源读取，不再写入。
HISTORICAL_HOME = PORTAL / "v1" / "index.html"
DEFAULT_REMOTE = "agentuser@43.132.146.234"
DEFAULT_LOCAL_BASE = "http://127.0.0.1:8088"


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="同步 PnL 到 portal/data/pnl.json（不碰 index.html）")
    p.add_argument(
        "--source",
        choices=["cloud", "local"],
        default=os.environ.get("PORTAL_DATA_SOURCE", "cloud"),
        help="数据源：cloud=Hermes 云端生产；local=本地 bridge。默认 cloud。",
    )
    p.add_argument(
        "--remote",
        default=os.environ.get("PORTAL_REMOTE", DEFAULT_REMOTE),
        help="cloud 模式 SSH 目标，默认 agentuser@43.132.146.234。",
    )
    p.add_argument(
        "--base-url",
        default=os.environ.get("PORTAL_LOCAL_BASE", DEFAULT_LOCAL_BASE),
        help="local 模式 bridge 地址，默认 http://127.0.0.1:8088。",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="只抓数并报告将写入的内容，不改动 index.html。",
    )
    return p.parse_args(argv)


class BridgeAPI:
    def __init__(self, source="cloud", remote=DEFAULT_REMOTE, base_url=DEFAULT_LOCAL_BASE):
        self.source = source
        self.remote = remote
        self.base_url = base_url.rstrip("/")

    def fetch(self, path):
        if self.source == "local":
            return self._fetch_local(path)
        return self._fetch_cloud(path)

    def _fetch_local(self, path):
        with urllib.request.urlopen(f"{self.base_url}{path}", timeout=8) as resp:
            return json.loads(resp.read())

    def _fetch_cloud(self, path):
        url = f"http://127.0.0.1:8088{path}"
        remote_cmd = f"curl -fsS --max-time 8 {shlex.quote(url)}"
        for attempt in range(3):
            try:
                r = subprocess.run(
                    ["ssh", self.remote, remote_cmd],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
            except subprocess.TimeoutExpired as exc:
                detail = f"ssh timed out after {exc.timeout}s"
            else:
                if r.returncode == 0:
                    return json.loads(r.stdout)
                detail = (r.stderr or r.stdout or "").strip()
            if attempt < 2:
                time.sleep(attempt + 1)
        raise RuntimeError(f"cloud bridge fetch failed: {path}; {detail}")


def fetch(url):
    """Legacy helper retained for small one-off local reads."""
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


def build_market_html(baseline, live):
    """Generate compact homepage market snapshot HTML."""
    li = live.get("live_index", {})
    m = baseline.get("market", {})
    iw = live.get("iwencai", {})

    def parse_float(v):
        try:
            m = re.search(r"[+-]?\d+(?:\.\d+)?", str(v).replace(",", ""))
            return float(m.group(0)) if m else None
        except Exception:
            return None

    def trend_class(value):
        num = parse_float(value)
        if num is None:
            return "neutral"
        return "up" if num > 0 else "down" if num < 0 else "neutral"

    def present(v):
        return v not in (None, "", "—")

    def baseline_matches_live():
        live_sh = parse_float(li.get("上证指数"))
        baseline_sh = parse_float(m.get("上证指数"))
        if live_sh is None or baseline_sh is None:
            return True
        return abs(live_sh - baseline_sh) < 0.05

    def review_note_market():
        """当日复盘页里的 SSOT 市场事实（涨跌停、情绪值）。

        腾讯 live_index 的涨跌家数不刷新（A1），首页快照不再从它派生任何
        公开数字；涨跌停与情绪改取当日公开复盘页，与复盘页同源。
        """
        updated = str(li.get("_updated") or "")
        date = updated[:10] if re.match(r"\d{4}-\d{2}-\d{2}", updated) else ""
        if not date:
            return {}
        path = PORTAL / "review-notes" / f"{date}.html"
        if not path.exists():
            return {}
        text = path.read_text(encoding="utf-8", errors="ignore")
        counts: dict = {}
        match = re.search(r"(\d+)涨停\s*/\s*(\d+)跌停", text)
        if match:
            counts["涨停家数"] = int(match.group(1))
            counts["跌停家数"] = int(match.group(2))
        emotion = re.search(r"情绪\s*([\d.]+)\s*%", text)
        if emotion:
            counts["情绪值"] = float(emotion.group(1))
        return counts

    def index_card(name, price_key, change_key):
        price = li.get(price_key, "—")
        chg = str(li.get(change_key, "—") or "—")
        cls = trend_class(chg)
        return (
            f'<div class="market-card index-card {cls}">'
            f'<span>{name}</span><strong>{price}</strong><em>{chg}</em></div>'
        )

    review_counts = review_note_market()
    use_baseline_counts = baseline_matches_live()

    def live_or_fallback_count(key):
        v = iw.get(key)
        bv = m.get(key)
        if present(v) and not (v == 0 and present(review_counts.get(key))):
            return v
        if present(review_counts.get(key)):
            return review_counts.get(key)
        if use_baseline_counts and present(bv):
            return bv
        return None

    up_cnt, dn_cnt = li.get("上涨家数"), li.get("下跌家数")

    zt = live_or_fallback_count("涨停家数")
    dt = live_or_fallback_count("跌停家数")
    limit_note = (
        "云端口径"
        if present(iw.get("涨停家数")) or present(iw.get("跌停家数"))
        else "涨停 / 跌停"
    )
    # 情绪只来自复盘页的 SSOT 值；腾讯 live_index 的涨跌家数不刷新（A1），
    # 不再派生任何公开数字。
    emotion_val = review_counts.get("情绪值")

    cards = [
        index_card("上证", "上证指数", "上证指数涨幅"),
        index_card("深证", "深证指数", "深证指数涨幅"),
        index_card("创业", "创业指数", "创业指数涨幅"),
        (
            '<div class="market-card neutral">'
            f'<span>成交额</span><strong>{li.get("上证指数成交额", "—")}</strong><em>上证口径</em></div>'
        ),
        (
            '<div class="market-card limit">'
            f'<span>涨跌停</span><strong><b>{zt or "—"}</b><small>/</small><b>{dt or "—"}</b></strong><em>{limit_note}</em></div>'
        ),
        (
            '<div class="market-card neutral">'
            f'<span>情绪值</span><strong>{str(emotion_val) + "%" if emotion_val is not None else "—"}</strong><em>市场温度</em></div>'
        ),
    ]
    return '<div class="market-grid">\n  ' + "\n  ".join(cards) + "\n</div>"


def replace_marker_block(html, start_marker, end_marker, replacement):
    """Replace content between two HTML comments, failing clearly if absent."""
    pattern = rf"({re.escape(start_marker)}).*?({re.escape(end_marker)})"
    new_html, count = re.subn(
        pattern,
        lambda m: f"{m.group(1)}\n{replacement}\n          {m.group(2)}",
        html,
        flags=re.DOTALL,
    )
    if count != 1:
        raise RuntimeError(f"marker block not found or duplicated: {start_marker} ... {end_marker}")
    return new_html


def as_number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def extract_existing_pnl_data(html):
    m = re.search(r"var PNL_DATA = (\{.*?\});\s*</script>", html, flags=re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return {}


def extract_git_pnl_data():
    r = subprocess.run(
        ["git", "show", "HEAD:index.html"],
        cwd=PORTAL,
        capture_output=True,
        text=True,
        timeout=8,
    )
    if r.returncode != 0:
        return {}
    return extract_existing_pnl_data(r.stdout)


def latest_nav(data, summary):
    nav = as_number((summary or {}).get("last_nav"))
    if nav is not None:
        return nav

    navs = ((data or {}).get("all_sh") or {}).get("nav") or []
    for value in reversed(navs):
        nav = as_number(value)
        if nav is not None:
            return nav
    return None


def existing_meta_values(existing_data_list, key):
    values = []
    for existing_data in existing_data_list:
        meta = (existing_data or {}).get("meta") or {}
        value = as_number(meta.get(key))
        if value is not None:
            values.append(value)
    return values


def resolve_meta(data, existing_data_list):
    summary = (data or {}).get("summary") or {}
    if isinstance(existing_data_list, dict):
        existing_data_list = [existing_data_list]

    deposit = as_number(summary.get("total_deposit"))
    if deposit is None:
        deposit_candidates = existing_meta_values(existing_data_list, "total_deposit")
        deposit = next((v for v in deposit_candidates if v > 200000), None)
        if deposit is None:
            deposit = deposit_candidates[0] if deposit_candidates else 200000

    total_asset = as_number(summary.get("total_asset"))
    if total_asset is None:
        nav = latest_nav(data, summary)
        if nav is not None and deposit is not None:
            total_asset = round(deposit * nav, 2)
        else:
            asset_candidates = existing_meta_values(existing_data_list, "total_asset")
            total_asset = asset_candidates[0] if asset_candidates else 0

    return {"total_asset": total_asset, "total_deposit": deposit}


def sanitize_public_pnl_data(data):
    """Keep chart inputs while dropping account and runtime details from public HTML."""
    public = dict(data or {})
    summary = public.get("summary") or {}
    safe_summary_keys = {"last_nav", "last_date", "daily_count", "today_snapshots", "pnl_pct"}
    public["summary"] = {k: summary[k] for k in safe_summary_keys if k in summary}
    safe_series_keys = {
        "type",
        "data_date",
        "is_fallback",
        "labels",
        "dates",
        "portfolio",
        "benchmark",
        "position",
        "nav",
    }
    for key, value in list(public.items()):
        if key in {"summary", "meta"} or not isinstance(value, dict):
            continue
        public[key] = {k: value[k] for k in safe_series_keys if k in value}
    return public


def main(argv=None):
    args = parse_args(argv)
    api = BridgeAPI(source=args.source, remote=args.remote, base_url=args.base_url)
    source_label = f"cloud:{args.remote}" if args.source == "cloud" else f"local:{args.base_url}"

    # ── PnL data ──
    data = {}
    for per in ["today", "week", "month", "quarter", "year", "all"]:
        for idx in ["sh", "sz", "cy"]:
            try:
                data[f"{per}_{idx}"] = api.fetch(f"/api/pnl?range={per}&index={idx}")
            except Exception as e:
                print(f"FAIL PnL {per}_{idx}: {e}")
                sys.exit(1)

    try:
        data["summary"] = api.fetch("/api/pnl/summary")
    except Exception as e:
        print(f"FAIL summary: {e}")
        data["summary"] = {}

    # ── Market snapshot ──
    try:
        baseline = api.fetch("/api/baseline")
        live = api.fetch("/api/live/quotes")
        market_html = build_market_html(baseline, live)
    except Exception as e:
        print(f"FAIL market: {e}")
        market_html = '<span style="color:var(--text3);font-size:12px">云端 bridge 不可用</span>'

    # ── 只写数据文件，不碰 index.html（审计回复 10 第二节第 12 条）──
    # 首页整页由 build_home.py 渲染（sync_portal 的 ③）。这里如果再就地改
    # index.html，两个写入者会互相覆盖——2026-10-01 的定时同步就是这么
    # 在工作树里留下一份没人认领的改动。**取数与渲染分开**：本脚本只落
    # data/pnl.json，build_home 读它。
    data["meta"] = resolve_meta(data, [extract_existing_pnl_data(HISTORICAL_HOME),
                                       extract_git_pnl_data()])
    data = sanitize_public_pnl_data(data)

    n = len(data.get("all_sh", {}).get("dates", []))
    summary = data.get("summary") or {}
    payload = {
        "schema": "portal.pnl_data.v1",
        "source": source_label,
        "fetched_at": f"{datetime.now():%Y-%m-%d %H:%M}",
        "data": data,
    }

    if args.dry_run:
        print(
            f"[dry-run] 将写入 {DATA_OUT}：PNL_DATA {n} 天"
            f"（last_date={summary.get('last_date')}，last_nav={summary.get('last_nav')}）"
            f"，数据源 {source_label}"
        )
        return

    DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    DATA_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] synced {n} PnL days from {source_label} → {DATA_OUT.relative_to(PORTAL)}")


if __name__ == "__main__":
    main()
