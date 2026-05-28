#!/usr/bin/env python3
"""Sync PnL + market data from bridge API → portal/index.html

Usage: python3 tools/sync_pnl_data.py
Default source is cloud Hermes via SSH, so local bridge is not required.
Use --source local only when intentionally syncing from a local bridge.
"""

import argparse, json, os, re, shlex, subprocess, sys, urllib.request
from datetime import datetime
from pathlib import Path

PORTAL = Path(__file__).resolve().parent.parent
DEFAULT_REMOTE = "agentuser@43.132.146.234"
DEFAULT_LOCAL_BASE = "http://127.0.0.1:8088"


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="同步 PnL + 市场快照到 portal/index.html")
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
        r = subprocess.run(
            ["ssh", self.remote, remote_cmd],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode != 0:
            detail = (r.stderr or r.stdout or "").strip()
            raise RuntimeError(f"cloud bridge fetch failed: {path}; {detail}")
        return json.loads(r.stdout)


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

    def index_card(name, price_key, change_key):
        price = li.get(price_key, "—")
        chg = str(li.get(change_key, "—") or "—")
        cls = trend_class(chg)
        return (
            f'<div class="market-card index-card {cls}">'
            f'<span>{name}</span><strong>{price}</strong><em>{chg}</em></div>'
        )

    def live_or_baseline_count(key):
        v = iw.get(key)
        bv = m.get(key)
        if v in (None, "", "—") or (v == 0 and bv not in (None, "", "—", 0)):
            return bv
        return v

    up_cnt, dn_cnt = li.get("上涨家数"), li.get("下跌家数")
    if up_cnt is not None and dn_cnt is not None:
        ratio_html = f"<b>{up_cnt}</b><small>/</small><b>{dn_cnt}</b>"
    else:
        ratio_html = str(m.get("涨跌比") or "—")

    zt = live_or_baseline_count("涨停家数")
    dt = live_or_baseline_count("跌停家数")
    emotion_val = round(up_cnt / (up_cnt + dn_cnt) * 100) if (up_cnt and dn_cnt and up_cnt + dn_cnt > 0) else None

    cards = [
        index_card("上证", "上证指数", "上证指数涨幅"),
        index_card("深证", "深证指数", "深证指数涨幅"),
        index_card("创业", "创业指数", "创业指数涨幅"),
        (
            '<div class="market-card neutral">'
            f'<span>成交额</span><strong>{li.get("上证指数成交额", "—")}</strong><em>上证口径</em></div>'
        ),
        (
            '<div class="market-card ratio">'
            f'<span>涨跌比</span><strong>{ratio_html}</strong><em>上涨 / 下跌</em></div>'
        ),
        (
            '<div class="market-card limit">'
            f'<span>涨跌停</span><strong><b>{zt or "—"}</b><small>/</small><b>{dt or "—"}</b></strong><em>涨停 / 跌停</em></div>'
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

    # ── Meta: 云端 production summary 是账户 SSOT；不再读本地 pnl.db ──
    summary = data.get("summary") or {}
    total_asset = summary.get("total_asset") or 0
    deposit = summary.get("total_deposit") or 200000
    data["meta"] = {"total_asset": total_asset, "total_deposit": deposit}

    # ── Market snapshot ──
    try:
        baseline = api.fetch("/api/baseline")
        live = api.fetch("/api/live/quotes")
        market_html = build_market_html(baseline, live)
    except Exception as e:
        print(f"FAIL market: {e}")
        market_html = '<span style="color:var(--text3);font-size:12px">云端 bridge 不可用</span>'

    # ── Embed into index.html ──
    target = PORTAL / "index.html"
    with open(target) as f:
        html = f.read()

    # PNL_DATA
    js_blob = f"<script>\nvar PNL_DATA = {json.dumps(data, ensure_ascii=False)};\n</script>"
    html = re.sub(r"(<!-- PNL_DATA_START -->).*?(<!-- PNL_DATA_END -->)", f"\\1\n{js_blob}\n  \\2", html, flags=re.DOTALL)

    # Market snapshot section: marker-based so homepage layout can change safely.
    new_snap = (
        f'<div id="market-snap">\n'
        f'  <div class="review-chips" style="margin-bottom:10px">'
        f'<span class="chip">更新于 {datetime.now():%m/%d %H:%M}</span>'
        f'<span class="chip">数据源 {source_label}</span></div>\n'
        f'  {market_html}\n'
        f'</div>'
    )
    html = replace_marker_block(
        html,
        "<!-- MARKET_SNAPSHOT_START -->",
        "<!-- MARKET_SNAPSHOT_END -->",
        new_snap,
    )

    with open(target, "w") as f:
        f.write(html)

    n = len(data.get("all_sh", {}).get("dates", []))
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] synced {n} PnL days + market snapshot from {source_label} → index.html")


if __name__ == "__main__":
    main()
