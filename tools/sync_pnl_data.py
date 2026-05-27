#!/usr/bin/env python3
"""Sync PnL + market data from bridge API → portal/index.html

Usage: python3 tools/sync_pnl_data.py
Bridge must be running on localhost:8088.
"""

import json, re, sys, urllib.request, sqlite3
from datetime import datetime
from pathlib import Path

PORTAL = Path(__file__).resolve().parent.parent


def fetch(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


def build_market_html(baseline, live):
    """Generate W04 market snapshot HTML (ported from market-overview.js render())."""
    li = live.get("live_index", {})
    m = baseline.get("market", {})
    iw = live.get("iwencai", {})
    sentiment = baseline.get("sentiment", {}) or {}
    sentiment_close = (baseline.get("sentiment_nodes", {}) or {}).get("收盘", {}) or {}
    nb = live.get("northbound", {}) or {}
    br = live.get("breadth", {}) or {}
    yb = baseline.get("yesterday_baseline", {}) or {}

    h = '<div style="display:flex;flex-direction:column;gap:6px">\n'

    def parse_float(v):
        try:
            m = re.search(r"[+-]?\d+(?:\.\d+)?", str(v).replace(",", ""))
            return float(m.group(0)) if m else None
        except Exception:
            return None

    def index_point_change(price, pct):
        price_num = parse_float(price)
        pct_num = parse_float(pct)
        if price_num is None or pct_num is None or pct_num <= -100:
            return ""
        prev_close = price_num / (1 + pct_num / 100)
        point = price_num - prev_close
        return f"{point:+.2f}点"

    # Row 1: 三大指数
    h += '<div style="display:flex;gap:6px">\n'
    for name, pk, ck in [("上证", "上证指数", "上证指数涨幅"), ("深证", "深证指数", "深证指数涨幅"), ("创业", "创业指数", "创业指数涨幅")]:
        price = li.get(pk, "—")
        chg = str(li.get(ck, "—"))
        d_ = "up" if chg.startswith("+") else "down" if chg.startswith("-") else ""
        pct = parse_float(chg) if chg not in ("—", "") else 0
        pct = pct if pct is not None else 0
        arrow = "▲" if pct > 0 else "▼" if pct < 0 else "—"
        c = "#DC2626" if d_ == "up" else "#059669" if d_ == "down" else ""
        point = index_point_change(price, chg)
        verdict = f"{arrow} {point} · {chg}" if point else f"{arrow} {chg}"
        h += f'<div class="kpi-card" style="flex:1;padding:8px 10px;background:var(--bg2);border:1px solid var(--border);border-radius:10px;text-align:center"><div class="kpi-label" style="font-size:10px;color:var(--text3);margin-bottom:2px">{name}</div><div class="kpi-value {d_}" style="font-size:20px;font-weight:700;color:{c}">{price}</div><div class="kpi-verdict {d_}" style="font-size:12px;font-weight:600;color:{c}">{verdict}</div></div>\n'
    h += "</div>\n"

    # Row 2: 成交额/涨跌比/振幅/涨跌停
    amt = li.get("上证指数成交额", "—")
    amtDiff = str(li.get("上证成交额差", "") or "")
    amtPct = str(li.get("上证成交额差百分比", "") or "")
    amtDir = "up" if amtDiff.startswith("+") else "down" if amtDiff.startswith("-") else ""
    ac = "#DC2626" if amtDir == "up" else "#059669" if amtDir == "down" else ""
    upCnt, dnCnt = li.get("上涨家数"), li.get("下跌家数")
    udHtml = f'<span style="color:#DC2626">{upCnt}</span>/<span style="color:#059669">{dnCnt}</span>' if (upCnt is not None and dnCnt is not None) else (m.get("涨跌比") or "—")
    amp = li.get("上证指数振幅", "—")
    def live_or_baseline_count(key):
        v = iw.get(key)
        bv = m.get(key)
        if v in (None, "", "—") or (v == 0 and bv not in (None, "", "—", 0)):
            return bv
        return v

    zt = live_or_baseline_count("涨停家数")
    dt = live_or_baseline_count("跌停家数")

    h += '<div style="display:flex;gap:6px">\n'
    h += f'<div class="kpi-card" style="flex:1;padding:6px 8px;background:var(--bg2);border:1px solid var(--border);border-radius:10px;text-align:center"><div class="kpi-label" style="font-size:10px;color:var(--text3);margin-bottom:2px">成交额</div><div class="kpi-value" style="font-size:15px;font-weight:700">{amt}</div>'
    if amtPct: h += f'<div class="kpi-verdict" style="font-size:11px;color:{ac}">较昨日此时 {amtPct}</div>'
    h += "</div>\n"
    h += f'<div class="kpi-card" style="flex:1;padding:6px 8px;background:var(--bg2);border:1px solid var(--border);border-radius:10px;text-align:center"><div class="kpi-label" style="font-size:10px;color:var(--text3);margin-bottom:2px">涨跌比</div><div class="kpi-value" style="font-size:15px;font-weight:700">{udHtml}</div></div>\n'
    h += f'<div class="kpi-card" style="flex:1;padding:6px 8px;background:var(--bg2);border:1px solid var(--border);border-radius:10px;text-align:center"><div class="kpi-label" style="font-size:10px;color:var(--text3);margin-bottom:2px">振幅</div><div class="kpi-value" style="font-size:15px;font-weight:700;color:var(--accent)">{amp}</div></div>\n'
    h += f'<div class="kpi-card" style="flex:1;padding:6px 8px;background:var(--bg2);border:1px solid var(--border);border-radius:10px;text-align:center"><div class="kpi-label" style="font-size:10px;color:var(--text3);margin-bottom:2px">涨跌停</div><div class="kpi-value" style="font-size:15px;font-weight:700"><span style="color:#DC2626">{zt or "—"}</span>/<span style="color:#059669">{dt or "—"}</span></div></div>\n'
    h += "</div>\n"

    # Row 3: 情绪 + 收益
    upCnt2, dnCnt2 = li.get("上涨家数"), li.get("下跌家数")
    emotionVal = round(upCnt2 / (upCnt2 + dnCnt2) * 100) if (upCnt2 and dnCnt2 and upCnt2 + dnCnt2 > 0) else None
    h += '<div style="display:flex;gap:6px">\n'
    if emotionVal is not None:
        h += f'<div class="kpi-card" style="flex:1;padding:6px 8px;background:var(--bg2);border:1px solid var(--border);border-radius:10px;text-align:center"><div class="kpi-label" style="font-size:10px;color:var(--text3);margin-bottom:2px">情绪值</div><div class="kpi-value" style="font-size:15px;font-weight:700">{emotionVal}%</div></div>\n'

    def sentiment_value(*keys):
        for src in (iw, sentiment, sentiment_close):
            for key in keys:
                v = src.get(key)
                num = parse_float(v)
                if num is not None:
                    return num
        return None

    for label, keys in [
        ("涨停收益", ("昨日涨停收益", "涨停收益")),
        ("连板收益", ("连板收益",)),
        ("炸板收益", ("炸板收益", "昨日炸板收益")),
    ]:
        v = sentiment_value(*keys)
        if v is not None:
            c = "#DC2626" if v > 0 else "#059669"
            sign = "+" if v > 0 else ""
            h += f'<div class="kpi-card" style="flex:1;padding:6px 8px;background:var(--bg2);border:1px solid var(--border);border-radius:10px;text-align:center"><div class="kpi-label" style="font-size:10px;color:var(--text3);margin-bottom:2px">{label}</div><div class="kpi-value" style="font-size:15px;font-weight:700;color:{c}">{sign}{v:.2f}%</div></div>\n'
    h += "</div>\n"

    # Row 4: 北向
    if nb.get("hgt_yi") is not None or nb.get("sgt_yi") is not None:
        total = (nb.get("hgt_yi", 0) or 0) + (nb.get("sgt_yi", 0) or 0)
        nc = "#DC2626" if total >= 0 else "#059669"
        sign = "+" if total >= 0 else ""
        h += f'<div style="display:flex;gap:6px;padding:4px 0"><div class="kpi-card" style="flex:1;padding:4px 10px;background:var(--bg2);border:1px solid var(--border);border-radius:10px;text-align:center"><span style="font-size:10px;color:var(--text3)">北向资金 </span><span style="font-weight:600;font-size:15px;color:{nc}">{sign}{total:.1f}亿</span></div></div>\n'

    # Row 5: 涨跌分布条
    if isinstance(br, list): br = {}
    bt = br.get("_total", 0) or 0
    if bt > 0:
        upCats = ["涨停", ">7%", "5~7%", "3~5%", "0~3%"]
        dnCats = ["-0~-3%", "-3~-5%", "-5~-7%", "<-7%", "跌停"]
        upColors = ["#DC2626", "#EF4444", "#F87171", "#FCA5A5", "#FEE2E2"]
        dnColors = ["#D1FAE5", "#A7F3D0", "#6EE7B7", "#34D399", "#059669"]
        allCats = upCats + dnCats; allColors = upColors + dnColors
        h += '<div style="flex:1;display:flex;flex-direction:column;justify-content:center">\n'
        h += '<div style="display:flex;align-items:center;gap:1px;height:16px;border-radius:3px;overflow:hidden">\n'
        for cat, color in zip(allCats, allColors):
            n = br.get(cat, 0) or 0; pct = n / bt * 100
            if pct > 0.3:
                h += f'<div title="{cat}: {n} ({pct:.1f}%)" style="width:{pct:.1f}%;height:100%;background:{color};cursor:pointer;min-width:2px"></div>\n'
        h += "</div>\n"
        h += '<div style="display:flex;justify-content:space-between;font-size:8px;color:var(--text3);margin-top:2px">\n'
        for cat in upCats: h += f"<span>{br.get(cat, 0)}</span>\n"
        h += '<span style="width:6px"></span>\n'
        for cat in dnCats: h += f"<span>{br.get(cat, 0)}</span>\n"
        h += f'<span style="color:var(--text2);font-weight:600">{bt}只</span>\n'
        h += "</div></div>\n"

    # Row 6: 昨日基线折叠
    yest = [
        ("上证", yb.get("上证昨涨幅", "—"), yb.get("上证昨成交额", "—"), yb.get("上证昨上涨"), yb.get("上证昨下跌")),
        ("深证", yb.get("深证昨涨幅", "—"), yb.get("深证昨成交额", "—"), yb.get("深证昨上涨"), yb.get("深证昨下跌")),
        ("创业", yb.get("创业昨涨幅", "—"), yb.get("创业昨成交额", "—"), yb.get("创业昨上涨"), yb.get("创业昨下跌")),
    ]
    if any(chg != "—" or amt != "—" for _, chg, amt, _, _ in yest):
        yBody = ""
        for name, chg, amt, up, dn in yest:
            yd = "up" if str(chg).startswith("+") else "down" if str(chg).startswith("-") else ""
            yc = "#DC2626" if yd == "up" else "#059669" if yd == "down" else ""
            yBody += f'<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;background:var(--bg4);border-radius:4px;font-size:11px"><strong style="color:var(--text);font-size:12px">{name}</strong> <span style="font-weight:600;color:{yc}">{chg}</span> <span style="color:var(--text3)">{amt}</span>'
            if up is not None and dn is not None:
                yBody += f' <span style="color:#DC2626">{up}</span>/<span style="color:#059669">{dn}</span>'
            yBody += "</span>"
        h += f'<div style="border-top:1px solid var(--border);padding-top:4px">\n<div onclick="var b=this.nextElementSibling;var a=this.querySelector(\'span\');b.style.display=b.style.display===\'none\'?\'flex\':\'none\';a.textContent=b.style.display===\'none\'?\'▶\':\'▼\'" style="cursor:pointer;user-select:none;font-size:10px;color:var(--text3);letter-spacing:.5px">\n<span style="font-size:9px">▶</span> 昨日收盘基线</div>\n<div style="display:none;margin-top:4px;gap:6px;flex-wrap:wrap">{yBody}</div></div>\n'

    h += "</div>"
    return h


def main():
    # ── PnL data ──
    data = {}
    for per in ["today", "week", "month", "quarter", "year", "all"]:
        for idx in ["sh", "sz", "cy"]:
            try:
                data[f"{per}_{idx}"] = fetch(f"http://localhost:8088/api/pnl?range={per}&index={idx}")
            except Exception as e:
                print(f"FAIL PnL {per}_{idx}: {e}")
                sys.exit(1)

    try:
        data["summary"] = fetch("http://localhost:8088/api/pnl/summary")
    except Exception as e:
        print(f"FAIL summary: {e}")
        data["summary"] = {}

    # ── Meta: 从 pnl.db daily_summary 取最新收盘值（最稳，不受 gen/bridge 干扰）──
    try:
        db_path = str(PORTAL.parent / "live-dashboard" / "data" / "pnl.db")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT nav, deposit FROM daily_summary ORDER BY date DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        if row:
            nav, deposit = row
            deposit = float(deposit) if deposit else 200000
            total_asset = round(nav * deposit)
        else:
            total_asset, deposit = 0, 200000
    except Exception as e:
        print(f"FAIL daily_summary: {e}")
        total_asset, deposit = 0, 200000
    data["meta"] = {"total_asset": total_asset, "total_deposit": deposit}

    # ── Market snapshot ──
    try:
        baseline = fetch("http://localhost:8088/api/baseline")
        live = fetch("http://localhost:8088/api/live/quotes")
        market_html = build_market_html(baseline, live)
    except Exception as e:
        print(f"FAIL market: {e}")
        market_html = '<span style="color:var(--text3);font-size:12px">bridge 未运行</span>'

    # ── Embed into index.html ──
    target = PORTAL / "index.html"
    with open(target) as f:
        html = f.read()

    # PNL_DATA
    js_blob = f"<script>\nvar PNL_DATA = {json.dumps(data, ensure_ascii=False)};\n</script>"
    html = re.sub(r"(<!-- PNL_DATA_START -->).*?(<!-- PNL_DATA_END -->)", f"\\1\n{js_blob}\n  \\2", html, flags=re.DOTALL)

    # Market snapshot section: replace between id="market-snap" and next <div class="pnl-section"
    snap_start = html.index('<div id="market-snap"')
    snap_end = html.index('<div class="pnl-section" id="pnl-section"', snap_start)
    new_snap = f'<div id="market-snap" style="max-width:960px;margin:0 auto;padding:0 32px 16px">\n  <div class="section-header">\n    <span class="num">02</span>\n    <h2>市场快照</h2>\n    <span class="count">更新于 {datetime.now():%m/%d %H:%M}</span>\n  </div>\n  {market_html}\n</div>\n\n'
    html = html[:snap_start] + new_snap + html[snap_end:]

    with open(target, "w") as f:
        f.write(html)

    n = len(data.get("all_sh", {}).get("dates", []))
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] synced {n} PnL days + market snapshot → index.html")


if __name__ == "__main__":
    main()
