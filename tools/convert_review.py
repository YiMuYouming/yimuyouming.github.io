#!/usr/bin/env python3
"""
复盘笔记 MD → Portal HTML 转换器

用法:
  # 单文件转换
  python3 tools/convert_review.py ~/Documents/YouMingVault/.../2026_5_15_Friday_ReviewNote.md

  # 转换并自动 commit（不 push）
  python3 tools/convert_review.py <md路径> --commit

  # 批量转换本周所有笔记
  python3 tools/convert_review.py --batch W20

输出:
  - review-notes/YYYY-MM-DD.html  （复盘 HTML）
  - 自动更新 index.html（首页最新 5 篇）
  - 自动更新 review-notes/index.html（全部列表）
"""

import re
import sys
import os
import subprocess
from html import escape as html_escape
from datetime import datetime
from pathlib import Path

PORTAL = Path(__file__).resolve().parent.parent
REVIEW_NOTES = PORTAL / "review-notes"
CSS_FILE = None  # will use inline CSS from template

# ── CSS 模板（从已有 HTML 提取，所有页面共用） ──

CSS = """*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#F7F5F3;--bg2:#FFFFFF;--bg3:#FAFAF9;--bg4:#F5F2EE;--border:#E5E2DE;--text:#2D2926;--text2:#5C5652;--text3:#8A8480;--accent:#D97706;--accent-hover:#B45309;--red:#DC2626;--green:#059669;--blue:#2563EB;--purple:#7C3AED;--amber:#D97706}
html{scroll-behavior:smooth;scroll-padding-top:70px}
body{font:16px/1.7 system-ui,-apple-system,'Noto Sans SC',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;-webkit-font-smoothing:antialiased}
.topbar{position:sticky;top:0;z-index:100;background:rgba(247,245,243,.88);border-bottom:1px solid var(--border);padding:12px 24px;display:flex;align-items:center;gap:14px;flex-wrap:wrap;backdrop-filter:blur(12px)}
.topbar .title{font-size:18px;font-weight:700;color:var(--accent);white-space:nowrap}
.topbar .back{font-size:13px;color:var(--text2);padding:3px 10px;border-radius:6px;border:1px solid var(--border);white-space:nowrap;text-decoration:none;transition:all .12s}
.topbar .back:hover{color:var(--accent);border-color:var(--accent);background:var(--bg4)}
.topbar .meta{display:flex;gap:8px;flex-wrap:wrap;margin-left:auto}
.chip{padding:3px 11px;border-radius:12px;font-size:13px;font-weight:600;background:var(--bg3);border:1px solid var(--border);white-space:nowrap;color:var(--text2)}
.chip.red{border-color:var(--red);color:var(--red)}
.chip.green{border-color:var(--green);color:var(--green)}
.chip.amber{border-color:var(--amber);color:var(--amber);background:rgba(217,119,6,.08)}
.chip.blue{border-color:var(--blue);color:var(--blue)}
.chip.purple{border-color:var(--purple);color:var(--purple)}
@media(max-width:768px){.topbar .meta{width:100%;margin-left:0}.topbar .chip{white-space:normal;overflow-wrap:anywhere}}
.layout{display:flex}
.sidebar{width:210px;flex-shrink:0;position:sticky;top:62px;align-self:flex-start;max-height:calc(100vh - 62px);overflow-y:auto;padding:16px 0 16px 14px;border-right:1px solid var(--border);font-size:14px}
.sidebar::-webkit-scrollbar{width:4px}
.sidebar::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.sidebar .label{font-size:11px;text-transform:uppercase;color:var(--text3);padding:8px 10px 4px;letter-spacing:1px;font-weight:600}
.sidebar a{display:block;padding:5px 10px;color:var(--text2);text-decoration:none;font-size:13px;border-radius:4px;margin-bottom:2px;border-left:2px solid transparent;transition:all .12s}
.sidebar a:hover{background:var(--bg4);color:var(--text)}
.sidebar a.s2{padding-left:24px;font-size:12px}
.sidebar a.active{color:var(--accent);background:var(--bg4);border-left-color:var(--accent)}
.content{flex:1;padding:24px 32px;max-width:1100px;min-width:0}
@media(max-width:768px){.sidebar{display:none}.content{padding:16px}}
.section{background:var(--bg2);border:1px solid var(--border);border-radius:10px;margin-bottom:20px;overflow:hidden}
.sh{display:flex;align-items:center;gap:10px;padding:12px 18px;font-size:16px;font-weight:700;cursor:pointer;user-select:none;border-bottom:1px solid var(--border);background:var(--bg4)}
.sh:hover{background:var(--border)}
.sh .tog{color:var(--text3);font-size:11px;transition:transform .15s;flex-shrink:0}
.sh.collapsed .tog{transform:rotate(-90deg)}
.sh .cnt{font-size:12px;font-weight:400;color:var(--text3);margin-left:auto}
.sb{padding:0 18px 16px}
.sb.hide{display:none}
.si{color:var(--text2);font-size:14px;margin-bottom:12px;line-height:1.6;padding:10px 0 0}
.tw{overflow-x:auto;margin-bottom:14px}
.tw table{width:100%;border-collapse:separate;border-spacing:0;font-size:13px}
.tw thead th{position:sticky;top:0;background:var(--bg4);padding:8px 10px;text-align:left;font-weight:600;color:var(--text2);border-bottom:2px solid var(--border);font-size:12px;white-space:nowrap}
.tw tbody td{padding:7px 10px;border-bottom:1px solid var(--border);white-space:nowrap}
.tw tbody tr:hover{background:var(--bg4)}
.tw tbody tr:nth-child(even){background:rgba(0,0,0,.015)}
.up{color:var(--red);font-weight:600}
.down{color:var(--green);font-weight:600}
.dim{color:var(--text3)}
.badge{display:inline-block;padding:2px 8px;border-radius:9px;font-size:11px;font-weight:600;white-space:nowrap}
.badge-red{background:rgba(220,38,38,.1);color:var(--red)}
.badge-green{background:rgba(5,150,105,.1);color:var(--green)}
.badge-yellow{background:rgba(217,119,6,.1);color:var(--amber)}
.badge-blue{background:rgba(37,99,235,.08);color:var(--blue)}
.sg{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;margin-bottom:14px}
.sc{background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:14px}
.sbx{padding:12px 16px;background:var(--bg4);border-left:4px solid var(--blue);border-radius:0 8px 8px 0;margin-bottom:14px;font-size:14px;line-height:1.6}
.sbx.warn{border-left-color:var(--amber)}
.sbx.red{border-left-color:var(--red)}
.sbx.green{border-left-color:var(--green)}
.sh2{font-size:17px;font-weight:700;margin:20px 0 10px;color:var(--text);padding-top:4px}
.sh3{font-size:15px;font-weight:600;margin:14px 0 8px;color:var(--text);padding-top:2px}
#s1b,.section#s3>.sh{font-family:"Noto Serif SC","Noto Serif","Songti SC",serif}
#s1b + .emotion-board .emotion-kpi .klabel,#s1b + .emotion-board .emotion-kpi .kval,#s1b + .emotion-board .emotion-conclusion,#s3>.sb>.stats-grid .stat-card .lbl,#s3>.sb>.stats-grid .stat-card .val,#s3>.sb>.sbx{font-family:"Noto Sans SC","PingFang SC","Hiragino Sans GB",system-ui,sans-serif}
#s1b + .emotion-board .emotion-kpi .kval,#s3>.sb>.stats-grid .stat-card .val{font-weight:700;letter-spacing:-.01em}
.para{font-size:14px;line-height:1.7;margin-bottom:8px;color:var(--text)}
.tight-list{font-size:14px;line-height:1.6;margin-bottom:8px;padding-left:20px}
.tight-list li{margin-bottom:3px}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px;margin-bottom:14px}
.stat-card{background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:10px 14px;text-align:center}
.stat-card .val{font-size:22px;font-weight:700}
.stat-card .lbl{font-size:11px;color:var(--text3);margin-top:2px}
.stat-card .val.red{color:var(--red)}.stat-card .val.green{color:var(--green)}.stat-card .val.amber{color:var(--amber)}
.node-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;margin-bottom:14px}
.node-card{background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:12px}
.node-card .nhead{font-weight:700;font-size:14px;margin-bottom:6px}
.node-card .nbody{font-size:13px;color:var(--text2);line-height:1.6}
.node-timeline{position:relative;display:grid;gap:14px;margin:12px 0 18px;padding-left:18px}
.node-timeline::before{content:"";position:absolute;left:5px;top:8px;bottom:8px;width:2px;background:linear-gradient(180deg,rgba(217,119,6,.55),rgba(217,119,6,.12))}
.node-note-card{position:relative;background:linear-gradient(180deg,#fff,#FBF8F3);border:1px solid rgba(229,226,222,.95);border-radius:12px;padding:14px 16px;min-width:0;box-shadow:0 10px 26px rgba(45,41,38,.045)}
.node-note-card::before{content:"";position:absolute;left:-19px;top:20px;width:10px;height:10px;border-radius:999px;background:#D97706;box-shadow:0 0 0 4px #F7F5F3,0 0 0 6px rgba(217,119,6,.18)}
.node-phase{display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:16px;font-weight:900;color:var(--text);margin-bottom:10px;padding-bottom:9px;border-bottom:1px solid rgba(229,226,222,.8)}
.node-phase span{font-family:'Noto Serif SC',serif}
.node-phase em{font-style:normal;font-size:11px;font-weight:800;letter-spacing:.08em;color:var(--accent);background:rgba(217,119,6,.08);border:1px solid rgba(217,119,6,.18);border-radius:999px;padding:4px 8px;white-space:nowrap}
.node-detail{display:grid;grid-template-columns:78px minmax(0,1fr);gap:10px;padding:9px 0;border-top:1px solid rgba(229,226,222,.64)}
.node-detail:first-of-type{border-top:0}
.node-label{font-size:12px;font-weight:900;color:var(--accent);line-height:1.5}
.node-copy{font-size:13px;color:var(--text2);line-height:1.7;word-break:break-word}
.node-copy strong{color:var(--text)}
.lesson-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin:12px 0 18px}
.lesson-card{position:relative;background:linear-gradient(180deg,#fff,#FCFAF7);border:1px solid rgba(229,226,222,.96);border-radius:12px;padding:15px 15px 14px;box-shadow:0 12px 28px rgba(45,41,38,.045);overflow:hidden}
.lesson-card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--blue)}
.lesson-card.warning::before{background:var(--red)}
.lesson-card.topic::before{background:var(--purple)}
.lesson-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:9px}
.lesson-tag{display:inline-flex;align-items:center;height:22px;padding:0 8px;border-radius:999px;font-size:12px;font-weight:900}
.lesson-card.cognition .lesson-tag{background:rgba(37,99,235,.08);color:var(--blue)}
.lesson-card.warning .lesson-tag{background:rgba(220,38,38,.08);color:var(--red)}
.lesson-card.topic .lesson-tag{background:rgba(124,58,237,.08);color:var(--purple)}
.lesson-type{font-size:11px;font-weight:900;color:var(--text3);letter-spacing:.08em;white-space:nowrap}
.lesson-principle{font-family:'Noto Serif SC',serif;font-size:17px;line-height:1.45;font-weight:800;color:var(--text);margin-bottom:11px;word-break:break-word}
.lesson-label{font-size:11px;font-weight:900;color:var(--accent);letter-spacing:.08em;margin-bottom:5px}
.lesson-evidence{background:rgba(245,242,238,.72);border:1px solid rgba(229,226,222,.82);border-radius:9px;padding:10px 11px;font-size:13px;line-height:1.7;color:var(--text2);margin-bottom:10px}
.lesson-evidence .para{font-size:13px;margin-bottom:0;color:var(--text2)}
.lesson-action{position:relative;background:rgba(217,119,6,.07);border:1px solid rgba(217,119,6,.18);border-radius:9px;padding:9px 11px 9px 32px;font-size:13px;line-height:1.6;color:var(--text)}
.lesson-action::before{content:"→";position:absolute;left:12px;top:9px;color:var(--accent);font-weight:900}
@media(max-width:520px){.lesson-grid{grid-template-columns:1fr}.lesson-head{align-items:flex-start}.lesson-type{white-space:normal;text-align:right}.lesson-principle{font-size:16px}}
.warn-box{background:rgba(220,38,38,.06);border:1px solid rgba(220,38,38,.2);border-radius:8px;padding:14px;margin-bottom:14px;font-size:13px;line-height:1.6}
.warn-box .wtitle{font-weight:700;color:var(--red);margin-bottom:4px}
[id]{scroll-margin-top:70px}
.verdict{background:var(--bg3);border:1px solid var(--green);border-radius:8px;padding:14px;margin:12px 0}
.verdict .vt{font-weight:700;color:var(--green);margin-bottom:4px;font-size:15px}
.verdict .vb{font-size:14px;color:var(--text2);line-height:1.7}
.debate-row{display:flex;gap:12px;margin-bottom:10px;font-size:13px;line-height:1.5}
.debate-row .dr-label{min-width:100px;font-weight:600;color:var(--text2);text-align:right;padding-top:2px}
.debate-row .dr-body{flex:1;padding:8px 12px;background:var(--bg3);border-radius:6px}
.debate-row .dr-body.accept{background:rgba(5,150,105,.06);border-left:3px solid var(--green)}
.debate-row .dr-body.partial{background:rgba(217,119,6,.04);border-left:3px solid var(--amber)}
.emotion-board{display:grid;gap:14px;margin:10px 0 16px}
.emotion-summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.emotion-kpi{background:linear-gradient(180deg,#fff,var(--bg3));border:1px solid var(--border);border-radius:10px;padding:11px 12px;min-height:76px}
.emotion-kpi .klabel{font-size:12px;color:var(--text3);margin-bottom:4px}
.emotion-kpi .kval{font-size:20px;line-height:1.15;font-weight:800;color:var(--text);word-break:break-word}
.emotion-kpi.good .kval{color:var(--red)}.emotion-kpi.warn .kval{color:var(--amber)}.emotion-kpi.bad .kval{color:var(--green)}
.emotion-conclusion{display:flex;align-items:baseline;gap:8px;margin:0 0 14px;padding:3px 0 3px 10px;border-left:3px solid var(--red);font-size:14px;line-height:1.6;flex-wrap:wrap}
.emotion-conclusion-label{font-weight:700;color:var(--red);white-space:nowrap}.emotion-conclusion-text{color:var(--text);font-weight:600;word-break:break-word}
.emotion-stage-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px}
.emotion-stage{background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:12px}
.emotion-stage .stage-title{font-size:14px;font-weight:800;color:var(--accent);margin-bottom:8px}
.emotion-row{display:grid;grid-template-columns:82px minmax(0,1fr);gap:8px;border-top:1px solid rgba(229,226,222,.75);padding:7px 0;font-size:12px}
.emotion-row:first-of-type{border-top:0}
.emotion-row .rlabel{color:var(--text3);white-space:normal;line-height:1.35;min-width:0}
.emotion-row .rval{color:var(--text2);line-height:1.45;word-break:break-word}
.emotion-row.major{display:block;background:#fff;border:1px solid var(--border);border-radius:8px;padding:9px 10px;margin-top:8px}
.emotion-row.major .rlabel{display:block;margin-bottom:3px;font-weight:700;color:var(--text)}
.emotion-thresholds{background:rgba(217,119,6,.06);border:1px solid rgba(217,119,6,.24);border-radius:10px;padding:12px}
.emotion-thresholds .threshold-title{font-size:13px;font-weight:800;color:var(--accent);margin-bottom:8px}
.emotion-thresholds .threshold-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px}
.emotion-thresholds .threshold-item{background:#fff;border:1px solid var(--border);border-radius:8px;padding:7px 9px;font-size:12px;line-height:1.45}
.emotion-thresholds .threshold-item strong{color:var(--text);margin-right:6px}"""

JS_FOOTER = """<script>
const io=new IntersectionObserver(e=>{e.forEach(e=>{const l=document.querySelector(`a[href="#${e.target.id}"]`);if(l&&e.isIntersecting){document.querySelectorAll('.sidebar a').forEach(a=>a.classList.remove('active'));l.classList.add('active')}})},{rootMargin:'-100px 0px -70% 0px'});
document.querySelectorAll('.section[id]').forEach(s=>io.observe(s));
</script>"""

# ── Parse helpers ──

def parse_frontmatter(text):
    """Extract YAML frontmatter between --- markers."""
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).strip().split('\n'):
        if ':' in line:
            key, _, val = line.partition(':')
            fm[key.strip()] = val.strip().strip('"')
    return fm


def parse_md_table(text):
    """Parse a markdown table into list of dicts. Returns (headers, rows)."""
    lines = text.strip().split('\n')
    if len(lines) < 2:
        return [], []
    headers = [h.strip() for h in lines[0].split('|')[1:-1]]
    rows = []
    for line in lines[2:]:  # skip separator
        cells = [c.strip() for c in line.split('|')[1:-1]]
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return headers, rows


def extract_tables(text):
    """Find all markdown tables in text."""
    tables = []
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        if re.match(r'^\|.*\|$', lines[i]):
            start = i
            while i < len(lines) and re.match(r'^\|.*\|$', lines[i]):
                i += 1
            tables.append('\n'.join(lines[start:i]))
        else:
            i += 1
    return tables


def extract_between(text, start_marker, end_marker=None):
    """Extract text between two markers."""
    start_idx = text.find(start_marker)
    if start_idx == -1:
        return ""
    start_idx += len(start_marker)
    if end_marker:
        end_idx = text.find(end_marker, start_idx)
        if end_idx == -1:
            return text[start_idx:].strip()
        return text[start_idx:end_idx].strip()
    return text[start_idx:].strip()


def extract_section(text, heading):
    """Extract a section by ## heading. Returns (content, remaining_text)."""
    pattern = rf'^## {re.escape(heading)}'
    m = re.search(pattern, text, re.MULTILINE)
    if not m:
        return "", text
    start = m.end()
    # Find next ## heading
    next_m = re.search(r'^## ', text[start:], re.MULTILINE)
    if next_m:
        end = start + next_m.start()
        return text[start:end].strip(), text[end:]
    return text[start:].strip(), ""


def pct_text(value, signed=False):
    """Render numeric frontmatter percentages consistently."""
    s = str(value).strip()
    if not s or s == '--':
        return s
    try:
        n = float(s.rstrip('%'))
        sign = '+' if signed and n > 0 and not s.startswith('+') else ''
        suffix = '' if s.endswith('%') else '%'
        return f'{sign}{s}{suffix}'
    except ValueError:
        return s


def numeric_value(value):
    """Extract the first numeric value from a frontmatter string."""
    m = re.search(r'-?\d+(?:\.\d+)?', str(value))
    return float(m.group(0)) if m else None


def anonymize_current_holdings(text, fm):
    """Replace current holding names and their security codes with stable public aliases."""
    content = str(text or '')
    position_summary = str((fm or {}).get('盘后持仓', ''))
    names = []
    for name in re.findall(
        r'([A-Za-z\u4e00-\u9fff][A-Za-z0-9\u4e00-\u9fff*]{1,15}?)\s*\d+(?:\.\d+)?\s*股',
        position_summary,
    ):
        if name not in names:
            names.append(name)

    labels = ('一', '二', '三', '四', '五', '六', '七', '八', '九', '十')
    for index, name in enumerate(names):
        alias = f'持仓标的{labels[index] if index < len(labels) else index + 1}'
        short_aliases = []
        for suffix in ('股份', '科技', '集团', '信息', '电子'):
            if name.endswith(suffix) and len(name) - len(suffix) >= 2:
                short_aliases.append(name[:-len(suffix)])
        codes = set(re.findall(rf'{re.escape(name)}[^\n]{{0,32}}\b([0368]\d{{5}})\b', content))
        codes.update(re.findall(rf'\b([0368]\d{{5}})\b[^\n]{{0,32}}{re.escape(name)}', content))
        content = content.replace(name, alias)
        for short_alias in short_aliases:
            content = content.replace(short_alias, alias)
        for code in codes:
            content = re.sub(rf'\b{re.escape(code)}\b', '代码已脱敏', content)
    return content


def sanitize_public_review_text(text, redact_internal_labels=True):
    """Redact account-specific execution details from the public review layer."""
    cleaned = str(text or '')
    cleaned = re.sub(
        r'\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:[+-]\d{2}:\d{2}|Z)?',
        '日期已记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'(?<![A-Za-z0-9_])pnl\.db(?![A-Za-z0-9_])', '内部账户记录', cleaned, flags=re.I)
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])c15_signal_ledger(?![A-Za-z0-9_])',
        '候选记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])d2_decision_receipt(?![A-Za-z0-9_])',
        '裁决记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])degraded_acceptance(?:_receipt|\.v\d+)?(?![A-Za-z0-9_])',
        '降级授权记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'TICKET-[A-Za-z0-9_-]+', '交易记录', cleaned, flags=re.I)
    cleaned = re.sub(
        r'[一二三四五六七八九十百千万两零〇\d]+\s*笔\s*'
        r'(?:买入|开仓|加仓|建仓)(?:\s*(?:部分仓位|仓位))?',
        '新增风险暴露',
        cleaned,
    )
    cleaned = re.sub(
        r'[一二三四五六七八九十百千万两零〇\d]+\s*笔\s*'
        r'(?:卖出|清仓|减仓)(?:\s*(?:部分仓位|仓位))?',
        '风险处理动作',
        cleaned,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])[一二三四五六七八九十百千万两零〇\d]+\s*笔',
        '若干笔',
        cleaned,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])tickets?\s*=\s*\d+(?![A-Za-z0-9_])',
        '交易记录数量已隐藏',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])(?:(?:execution|executable)\s+)?tickets?\b',
        '内部执行记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'(?<![A-Za-z0-9_])EXEC-[A-Za-z0-9_+:-]+', '执行记录', cleaned, flags=re.I)
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])trade[_\s-]?id\s*[:=]?\s*[A-Za-z0-9_-]+'
        r'(?:\s*[–—-]\s*[A-Za-z0-9_-]+)?',
        '交易流水已隐藏',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])trade\s*[:=]\s*[A-Za-z0-9_-]+',
        '交易流水已隐藏',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'(?<![A-Za-z0-9_])CAN-[A-Za-z0-9_-]+', '内部候选记录', cleaned, flags=re.I)
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])blocked[_-]?degraded(?![A-Za-z0-9_])',
        '数据降级，仅观察', cleaned, flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])ready_with_warnings(?![A-Za-z0-9_])',
        '复核状态已记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])PLAN_NOT_CURRENT(?![A-Za-z0-9_])',
        '计划状态已记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])blocked(?![A-Za-z0-9_])',
        '状态受限',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])degraded[ _-]?acceptance(?![A-Za-z0-9_])',
        '数据缺口确认',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])candidate_id(?![A-Za-z0-9_])',
        '候选记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'(?<![A-Za-z0-9_])backfill(?![A-Za-z0-9_])', '补录', cleaned, flags=re.I)
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])yimu_resolution_handoff\.md(?![A-Za-z0-9_])',
        '交接记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])post_trade_reconciliation(?![A-Za-z0-9_])',
        '成交事实核对',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])lot_reconciliation_ok\s*=\s*(?:true|false)(?![A-Za-z0-9_])',
        '账户事实已复核',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])valuation_complete\s*=\s*(?:true|false)(?![A-Za-z0-9_])',
        '估值状态已记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])(?:scheduled_review_fill|rotation_decisions|'
        r'round_3_resolved|yangmi_red_team_round3)(?![A-Za-z0-9_])',
        '复核记录已脱敏',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'内部执行记录[_＿]id', '记录', cleaned, flags=re.I)
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])stage_final\s*[:=]\s*done(?![A-Za-z0-9_])',
        '终稿', cleaned, flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])stage_(?:a|b|c|d0|d|red_team|final)\s*[:=]\s*[A-Za-z_]+(?![A-Za-z0-9_])',
        '流程状态已确认', cleaned, flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])(?:finalized[_-]?degraded|degraded[_-]?(?:done|accepted))(?![A-Za-z0-9_])',
        '降级流程已记录', cleaned, flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_.-])market_watch\.red_team\.v\d+(?![A-Za-z0-9_.-])',
        '对抗记录已脱敏', cleaned, flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])red[_ -]?receipt(?![A-Za-z0-9_])',
        '对抗回执已脱敏', cleaned, flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])red[_-]?team(?![A-Za-z0-9_])',
        '对抗记录', cleaned, flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])round_\d+_submitted(?![A-Za-z0-9_])',
        '对抗状态已记录', cleaned, flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])finalizer(?![A-Za-z0-9_])',
        '终稿流程', cleaned, flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])observation[_-]?only(?![A-Za-z0-9_])',
        '仅观察', cleaned, flags=re.I,
    )
    cleaned = re.sub(
        r'["`]?(?:process[ _-]?defect)["`]?\s*[:=]\s*(?:true|false)',
        '流程缺口已记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])process[ _-]?defect(?![A-Za-z0-9_])',
        '流程缺口',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])human_resolution(?![A-Za-z0-9_])',
        '人工裁决',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])(?:ledger|d2)_sha256(?![A-Za-z0-9_])',
        '内部校验字段',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])trade_review(?![A-Za-z0-9_])',
        '交易复核',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])trade_watch(?![A-Za-z0-9_])',
        '持仓复核',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'(?<![A-Za-z0-9_])no_touch(?![A-Za-z0-9_])', '不参与', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])observe(?![A-Za-z0-9_])', '观察', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])exclude(?![A-Za-z0-9_])', '排除', cleaned, flags=re.I)
    cleaned = re.sub(r'human_required\s*=\s*[A-Z0-9_]+', '需人工复核', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<!\d)8088(?!\d)', '盘前数据入口已隐藏', cleaned)
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])available_add_pct\s*=\s*[-+]?\d+(?:\.\d+)?',
        '新增仓位条件已脱敏',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])execution_card(?![A-Za-z0-9_])',
        '规则条件记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])review_source_packet(?![A-Za-z0-9_])',
        '来源记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])source_gaps?(?![A-Za-z0-9_])',
        '数据缺口',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])(?:c15|d0|d1|d2)_[A-Za-z0-9_]+(?:\s*=\s*[^\s，。；|]+)?',
        '内部校验字段',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])(?:position_lots|trade_records)(?![A-Za-z0-9_])',
        '内部账户记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])SIG-\d{8}-[A-Za-z0-9]+(?![A-Za-z0-9_])',
        '候选记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?:added|changed)_candidate_ids\s*=\s*\[[^\]]*\]|changes\s*=\s*\[[^\]]*\]',
        '候选变更已记录', cleaned, flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])(?:added|changed)_candidate_ids(?![A-Za-z0-9_])',
        '候选变更字段', cleaned, flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])candidate_disposition(?![A-Za-z0-9_])',
        '候选裁决记录', cleaned, flags=re.I,
    )
    cleaned = re.sub(r'scripts\.selection_closure\.artifact_sha256', '内部校验工具', cleaned, flags=re.I)
    cleaned = re.sub(r'回执审计', '复核说明', cleaned)
    cleaned = re.sub(
        r'artifact\s+hash\s+与\s*回执自哈希\s*均匹配',
        '复核记录一致',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'(?<![A-Za-z0-9_])artifact\s+hash(?![A-Za-z0-9_])', '校验记录', cleaned, flags=re.I)
    cleaned = re.sub(r'回执自哈希', '校验记录', cleaned)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])receipt_sha256(?![A-Za-z0-9_])', '回执哈希', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])artifact_sha256(?![A-Za-z0-9_])', '记录哈希', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])canonical(?![A-Za-z0-9_])', '规范校验', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])', '哈希已隐藏', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])d2_receipt(?![A-Za-z0-9_])', '裁决记录', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])receipt(?![A-Za-z0-9_])', '来源记录', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])resolution(?![A-Za-z0-9_])', '裁决记录', cleaned, flags=re.I)
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])(?:focus_sectors|rotation_board_scan)(?![A-Za-z0-9_])',
        '板块扫描字段',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'(?<![A-Za-z0-9_])candidate(?![A-Za-z0-9_])', '候选记录', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])SSOT(?![A-Za-z0-9_])', '规则源', cleaned, flags=re.I)
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])(?:neodata_query_script_missing|'
        r'semiconductor_index_exact_close_unverified|asia_snapshot_session_scope|'
        r'domestic_high_impact_event_unverified|account_position_reconciliation_mismatch_\d+|'
        r'quotes_stale_preopen)(?![A-Za-z0-9_])',
        '数据缺口',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])execution_plan_valid\s*=\s*(?:true|false)(?![A-Za-z0-9_])',
        '规则条件已脱敏',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])add_allowed\s*=\s*(?:true|false)(?![A-Za-z0-9_])',
        '新增仓位条件已脱敏',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])freshness\s*=\s*`?[A-Za-z][A-Za-z0-9_-]*`?(?![A-Za-z0-9_])',
        '行情时效已记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])MARKET_SESSION_CLOSED(?![A-Za-z0-9_])',
        '市场状态已记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'(?<![A-Za-z0-9_])lots\s*=\s*[-+]?\d+(?![A-Za-z0-9_])', '账户批次已隐藏', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])NeoData(?![A-Za-z0-9_])', '外部数据源', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])baseline(?![A-Za-z0-9_])', '盘前基准', cleaned, flags=re.I)
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])(?:stale|delayed|dead|missing)(?![A-Za-z0-9_])',
        '数据状态已记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'(?<![A-Za-z0-9_])ledger(?![A-Za-z0-9_])', '候选记录', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])source_gap(?![A-Za-z0-9_])', '数据缺口', cleaned, flags=re.I)
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])AI\s+context(?![A-Za-z0-9_])',
        '系统判断',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])limit_up_detail\s+returned\s*=\s*(\d+)(?![A-Za-z0-9_])',
        lambda match: '连板明细数据缺失' if match.group(1) == '0' else '连板明细数据已记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'缺源(?:脚本)?占位', '数据缺口估算', cleaned)
    cleaned = re.sub(r'占位内容', '临时内容', cleaned)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])radarsignal(?![A-Za-z0-9_])', '观察信号', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])decision_gate(?![A-Za-z0-9_])', '实时门禁', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])POS-SIZE-\d+(?![A-Za-z0-9_])', '仓位规则', cleaned, flags=re.I)
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])ACCT-[A-Za-z0-9_-]+(?![A-Za-z0-9_])',
        '账户规则',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])WIN-[A-Za-z0-9_-]+(?![A-Za-z0-9_])',
        '窗口规则',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'(?<![A-Za-z0-9_])W1_[A-Z0-9_]+(?![A-Za-z0-9_])', '窗口条件', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])C1\.5(?![A-Za-z0-9_])', '候选证据层', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])C2(?![A-Za-z0-9_])', '板块复核层', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])D1(?![A-Za-z0-9_])', '系统复核层', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])D2(?![A-Za-z0-9_])', '人工复核层', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])D3(?![A-Za-z0-9_])', '阶段复核', cleaned, flags=re.I)
    cleaned = re.sub(r'机器预案层', '系统复核层', cleaned)
    cleaned = re.sub(r'人工裁决层', '人工复核层', cleaned)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])F-\d{3}(?![A-Za-z0-9_])', '审阅项', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])fail[-_ ]closed(?![A-Za-z0-9_])', '证据不足则关闭', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])(?:added_at_)?peak_risk(?![A-Za-z0-9_])', '高位风险标记', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])rotation_state(?![A-Za-z0-9_])', '轮动状态证据', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])candidate_codes(?![A-Za-z0-9_])', '候选代码记录', cleaned, flags=re.I)
    public_rule_labels = {
        'CLIMAX_STOP': '高潮风险约束',
        'WEEK_STOP': '周回撤门禁',
        'LOSS_STREAK': '连亏门禁',
        'DAY_STOP': '日内风险约束',
    }
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])(?:CLIMAX_STOP|WEEK_STOP|LOSS_STREAK|DAY_STOP)(?![A-Za-z0-9_])',
        lambda match: public_rule_labels[match.group(0).upper()],
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])(?:PLAN_W1_CLOSED|WINDOW_CLOSED|POSITION_ADD_BLOCKED)(?![A-Za-z0-9_])',
        '执行条件已隐藏',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'/Users/[A-Za-z0-9._-]+/[^\s`<>|，。；]+',
        '内部审计记录（路径已隐藏）',
        cleaned,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])/?api/[^\s`<>|，。；]+',
        '内部执行入口已隐藏',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'receipt_sha256=[0-9a-f]{64}', 'receipt_sha256=已隐藏', cleaned, flags=re.I)
    cleaned = re.sub(
        r'(?<!\d)\d{1,2}:\d{2}(?::\d{2})?(?=[^，。；\n|]{0,24}(?:成交|买入|加仓|减仓|清仓|卖出|gate|快照|内部执行校验))',
        '盘中',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<!\d)\d{1,2}:\d{2}(?::\d{2})?(?=\s*@\s*\d+(?:\.\d+)?)',
        '盘中',
        cleaned,
    )
    cleaned = re.sub(
        r'(?<!\d)\d{1,2}:\d{2}(?::\d{2})?(?=[^，。；\n|]{0,28}(?:两笔|执行卡|门禁|买入|卖出))',
        '盘中',
        cleaned,
    )
    cleaned = re.sub(
        r'精确\s*(?:decision_)?gate\s*快照(?:缺失|未留存)',
        '精确内部执行校验未留存',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?:decision_)?gate(?:\.allowed)?\s*=\s*(?:true|false)',
        '内部执行校验已脱敏',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_.])allowed\s*=\s*(?:true|false)',
        '内部执行校验已脱敏',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'实时门禁(?:\.allowed)?\s*=\s*(?:true|false)',
        '内部执行校验已脱敏',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'gatestatus', '内部执行校验状态', cleaned, flags=re.I)
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])reconciliation',
        '成交事实核对',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'无盘前\s*内部执行记录', '盘前执行记录未公开', cleaned)
    cleaned = re.sub(r'已成交\s*成交事实核对', '成交事实已核对', cleaned)
    cleaned = re.sub(
        r'(?<![:\d])\b\d+\s*@\s*\d+(?:\.\d+)?',
        '部分仓位@成交价已隐藏',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:原|合计|累计|总仓)\s*)\d+(?:\s*股)?(?:\s*[+→=]\s*\d+(?:\s*股)?)+',
        lambda match: (
            '总仓数量已脱敏'
            if match.group(1).strip() == '总仓'
            else f'{match.group(1)}仓位数量已脱敏'
        ),
        cleaned,
    )
    cleaned = re.sub(
        r'累计\s*\d+(?:\s*股)?(?=\s*(?:全清|清仓|持有|可卖|锁定))',
        '累计仓位已脱敏',
        cleaned,
    )
    cleaned = re.sub(r'\d+\s*股', '部分仓位', cleaned)
    cleaned = re.sub(
        r'(?<![\d.+])\d{2,6}(?=\s*(?:锁定|锁|可卖量|解锁))',
        '仓位数量已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'新\s*\d+(?:\s*股)?\s*(?:已)?解锁(?:日)?\s*'
        r'(?:\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2})?',
        '新增批次可卖状态已记录',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:先|再|计划)?(?:买入|卖出|加仓|减仓|清仓|买|卖|减)\s+)'
        r'[-+]?\d{2,4}(?:\.\d+)?(?=\s*(?:浮亏|浮盈|亏损|盈利|成交|买入|卖出|加仓|减仓|清仓|扩大|缩小|$))',
        r'\1成交价已隐藏',
        cleaned,
    )
    cleaned = re.sub(
        r'(?:全部|新?部分仓位)?\s*T\+1\s*锁(?:定)?至\s*(?:\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2})',
        'T+1状态已记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?:全部|新?部分仓位)?\s*锁定至\s*\d{1,2}月\d{1,2}日',
        'T+1状态已记录',
        cleaned,
    )
    cleaned = re.sub(
        r'(?:全部|新?部分仓位)?\s*\d{1,2}/\d{1,2}\s*解锁',
        'T+1状态已记录',
        cleaned,
    )
    cleaned = re.sub(
        r'\d{1,2}/\d{1,2}\s*T\+1\s*(?:已)?(?:锁定|解锁|可卖|不可卖)',
        '次日可卖状态复核',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?:全部|新?部分仓位)?\s*T\+1\s*(?:已)?(?:锁定|解锁|可卖|不可卖)',
        '可卖状态已记录',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![\d/])锁(?:定)?\s*\d{1,2}/\d{1,2}(?![\d/])',
        '可卖状态已记录',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:先|再|计划)?(?:买入|卖出|加仓|减仓|清仓|买|卖|减))\s*\d+(?![\d.%])',
        r'\1部分仓位',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:用|看|观察|参考|区间(?:为)?|验证(?:区间)?|(?:再次)?测试)[：:]?\s*)'
        r'\d{2,3}(?:\.\d+)?\s*[—~-]\s*\d{2,3}(?:\.\d+)?'
        r'(?:\s*/\s*\d{2,3}(?:\.\d+)?\s*[—~-]\s*\d{2,3}(?:\.\d+)?)?',
        r'\1关键区间',
        cleaned,
    )
    cleaned = re.sub(
        r'(?<![\d.])\d{2,4}(?:\.\d+)?\s*[—~-]\s*\d{2,4}(?:\.\d+)?'
        r'(?=\s*(?:/|风险区|修复区|验证区|下方|上方|失守|修复))',
        '关键区间',
        cleaned,
    )
    cleaned = re.sub(
        r'(?<=[\u4e00-\u9fff])\d{2,4}(?:\.\d+)?'
        r'(?=\s*(?:下方|修复(?:受阻|条件|彻底|判断)?|风险区|止损线|未收复|收复|失守|守住))',
        '关键位',
        cleaned,
    )
    cleaned = re.sub(
        r'(?<!涨停)(?<!跌停)(?<!上涨)(?<!下跌)'
        r'(?<=[\u4e00-\u9fff])'
        r'(?!\d{2,4}(?:\.\d+)?\s*/\s*(?:涨停|跌停|上涨|下跌)\d)'
        r'\d{2,4}(?:\.\d+)?'
        r'(?=\s*(?:/|与)[\u4e00-\u9fff]{2,8}\d)',
        '关键位',
        cleaned,
    )
    cleaned = re.sub(
        r'(?<=[\u4e00-\u9fff])\d{2,4}(?:\.\d+)?'
        r'(?=\s*(?:/|与)[^，。；\n|]{0,24}(?:风险区|失守))',
        '关键位',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:风险复核带|价格风险带)[^，。；\n|]*?MA\d+\s*[(]?\s*)'
        r'\d{2,4}(?:\.\d+)?',
        r'\1关键位',
        cleaned,
    )
    cleaned = re.sub(
        r'(?<![\d.])\d{2,4}(?:\.\d+)?'
        r'(?=\s*修复(?:受阻|条件|彻底|判断|失败))',
        '关键位',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:跌破|破|击穿|站稳|站上|收复|守住|守|不站回|未站|失守|考验|识别|验证|上方|看|观察|复核|等待|低于|高于|突破|低点)(?:MA\d+=)?)'
        r'\d+(?:\.\d+)?\s*[—~-]\s*\d+(?:\.\d+)?',
        r'\1关键区间',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:跌破|破|击穿|站稳|站上|收复|守住|守|不站回|未站|失守|考验|识别|验证|上方|看|观察|复核|等待|低于|高于|突破|低点)(?:MA\d+=)?)'
        r'\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)*(?!\s*(?:只|家|个|人|条))',
        r'\1关键位',
        cleaned,
    )
    cleaned = re.sub(
        r'(关键位)\s*[<>]\s*\d+(?:\.\d+)?',
        r'\1附近',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:持续|仍|未站稳|不站稳)\s*)[<>≤≥]\s*\d+(?:\.\d+)?',
        r'\1关键位',
        cleaned,
    )
    cleaned = re.sub(
        r'(?<=[（(])\s*[<>≤≥]\s*\d+(?:\.\d+)?'
        r'(?=\s*(?:清仓|卖出|减仓|降低风险|降风险|风险|建议|[）)]))',
        '关键位',
        cleaned,
    )
    cleaned = re.sub(r'(?<![A-Za-z0-9_])rule_state(?![A-Za-z0-9_])', '运行规则', cleaned, flags=re.I)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])entry_leg(?![A-Za-z0-9_])', '建仓层级', cleaned, flags=re.I)
    cleaned = re.sub(
        r'(?:减至\s*)?(?:≤|不高于)\s*\d+(?:\.\d+)?%',
        '降低至内部集中度上限',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:[\u4e00-\u9fffA-Za-z]{1,12})(?:虽)?收)\s*\d+(?:\.\d+)?',
        r'\1 价格已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'(未完成\s*)\d+(?:\.\d+)?(?=\s*修复)',
        r'\1关键位',
        cleaned,
    )
    cleaned = re.sub(
        r'(为\s*)\d+(?:\.\d+)?\s*[-~—]\s*\d+(?:\.\d+)?(?=\s*一字板)',
        r'\1关键区间',
        cleaned,
    )
    cleaned = re.sub(
        r'(冲高\s*)\d+(?:\.\d+)?',
        r'\1关键位',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:尚未|未)?(?:收复|收回|站稳|站上|守住|失守|跌破|破|看|观察|校准)\s*)'
        r'\d+(?:\.\d+)?(?:\s*(?:[-~/、]|和|与)\s*\d+(?:\.\d+)?)*(?!\s*(?:只|家|个|人|条))',
        r'\1关键位',
        cleaned,
    )

    def redact_calibration_clause(match):
        return re.sub(r'(?<![\d.])\d+\.\d+(?![\d.])', '关键位', match.group(0))

    cleaned = re.sub(
        r'明日以[^。；\n]{0,180}?校准',
        redact_calibration_clause,
        cleaned,
    )
    cleaned = re.sub(r'清仓建议', '降低风险建议', cleaned)
    cleaned = re.sub(r'禁止补仓', '不提高风险暴露', cleaned)
    cleaned = re.sub(
        r'(?:(?:不高于|上限(?:显示|要求)?|要求)\s*)\d+(?:\.\d+)?%',
        '内部集中度上限',
        cleaned,
    )
    cleaned = re.sub(r'(?:不高于)?关键位%', '内部集中度上限', cleaned)
    cleaned = cleaned.replace('降至降低至内部集中度上限', '降至内部集中度上限')
    cleaned = re.sub(
        r'((?:现价|当前价)[：:]?\s*)[-+]?\d+(?:\.\d+)?(?![\d.%/])',
        r'\1价格已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'([\u4e00-\u9fffA-Za-z]{2,16})\d{2,3}(?:\.\d+)?(?=后(?:完成|等待|再|才))',
        r'\1关键位突破',
        cleaned,
    )
    cleaned = re.sub(r'受\d+(?:\.\d+)?前高', '受前高', cleaned)
    cleaned = re.sub(r'@\s*\d+(?:\.\d+)?', '@成交价已隐藏', cleaned)
    cleaned = re.sub(
        r'(@成交价已隐藏)\s*[×xX*]\s*\d+(?![\d.])',
        r'\1 部分仓位',
        cleaned,
    )
    cleaned = re.sub(
        r'(@成交价已隐藏)(?:\s*/\s*\d+(?:\.\d+)?)+',
        r'\1',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:买入|卖出|加仓|减仓|清仓)[^，。；\n|（）()]{0,30})'
        r'[（(]\s*\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)+\s*[）)]',
        r'\1（成交价已隐藏）',
        cleaned,
    )
    cleaned = re.sub(
        r'\d+\s*@\s*成交价已隐藏',
        '部分仓位@成交价已隐藏',
        cleaned,
    )
    cleaned = re.sub(
        r'(?:仅)?(?:\d+(?:\s*股)?|部分仓位)\s*(?:可卖|不可卖)',
        '可卖状态已记录',
        cleaned,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])lot(?![A-Za-z0-9_])',
        '账户批次',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'次日\s*解锁(?:后)?(?:再)?',
        '次日可卖状态复核后',
        cleaned,
    )
    cleaned = re.sub(
        r'[-+]?\d+(?:\.\d+)?\s*[—~-]\s*[-+]?\d+(?:\.\d+)?\s*pcts?(?![A-Za-z0-9_])',
        '若干个百分点',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'[-+]?\d+(?:\.\d+)?\s*pcts?(?![A-Za-z0-9_])',
        '账户比例已脱敏',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])24\s*h(?:ours?)?(?![A-Za-z0-9_])|24\s*小时',
        '次日',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'((?:以|按)\s*)\d+(?:\.\d+)?(?=\s*(?:成交|买入|加仓|减仓|清仓|卖出|买|卖|减))',
        r'\1成交价已隐藏',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:成交|买入|卖出|加仓|减仓|清仓)价(?:约|为)?\s*[:：]?\s*)\d+(?:\.\d+)?',
        r'\1已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:买入|卖出|加仓|减仓|清仓)后)\s*\d+(?:\.\d+)?',
        r'\1价格已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:买|卖)(?:在|于)\s*)[-+]?\d+(?:\.\d+)?(?![\d.%/])',
        r'\1价格已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:清仓|卖出)[^，。；\n|]{0,24}[，,]\s*收盘[：:\s]+)'
        r'[-+]?\d+(?:\.\d+)?(?![\d.%/])',
        r'\1价格已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'(?<![\d.])\d{2,4}(?:\.\d+)?(?=\s*(?:买点|卖点))',
        '价格已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'(?<![\d.])\d{2,4}(?:\.\d+)?(?=\s*(?:是|为)\s*(?:脉冲后|冲高后|拉升后)?成交)',
        '价格已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'(?:从|由)\s*(?:约\s*)?[-+]?\d+(?:\.\d+)?%\s*'
        r'(?:加至|增至|提高至|提升至|降至|减至|到)\s*'
        r'(?:约\s*)?[-+]?\d+(?:\.\d+)?%',
        '账户比例已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'(\|\s*(?:当日|账户|月度|周度)?(?:盈亏|损益)\s*\|\s*)'
        r'(\*{0,2})[-+]?(?:\d{1,3}(?:,\d{3})+|\d{4,})(?=\s*[（(])',
        r'\1\2金额已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'浮盈垫\s*\d+(?:\.\d+)?\s*[><=]+\s*(?:加仓前)?成本\s*'
        r'\*{0,2}\d+(?:\.\d+)?\*{0,2}',
        '浮盈垫已核对',
        cleaned,
    )
    cleaned = re.sub(
        r'(?:预案)?硬卡\s*\*{0,2}\d+(?:\.\d+)?\*{0,2}',
        '预案关键位',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:未)?站回\s*)\*{0,2}\d+(?:\.\d+)?\*{0,2}',
        r'\1关键位',
        cleaned,
    )
    cleaned = re.sub(
        r'(?<![\d.])\d+(?:\.\d+)?'
        r'(?=\s*=\s*(?:加仓前\s*)?部分仓位加权成本)',
        '成本已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:误填|原填|更正自)\s*)\d+(?:\.\d+)?',
        r'\1成本已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'(?<![\d.])\d+(?:\.\d+)?(?=\s*在其(?:上|下))',
        '价格已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'(买入|卖出|买|卖)\s*\d{2,3}\.\d+',
        lambda match: '买入价已脱敏' if match.group(1).startswith('买') else '卖出价已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:组合|加仓|买入)?成本(?:价|线)?(?:约|为|≈)?\s*[:：]?\s*)'
        r'\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)+',
        r'\1已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:买入|卖出|加仓|减仓|清仓|买|卖|减)\s*'
        r'[\u4e00-\u9fffA-Za-z]{1,12})\d{2,4}(?:\.\d+)',
        r'\1成交价已隐藏',
        cleaned,
    )
    cleaned = re.sub(
        r'(?<![\d.])\d{2,4}\.\d+(?=\s*(?:买入|卖出|加仓|减仓|清仓|全清))',
        '成交价已隐藏',
        cleaned,
    )
    cleaned = re.sub(
        r'买入均价\s*\([^)]*\)\s*/\s*\d+(?:\.\d+)?\s*=\s*\d+(?:\.\d+)?',
        '买入均价已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:均)?成本(?:价|线)?(?:约|为|≈)?\s*[:：]?\s*)\d+(?:\.\d+)?',
        r'\1已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'(成本已脱敏)(?:\s*/\s*\d+(?:\.\d+)?)+',
        r'\1',
        cleaned,
    )
    cleaned = re.sub(
        r'(均价(?:约|为|≈)?\s*[:：]?\s*)\d+(?:\.\d+)?',
        r'\1已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'\d{2,4}(?:\.\d+)?(?=\s*(?:风险区|止损位|结构位|复核线|低点))',
        '关键位',
        cleaned,
    )
    cleaned = re.sub(
        r'(?<![\d.])\d+(?:\.\d+)?\s*[—~-]\s*\d+(?:\.\d+)?'
        r'(?=\s*(?:有)?(?:短压|压力|阻力|支撑))',
        '关键区间',
        cleaned,
    )
    # Keep inline availability and execution-process wording out of the public layer.
    cleaned = re.sub(r'T\+1状态已记录', '可卖状态已记录', cleaned, flags=re.I)
    cleaned = re.sub(
        r'(?<![A-Za-z0-9_])T\+1(?![A-Za-z0-9_])',
        '可卖状态',
        cleaned,
        flags=re.I,
    )
    if redact_internal_labels:
        cleaned = re.sub(r'门禁', '执行条件', cleaned)
        cleaned = re.sub(r'执行卡', '规则条件', cleaned)
    cleaned = re.sub(
        r'(?:票据|来源记录)\s*[:：=]?\s*\d+',
        '成交细节已隐藏',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'未获弈沐指令', '执行原因未公开', cleaned)
    cleaned = re.sub(r'票据交易记录', '成交细节已隐藏', cleaned)
    cleaned = re.sub(r'票据读取', '来源记录已隐藏', cleaned)
    cleaned = re.sub(r'票据', '来源记录', cleaned)
    cleaned = re.sub(r'FIFO关闭交易流水已隐藏', '成交细节已隐藏', cleaned, flags=re.I)
    cleaned = re.sub(r'绑定账户批次\s*交易流水已隐藏', '成交细节已隐藏', cleaned)
    cleaned = re.sub(r'账户批次', '记录已隐藏', cleaned)
    cleaned = re.sub(r'(?<![A-Za-z0-9_])FIFO(?![A-Za-z0-9_])', '成交细节', cleaned, flags=re.I)
    cleaned = re.sub(
        r'(成交细节已隐藏)(?:[，,；;、]\s*\1)+',
        r'\1',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:单票|总仓|总仓位|仓位|持仓\s+|超限)[^，。；|]{0,24}?)'
        r'[-+]?\d+(?:\.\d+)?%\s*[>≥]\s*[-+]?\d+(?:\.\d+)?%',
        r'\1账户比例已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:单票|总仓位|仓位|持仓率|持仓\s+)[^，。；|]{0,24}?)'
        r'[-+]?\d+(?:\.\d+)?%'
        r'(?=\s*(?:已|为|上限|超|基准|附近|只减|未|，|。|；|$))',
        r'\1账户比例已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:总)?仓位(?:上限)?\*{0,2}\s*[：:]\s*'
        r'(?:维持当前|维持|约为|为|盘后)?\s*)'
        r'(?:约)?\d+(?:\.\d+)?%',
        r'\1账户比例已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'(现仓\s*)(?:约)?[-+]?\d+(?:\.\d+)?%',
        r'\1账户比例已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'((?:仍)?持仓时\s*)(?:约)?[-+]?\d+(?:\.\d+)?%\s*上限',
        r'\1内部集中度上限',
        cleaned,
    )
    cleaned = re.sub(
        r'(?:约)?[-+]?\d+(?:\.\d+)?%\s*总仓(?=\s*(?:风险|上限|超限|基准))',
        '总仓账户比例已脱敏',
        cleaned,
    )
    cleaned = re.sub(
        r'(?:连亏)?持仓上限(?:为|约为)?\s*[-+]?\d+(?:\.\d+)?%',
        '持仓内部集中度上限',
        cleaned,
    )
    cleaned = re.sub(
        r'(生产端仍显示|昨日计划亦按)\s*[-+]?\d+(?:\.\d+)?%\s*(?:表述)?',
        r'\1账户规则口径',
        cleaned,
    )
    cleaned = re.sub(
        r'仓位超\s*[-+]?\d+(?:\.\d+)?%\s*(?:参考)?上限',
        '仓位超过内部集中度上限',
        cleaned,
    )
    cleaned = re.sub(r'跌超\d+(?:\.\d+)?%', '跌幅达到风险阈值', cleaned)
    cleaned = re.sub(
        r'((?:持仓|持有)复核[^。\n]{0,160}?/)\d{2,4}(?:\.\d+)?(?=[。．）)])',
        r'\1价格已脱敏',
        cleaned,
    )

    safe_lines = []
    for line in cleaned.splitlines():
        if any(marker in line for marker in (
            'Portal 今日一句话来源',
            'Portal 今日一个认知来源',
            'Portal 每日市场手记 SSOT',
        )):
            continue
        line = re.sub(
            r'^\s*(?:-\s*)?(?:T\+1|可卖状态)[：:].*$',
            '- 可卖状态以账户事实为准。',
            line,
            flags=re.I,
        )
        if re.search(r'盈亏|浮盈|亏损|浮亏|盈利|实现|成交|买入|加仓|减仓|清仓|卖出|止损|持仓|仓位|账户|试仓|暴露', line):
            line = re.sub(r'(?<!\d)\d{1,2}:\d{2}(?::\d{2})?', '盘中', line)
            line = re.sub(
                r'总资产\s*[-+]?\d+(?:\.\d+)?',
                '总资产已脱敏',
                line,
            )
            line = re.sub(
                r'收\s*[-+]?\d{2,4}(?:\.\d+)?(?![\d.%/])',
                '收 价格已脱敏',
                line,
            )
            line = re.sub(
                r'((?:盘前|盘后)?仓位[^：:]{0,20}[：:][^，。；|]{0,24}?)(?:约|为|当前)?[-+]?\d+(?:\.\d+)?%',
                r'\1账户比例已脱敏',
                line,
            )
            if re.search(r'内部账户记录|持仓复核|SSOT', line, flags=re.I):
                line = re.sub(
                    r'(?<![\d.])\d{1,6}(?:\s*\+\s*\d{1,6})+(?=\s*(?:锁|解锁|[）)]))',
                    '仓位数量已脱敏',
                    line,
                )
                line = re.sub(
                    r'(?<![\d.])\d{2,6}(?=\s*[（(])',
                    '部分仓位',
                    line,
                )
                line = re.sub(r'(?<![\d.])\d{1,2}/\d{1,2}(?![\d/])', '次日状态', line)
            if re.search(r'自选池|持仓|新开仓|加仓', line):
                line = re.sub(
                    r'((?:午盘|尾盘|收盘)[：:\s]*[-+]?\d+(?:\.\d+)?%[、,]\s*)[-+]?\d+(?:\.\d+)?',
                    r'\1价格已脱敏',
                    line,
                )
                line = re.sub(
                    r'((?:振幅)[：:]?\s*)[-+]?\d+(?:\.\d+)?\s*[-~—]\s*[-+]?\d+(?:\.\d+)?',
                    r'\1关键区间',
                    line,
                )
                line = re.sub(
                    r'([-+]?\d+(?:\.\d+)?%)[（(]\s*[-+]?\d+(?:\.\d+)?',
                    r'\1（价格已脱敏',
                    line,
                )
                line = re.sub(
                    r'((?:高点|低点|收盘价|收盘|现价|当前价)[：:]?\s*)[-+]?\d+(?:\.\d+)?(?![\d.%/])',
                    r'\1价格已脱敏',
                    line,
                )
                line = re.sub(
                    r'[-+]?\d+(?:\.\d+)?(?=\s*(?:收(?:平|盘)|翻(?:红|绿)))',
                    '价格已脱敏',
                    line,
                )
                line = re.sub(
                    r'((?:新开仓|加仓|买入)[^，。；|]{0,24}[（(]\s*)'
                    r'[-+]?\d+(?:\.\d+)?(?![\d.%/])',
                    r'\1价格已脱敏',
                    line,
                )
                line = re.sub(
                    r'(?<![A-Za-z0-9_])T\s*出\s*'
                    r'(?:\d{1,3}(?:,\d{3})+|\d+)(?![\d.])',
                    'T 出部分仓位',
                    line,
                )
                line = re.sub(
                    r'(@成交价已隐藏)\s*[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?![\d.])',
                    r'\1 部分仓位',
                    line,
                )
                line = re.sub(
                    r'(?<![\u4e00-\u9fffA-Za-z])持仓\s*'
                    r'(?:数量|股数)?\s*\d+(?![\d.%])',
                    '持仓数量已脱敏',
                    line,
                )
                line = re.sub(
                    r'((?:突破|跌破|站稳|站上|失守|收复|守住|考验)\s*)'
                    r'[-+]?\d+(?:\.\d+)?(?=\s*(?:后|回踩|附近|上方|下方|未破|失守))',
                    r'\1关键位',
                    line,
                )
            line = re.sub(
                r'(?:当前|目前|盘后仓位|账户比例|仓位比例)\s*'
                r'(?:约|为|当前)?\s*[-+]?\d+(?:\.\d+)?%',
                '账户比例已脱敏',
                line,
            )
            line = re.sub(
                r'((?:持仓|加仓|买入|卖出|成交)[^，。；|]{0,32}[-+]?\d+(?:\.\d+)?%\s*[（(]\s*)'
                r'\d+(?:\.\d+)?(?=\s*[，,）)])',
                r'\1价格已脱敏',
                line,
            )
            line = re.sub(
                r'((?:午盘|尾盘|日内低点|买入后(?:五分钟K线)?最低(?:跌至)?|成交后最低)[：:]?\s*)'
                r'(?!(?:\d{2,4}(?:\.\d+)?)(?:%|家|只|/|→|飙至))'
                r'\d{2,4}(?:\.\d+)?',
                r'\1价格已脱敏',
                line,
            )
            line = re.sub(
                r'(MA\d+\s*[(=:]?\s*)\d{2,4}(?:\.\d+)?',
                r'\1关键位',
                line,
            )
            line = re.sub(
                r'(关键位)\s*[<>]\s*\d+(?:\.\d+)?',
                r'\1附近',
                line,
            )
            line = re.sub(
                r'(?<![\d.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*元',
                '金额已脱敏',
                line,
            )
            line = re.sub(
                r'(?<![\d.])[-+]?\d+(?:\.\d+)?\s*万(?!亿)',
                '金额已脱敏',
                line,
            )
            line = re.sub(
                r'(?:约)?\d+(?:\.\d+)?%\s*(?:账户|仓位)',
                '账户比例已脱敏',
                line,
            )
            line = re.sub(
                r'((?:\*\*)?仓位(?:\*\*)?\s*[：:]?\s*(?:维持|约为|为|盘后)?\s*)(?:约)?\d+(?:\.\d+)?%',
                r'\1账户比例已脱敏',
                line,
            )
            line = re.sub(
                r'((?:浮盈|锁盈|已?实现|盈亏|亏损|盈利|止损)(?:为|约|[:：=])?\s*[（(]?)'
                r'[-+]?(?:\d{1,3}(?:,\d{3})+|\d{4,})(?!\d)',
                r'\1金额已脱敏',
                line,
            )
        safe_lines.append(line)
    return '\n'.join(safe_lines)


def public_position_summary(position):
    """Expose position state without publishing names, quantities, or costs."""
    if not position or '空仓' in str(position):
        return '空仓'
    return '持仓状态已记录'


def sanitize_public_review_cell(header, value, position_row=False):
    """Apply header-aware redaction to sensitive review table fields."""
    header = str(header or '')
    raw_value = str(value or '')
    if header in ('时间', '成交时间') and re.fullmatch(
        r'(?:\d{4}-\d{1,2}-\d{1,2}\s+)?\d{1,2}:\d{2}(?::\d{2})?',
        str(value or '').strip(),
    ):
        return '盘中'
    if header == '价格':
        return '已脱敏'
    if header == '现价':
        return '已脱敏'
    if any(key in header for key in ('成本', '成交价', '买入价', '卖出价', '浮盈/股')):
        return '已脱敏'
    if any(key in header for key in ('盈亏', '损益')):
        raw_value = str(value or '').strip()
        if re.fullmatch(r'[-+]?\d+(?:\.\d+)?%', raw_value):
            return raw_value
        if re.search(r'\d', raw_value):
            return '金额已脱敏'
    if header in ('数量', '现持仓', '持仓数量') or header.endswith('数量') or any(
        key in header for key in ('股数', '可卖数量', '可卖量')
    ):
        return '已脱敏'
    if header == '仓位':
        return '已脱敏'
    if 'T+1可卖' in header or '可卖状态' in header:
        return '按账户事实复核'
    if re.search(r'(?:理论)?可卖|可卖(?:数量|量)', header):
        return '已脱敏'
    if re.search(r'\d{1,2}/\d{1,2}[^|]{0,12}收盘|收盘[^|]{0,12}\d{1,2}/\d{1,2}', header):
        return '已脱敏'
    if '止损' in header:
        return '关键风险位（已脱敏）'
    if any(key in header for key in ('触发', '失效')) and (
        re.search(r'买入|卖出|加仓|减仓|清仓|止损|降险|补仓|提高暴露|先减|再减', raw_value)
        or re.search(r'\d+(?:\.\d+)', raw_value)
    ):
        return '风险条件已记录（具体阈值已脱敏）'
    if header == '今日检查' and (
        re.search(r'\d{1,3}\.\d+[^，。；|]{0,12}(?:突破|收复|失守|守住|回踩)', raw_value)
        or len(re.findall(r'\d+(?:\.\d+)', raw_value)) >= 2
    ):
        return '价格/结构确认条件已记录（具体阈值已脱敏）'
    contextual_value = f'持仓复核：{raw_value}' if position_row else raw_value
    sanitized = sanitize_public_review_text(contextual_value)
    if position_row:
        sanitized = re.sub(r'^持仓复核：', '', sanitized)
        sanitized = re.sub(
            r'((?:收盘|收盘价|现价|当前价|成交价|买入价|卖出价)'
            r'(?:约|为|≈|[：:]|\s)*)[-+]?\d+(?:\.\d+)?(?![\d.%/])',
            r'\1价格已脱敏',
            sanitized,
        )
        sanitized = re.sub(
            r'(MA\d+\s*(?:约|=|:|：)?\s*)\d+(?:\.\d+)?(?![\d.%/])',
            r'\1关键位',
            sanitized,
        )
        if header not in ('标的', '代码', '名称', '板块', '方向', '窗口', '今日定位', '阶段', '角色'):
            sanitized = re.sub(
                r'(?<![\d.])[-+]?\d{1,4}\.\d+(?![\d.%/])',
                '价格已脱敏',
                sanitized,
            )
            sanitized = re.sub(
                r'((?:今日|当日|日内|浮盈|浮亏|盈亏|实现|亏损|盈利)[^，。；|]{0,16}?)'
                r'[-+]?(?:\d{1,3}(?:,\d{3})+|\d{3,})(?![\d.%])',
                r'\1金额已脱敏',
                sanitized,
            )
    return sanitized


# ── HTML generators ──

def html_topbar(fm):
    """Generate the topbar with meta chips."""
    weekday = fm.get('weekday', '')
    emo_raw = fm.get('情绪值', '--')
    emo = pct_text(emo_raw)
    sh_idx = fm.get('上证指数', '--')
    sh_pct_raw = fm.get('上证涨幅', '--')
    sh_pct = pct_text(sh_pct_raw, signed=True)
    zt = fm.get('涨停家数', '--')
    dt = fm.get('跌停家数', '--')
    pos = public_position_summary(fm.get('盘后持仓', '空仓'))

    emo_val = numeric_value(emo_raw)
    emo_chip = 'red' if emo_val is not None and emo_val < 25 else ('amber' if emo_val is not None and emo_val < 45 else 'green')
    sh_chip = 'red' if sh_pct.startswith('+') else 'green'

    return f"""<div class="topbar">
  <a id="back-home" class="back" href="../index.html#reviews">← 返回首页</a>
  <div class="title">{fm.get('date','')} {weekday} 复盘笔记</div>
  <div class="meta">
    <span class="chip {emo_chip}">情绪 {emo}</span>
    <span class="chip {sh_chip}">上证 {sh_idx} {sh_pct}</span>
    <span class="chip blue">{zt}涨停 / {dt}跌停</span>
    <span class="chip purple">持仓 {pos}</span>
    <span class="chip green">终稿 (红蓝对抗完成)</span>
  </div>
</div>"""


def html_table(headers, rows, cell_fn=None):
    """Render a table. cell_fn(key, value) can transform cell content."""
    if not headers or not rows:
        return ""
    position_table = any(
        re.search(r'数量|成本|现持仓|持仓数量|(?:理论)?可卖|可卖(?:数量|量)', str(header))
        for header in headers
    )
    thead = '<thead><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr></thead>'
    tbody = '<tbody>'
    for row in rows:
        position_row = any(
            '持仓' in str(row.get(key, ''))
            for key in ('窗口', '今日定位', '方向', '阶段', '角色')
        ) or any(
            re.search(r'(?:持仓\s*\d|成本\s*\d|收盘\s*\d)', str(value))
            for value in row.values()
        ) or ('当前事实' in headers and '今日结论' in headers) or position_table
        tbody += '<tr>'
        for h in headers:
            if h == '收盘价' and position_row:
                v = '已脱敏'
            else:
                v = sanitize_public_review_cell(h, row.get(h, ''), position_row=position_row)
            if cell_fn:
                v = cell_fn(h, v)
            tbody += f'<td>{v}</td>'
        tbody += '</tr>'
    tbody += '</tbody>'
    return f'<div class="tw"><table>{thead}{tbody}</table></div>'


def html_emotion_board(headers, rows, fm=None):
    """Render 表2 情绪高标 as scan-friendly cards instead of a very wide table."""
    if not headers or not rows:
        return ""

    metric_header = next(
        (h for h in headers if h in ("指标", "观察维度")),
        headers[0],
    )
    stages = [h for h in headers if h not in (metric_header, "门槛")]
    row_by_metric = {row.get(metric_header, ""): row for row in rows}

    def clean(value):
        s = str(value or "").strip().replace("**", "")
        return s if s else "—"

    def safe(value):
        return html_escape(clean(value), quote=False)

    def meaningful(value):
        return clean(value) not in ("—", "TBD", "...")

    def metric_value(metric, stage_preference=("收盘", "尾盘", "午盘", "早盘", "竞价")):
        row = row_by_metric.get(metric, {})
        for stage in stage_preference:
            value = row.get(stage)
            if meaningful(value):
                return clean(value)
        fm_keys = {
            "赚钱效应": ("赚钱效应",),
            "涨停收益": ("昨日涨停收益",),
            "连板收益": ("昨日连板收益",),
            "封板率": ("封板率",),
            "炸板率": ("炸板率",),
            "一进二晋级率": ("一进二晋级率",),
            "三进四晋级率": ("三进四晋级率",),
            "竞价验证结论": ("竞价验证结论",),
        }.get(metric, ())
        for key in fm_keys:
            value = (fm or {}).get(key)
            if meaningful(value):
                return clean(value)
        return "—"

    def kpi_class(value):
        s = clean(value)
        if "好" in s or "A好" in s or "3.92" in s:
            return "good"
        if "0.0" in s or "8.86" in s or "73.17" in s or "⚠️" in s:
            return "bad"
        if "26.83" in s or "1.98" in s or "12.36" in s:
            return "warn"
        return ""

    kpis = [
        ("赚钱效应", metric_value("赚钱效应")),
        ("涨停收益", metric_value("涨停收益")),
        ("连板收益", metric_value("连板收益")),
        ("封板率", metric_value("封板率")),
        ("炸板率", metric_value("炸板率")),
        ("一进二", metric_value("一进二晋级率")),
        ("三进四", metric_value("三进四晋级率")),
    ]
    conclusion = metric_value("竞价验证结论")
    html = '<div class="emotion-board">'
    html += '<div class="emotion-summary-grid">'
    for label, value in kpis:
        html += (
            f'<div class="emotion-kpi {kpi_class(value)}">'
            f'<div class="klabel">{safe(label)}</div><div class="kval">{cell_color(label, safe(value))}</div></div>'
        )
    html += '</div>'
    if meaningful(conclusion):
        html += (
            f'<div class="emotion-conclusion">'
            f'<span class="emotion-conclusion-label">结论：</span>'
            f'<span class="emotion-conclusion-text">{safe(conclusion)}</span>'
            f'</div>'
        )

    display_rows = [row for row in rows if row.get(metric_header, "") != "竞价验证结论"]
    major_metrics = {"梯队", "最高板/次高板"}
    html += '<div class="emotion-stage-grid">'
    for stage in stages:
        html += f'<div class="emotion-stage"><div class="stage-title">{stage}</div>'
        stage_has_data = False
        for row in display_rows:
            metric = row.get(metric_header, "")
            value = row.get(stage, "")
            if not meaningful(value):
                continue
            stage_has_data = True
            major = " major" if metric in major_metrics else ""
            html += (
                f'<div class="emotion-row{major}">'
                f'<span class="rlabel">{safe(metric)}</span><span class="rval">{cell_color(metric, safe(value))}</span></div>'
            )
        if not stage_has_data:
            html += '<div class="emotion-row"><span class="rlabel">记录</span><span class="rval">—</span></div>'
        html += '</div>'
    html += '</div>'

    thresholds = [(row.get(metric_header, ""), clean(row.get("门槛", ""))) for row in display_rows if meaningful(row.get("门槛", ""))]
    if thresholds:
        html += '<div class="emotion-thresholds"><div class="threshold-title">门槛速查</div><div class="threshold-grid">'
        for metric, threshold in thresholds:
            html += f'<div class="threshold-item"><strong>{safe(metric)}</strong>{safe(threshold)}</div>'
        html += '</div></div>'
    html += '</div>'
    return html


def cell_color(header, value):
    """Color-code table cells based on content."""
    if not value or value in ('—', 'TBD', ''):
        return value
    s = str(value)
    # Strip markdown bold markers
    s = s.replace('**', '')
    # positive/negative percentages
    if header in ('涨幅', '涨跌幅', '竞价%', '早盘%', '午盘%', '收盘%', '浮盈%',
                   '上证(%)', '上证涨幅', '板块涨跌幅'):
        if s.startswith('+') or (s.replace('.','').replace('%','').lstrip('-').isdigit() and float(s.replace('%','')) > 0):
            return f'<span class="up">{s}</span>'
        elif s.startswith('-'):
            return f'<span class="down">{s}</span>'
    # 主力 net flow
    if header in ('主力', '收盘主力', '主力(问财)', '主力趋势'):
        if '🔥' in s:
            s_clean = s.replace('🔥','')
            if s_clean.startswith('+') or (s_clean.replace('.','').replace('亿','').lstrip('-').isdigit() and not s_clean.startswith('-')):
                return f'<span class="up">{s}</span>'
            return f'<span class="down">{s}</span>'
        if s.startswith('+'):
            return f'<span class="up">{s}</span>'
        if s.startswith('-'):
            return f'<span class="down">{s}</span>'
    # 换手率
    if header == '换手' and s.endswith('%'):
        try:
            v = float(s.replace('%',''))
            if v > 20:
                return f'<span style="color:var(--red);font-weight:600">{s}</span>'
        except:
            pass
    return s


def html_section_header(id_, label, subtitle=""):
    """Collapsible section header."""
    cnt_html = f'<span class="cnt">{subtitle}</span>' if subtitle else ''
    return f"""<div class="section" id="{id_}">
<div class="sh" onclick="this.classList.toggle('collapsed');this.nextElementSibling.classList.toggle('hide')">
  <span class="tog">▼</span> {label}{cnt_html}
</div>
<div class="sb">"""


def html_section_footer():
    return '</div>\n</div>'


def html_subheading(text, id_=None):
    id_attr = f' id="{id_}"' if id_ else ''
    return f'<div class="sh3"{id_attr}>{text}</div>'


REVIEW_PLACEHOLDER_RE = re.compile(r'\[待弈沐补充(?:盘感)?\]')


def strip_review_placeholders(text):
    """Remove source-note placeholders that should not appear in portal pages."""
    value = REVIEW_PLACEHOLDER_RE.sub('', str(text or ''))
    value = re.sub(r'[（(]待弈沐裁决[）)]', '', value)
    value = value.replace('待定', '尚未确认')
    return value.strip()


def md_text_to_html(text):
    """Convert markdown text block to HTML, preserving paragraphs/lists/quotes."""
    text = strip_review_placeholders(text)
    if not text:
        return ""
    lines = text.strip().split('\n')
    out = []
    i = 0
    in_list = False
    in_quote = False

    while i < len(lines):
        line = lines[i].strip()

        # Blockquote
        if line.startswith('>'):
            if not in_quote:
                out.append('<div class="si">')
                in_quote = True
            content = line.lstrip('> ').strip()
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
            out.append(f'{content}<br>')
            i += 1
            continue
        elif in_quote:
            out.append('</div>')
            in_quote = False

        # Horizontal rule
        if line == '---':
            out.append('<hr class="divider">')
            i += 1
            continue

        # Skip markdown table rows (they're handled by extract_tables)
        if re.match(r'^\|.*\|$', line):
            i += 1
            continue

        # Empty line
        if not line:
            if in_list:
                out.append('</ol>')
                in_list = False
            i += 1
            continue

        # Numbered list item (must start at beginning of line with exactly "N. ")
        m = re.match(r'^(\d+)\.\s+(.+)', line)
        if m and not re.match(r'^\d+\.\s*\*\*\[', line):
            if not in_list:
                out.append('<ol class="tight-list">')
                in_list = True
            item = m.group(2)
            item = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', item)
            out.append(f'<li>{item}</li>')
            i += 1
            continue

        # Heading
        m = re.match(r'^#{2,5}\s+(.+)', line)
        if m:
            if in_list:
                out.append('</ol>')
                in_list = False
            level = len(line) - len(line.lstrip('#'))
            cls = 'sh2' if level <= 3 else 'sh3'
            h_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', m.group(1))
            out.append(f'<div class="{cls}">{h_text}</div>')
            i += 1
            continue

        # Regular paragraph line
        if in_list:
            out.append('</ol>')
            in_list = False
        if re.match(r'^\*\*[^*]+\*\*[：:]$', line):
            i += 1
            continue
        para = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
        para = re.sub(r'`([^`]+)`', r'<code>\1</code>', para)
        out.append(f'<div class="para">{para}</div>')
        i += 1

    if in_list:
        out.append('</ol>')
    if in_quote:
        out.append('</div>')

    return '\n'.join(out)


def md_inline_to_html(text):
    """Render a short markdown-ish phrase safely inside custom cards."""
    value = html_escape(strip_review_placeholders(text), quote=False)
    value = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', value)
    return value


def normalize_node_label(label):
    """Keep long node-note labels compact enough for the left rail."""
    label = label.strip()
    aliases = [
        ('说明', '说明'),
        ('结论', '结论'),
        ('持仓', '持仓'),
        ('账户', '账户'),
        ('板块', '板块'),
        ('自选池', '自选池'),
        ('连板', '连板'),
        ('弈沐操作', '操作'),
        ('风险', '风险'),
        ('午后关注', '关注'),
        ('明日预案', '预案'),
    ]
    for prefix, compact in aliases:
        if label.startswith(prefix):
            return compact
    return label[:8]


def split_node_detail(line):
    """Parse both bold-label and plain-label node-note rows."""
    line = line.strip()
    if line.startswith('-'):
        line = line[1:].strip()
    if re.match(r'^\d+[.)、]\s+', line):
        return "记录", line
    m = re.match(r'^(弈沐操作)(\[[^\]]+\])?[：:]\s*(.+)$', line)
    if m:
        ticket = f'{m.group(2)} ' if m.group(2) else ''
        return "操作", f'{ticket}{m.group(3).strip()}'
    m = re.match(r'^\*\*(.+?)\*\*[：:]\s*(.+)$', line)
    if m:
        return normalize_node_label(m.group(1)), m.group(2).strip()
    m = re.match(r'^([^：:\n]{2,28})[：:]\s*(.+)$', line)
    if m:
        return normalize_node_label(m.group(1)), m.group(2).strip()
    return "记录", line


def html_node_notes(body):
    """Render 节点说明 as one readable card per market phase."""
    marker_re = re.compile(
        r'^\*\*(竞价|早盘|午盘|尾盘|收盘)(?:[（(][^）)]*[）)])?\*\*(?:[（(][^）)]*[）)])?[：:]?\s*$',
        re.MULTILINE,
    )
    matches = list(marker_re.finditer(body))
    if not matches:
        return f'<div class="si">{md_text_to_html(body.strip())}</div>'

    phase_times = {
        '竞价': '09:25',
        '早盘': '10:00',
        '午盘': '11:30',
        '尾盘': '14:30',
        '收盘': '15:00',
    }
    html = '<div class="node-timeline">'
    for idx, match in enumerate(matches):
        phase = match.group(1)
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        segment = body[start:end].strip()
        if not segment:
            continue

        details = []
        for raw_line in segment.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if re.fullmatch(r'-{2,}', line):
                continue
            details.append(split_node_detail(line))

        time_label = phase_times.get(phase, '')
        html += (
            f'<article class="node-note-card" data-phase="{md_inline_to_html(phase)}">'
            f'<div class="node-phase"><span>{md_inline_to_html(phase)}</span><em>{time_label}</em></div>'
        )
        if details:
            for label, copy in details:
                html += (
                    '<div class="node-detail">'
                    f'<div class="node-label">{md_inline_to_html(label)}</div>'
                    f'<div class="node-copy">{md_inline_to_html(copy)}</div>'
                    '</div>'
                )
        else:
            html += '<div class="node-detail"><div class="node-label">记录</div><div class="node-copy">—</div></div>'
        html += '</article>'
    html += '</div>'
    return html


def parse_plain_numbered_sentence_lessons(text):
    """Parse `1. 原则。证据` cognition items used by finalized ReviewNotes."""
    items = []
    for match in re.finditer(
        r'^\d+\.\s+(?P<item>.*?)(?=^\d+\.\s+|^#{2,5}\s+|^---\s*$|\Z)',
        text,
        re.MULTILINE | re.DOTALL,
    ):
        raw = match.group("item").strip()
        sentence = re.match(r'(?P<title>[^。！？\n]+)[。！？]\s*(?P<body>.*)', raw, re.DOTALL)
        if not sentence or not sentence.group("body").strip():
            sentence = re.match(r'(?P<title>[^；;\n]+)[；;]\s*(?P<body>.*)', raw, re.DOTALL)
        if not sentence:
            continue
        title = sentence.group("title").strip()
        body = sentence.group("body").strip()
        if title and body:
            items.append({"kind": "认知", "title": title, "body": body})
    return items


def html_lesson_cards(text):
    """Render §二 心得与教训 as type-coded cards."""
    item_re = re.compile(
        r'^\d+\.\s+\*\*\[(?P<kind>[^\]]+)\]\s*(?P<title>.+?)\*\*\s*(?:[—-]\s*)?(?P<body>.*?)(?=\n\d+\.\s+\*\*\[|\Z)',
        re.MULTILINE | re.DOTALL,
    )
    items = list(item_re.finditer(text))
    if not items:
        plain_tagged = list(re.finditer(
            r'^\d+\.\s+\[(?P<kind>[^\]]+)\]\s*(?P<title>.+?)\s*[—-]\s*(?P<body>.*?)(?=^\d+\.\s+\[|^#{2,5}\s+|^---\s*$|\Z)',
            text,
            re.MULTILINE | re.DOTALL,
        ))
        if plain_tagged:
            before = text[:plain_tagged[0].start()].strip()
            after = text[plain_tagged[-1].end():].strip()
            html = ""
            if before:
                html += f'<div class="si">{md_text_to_html(before)}</div>'
            html += render_lesson_card_grid([
                {
                    "kind": item.group("kind").strip(),
                    "title": item.group("title").strip(),
                    "body": item.group("body").strip(),
                }
                for item in plain_tagged
            ])
            if after:
                html += f'<div class="si">{md_text_to_html(after)}</div>'
            return html
        untagged = list(re.finditer(
            r'^(?:\d+\.\s+\*\*(?P<title_a>.+?)\*\*|\*\*\d+\.\s+(?P<title_b>.+?)\*\*)\s*\n+(?P<body>.*?)(?=^(?:\d+\.\s+\*\*|\*\*\d+\.)|^#{2,5}\s+|\Z)',
            text,
            re.MULTILINE | re.DOTALL,
        ))
        if untagged:
            before = text[:untagged[0].start()].strip()
            after = text[untagged[-1].end():].strip()
            html = ""
            if before:
                html += f'<div class="si">{md_text_to_html(before)}</div>'
            html += render_lesson_card_grid([
                {
                    "kind": "认知",
                    "title": (item.group("title_a") or item.group("title_b")).strip(),
                    "body": item.group("body").strip(),
                }
                for item in untagged
            ])
            if after:
                html += f'<div class="si">{md_text_to_html(after)}</div>'
            return html
        plain_numbered = parse_plain_numbered_sentence_lessons(text)
        if plain_numbered:
            return render_lesson_card_grid(plain_numbered)
        return f'<div class="si">{md_text_to_html(text.strip())}</div>'

    return render_lesson_card_grid([
        {
            "kind": item.group("kind").strip(),
            "title": item.group("title").strip(),
            "body": item.group("body").strip(),
        }
        for item in items
    ])


def render_lesson_card_grid(items):
    class_by_kind = {"认知": "cognition", "教训": "warning", "议题": "topic", "流程缺陷": "warning"}
    type_by_kind = {"认知": "今日提炼", "教训": "风险校正", "议题": "待验证问题", "流程缺陷": "流程校正"}
    html = '<div class="lesson-grid">'
    for item in items:
        kind = item["kind"]
        title = item["title"]
        body = item["body"]
        css = class_by_kind.get(kind, "cognition")
        action = infer_lesson_action(kind, title, body)
        html += (
            f'<article class="lesson-card {css}">'
            '<div class="lesson-head">'
            f'<div class="lesson-tag">{md_inline_to_html(kind)}</div>'
            f'<div class="lesson-type">{type_by_kind.get(kind, "认知提炼")}</div>'
            '</div>'
            f'<div class="lesson-label">可复用原则</div>'
            f'<div class="lesson-principle">{md_inline_to_html(title)}</div>'
            f'<div class="lesson-label">当日证据</div>'
            f'<div class="lesson-evidence">{md_text_to_html(body)}</div>'
            f'<div class="lesson-label">下次动作</div>'
            f'<div class="lesson-action">{md_inline_to_html(action)}</div>'
            '</article>'
        )
    html += '</div>'
    return html


def infer_lesson_action(kind, title, body):
    """Convert a daily lesson into a conservative next-action prompt."""
    source = f"{title} {body}"
    if kind == "议题":
        return "保留为观察问题，次日用板块、中军和资金数据重新验证。"
    if kind == "教训":
        return "下次出手前先停顿复核预案、窗口、量能和失效点，缺一项就降级处理。"
    if re.search(r"加速|追高|超买|高潮", title):
        return "加速段只做持仓管理，不把情绪高潮当新增买点。"
    if re.search(r"缩量|突破|量价|承接|回踩", title):
        return "把量价确认和承接作为前置条件，次日继续验证是否延续。"
    if re.search(r"建仓|买点|开仓|选股|板块|个股", title):
        return "开仓前先确认板块强度、对标标的、买点窗口和失效点，再定个股。"
    if re.search(r"未盯盘|过程缺失|事实层|source_gaps|盘中授权|门禁", source):
        return "先补事实层和缺口清单，不用收盘结果倒推盘中授权，次日交给实时门禁重新裁决。"
    if re.search(r"账户|批次|对账|数量|冲突", source):
        return "先核对账户事实和基础数量，冲突解除前主动交易动作降级为观察/核对。"
    if re.search(r"卖|清仓|止盈|锁利|减仓|涨停次日|不赌|转弱", source):
        return "触发高开放量、转弱或分歧信号时，先分批锁利或降风险，再看承接。"
    if re.search(r"建仓|买点|开仓|选股|板块|方向|个股", source):
        return "开仓前先确认板块强度、对标标的、买点窗口和失效点，再定个股。"
    if re.search(r"缩量|突破|量价|承接|回踩", source):
        return "把量价确认和承接作为前置条件，次日继续验证是否延续。"
    if re.search(r"犹豫|执行|纪律|理由", source):
        return "信号触发后按预案执行，复盘只评估规则质量，不倒果为因。"
    return "下次交易前把这条转成检查项，先验信号，再决定动作。"


def md_text_with_tables_to_html(text):
    """Convert markdown text while preserving table position."""
    chunks = []
    text_lines = []
    table_lines = []

    def flush_text():
        nonlocal text_lines
        rendered = md_text_to_html('\n'.join(text_lines).strip())
        if rendered:
            chunks.append(rendered)
        text_lines = []

    def flush_table():
        nonlocal table_lines
        headers, rows = parse_md_table('\n'.join(table_lines))
        if headers and rows:
            chunks.append(html_table(headers, rows, cell_color))
        table_lines = []

    for line in text.split('\n'):
        if re.match(r'^\|.*\|$', line.strip()):
            flush_text()
            table_lines.append(line)
        else:
            if table_lines:
                flush_table()
            text_lines.append(line)

    if table_lines:
        flush_table()
    flush_text()
    return '\n'.join(chunks)


def split_red_team_rounds(text):
    """Split red-team debate text by Round markers.

    Supports both standard headings (`### Round 1 ...`) and the older
    blockquote marker style (`> 洋米 Round 1 — ...`).
    """
    round_bodies = {}
    current_round = None
    current_lines = []

    def flush():
        nonlocal current_lines
        if current_round:
            body = '\n'.join(current_lines).strip()
            if body:
                round_bodies[current_round] = body
        current_lines = []

    for raw_line in text.split('\n'):
        stripped = raw_line.strip()
        heading_match = re.match(r'^###\s+(Round\s+[123])\s*(?:[：:—-].*)?$', stripped)
        quote_match = re.match(r'^>\s*.*\b(Round\s+[123])\b.*$', stripped)
        marker = heading_match or quote_match

        if marker:
            flush()
            current_round = marker.group(1)
            continue

        if current_round:
            current_lines.append(raw_line)

    flush()
    return round_bodies


# ── Section parsers ──

def parse_s0(text, label='昨日预案'):
    """Parse §〇 plan or operation-guide content."""
    subtitle = '昨日终审定稿' if label == '昨日预案' else '公开操作边界'
    html = html_section_header("s0", f"第〇部分 · {label}", subtitle)
    html += md_text_with_tables_to_html(text)
    html += html_section_footer()
    return html


def find_h3_blocks(text):
    """Split text by ### headings. Returns list of (heading, body_text)."""
    blocks = []
    pattern = r'^### (.+)$'
    lines = text.split('\n')
    i = 0
    current_heading = None
    current_body = []
    while i < len(lines):
        m = re.match(pattern, lines[i])
        if m:
            if current_heading is not None:
                blocks.append((current_heading, '\n'.join(current_body)))
            current_heading = m.group(1).strip()
            current_body = []
        elif current_heading is not None:
            current_body.append(lines[i])
        i += 1
    if current_heading is not None:
        blocks.append((current_heading, '\n'.join(current_body)))
    return blocks


def heading_has(heading, keyword):
    """Check if heading contains keyword (substring match)."""
    return keyword in heading


def parse_s1(text, fm=None):
    """Parse §一 当日复盘."""
    html = html_section_header("s1", "§一 · 当日复盘", "")

    blocks = find_h3_blocks(text)
    if not blocks:
        html += html_section_footer()
        return html

    # Process blocks in order
    for heading, body in blocks:
        body = body.strip()
        if not body:
            continue

        # Skip empty or template placeholder rows
        tables_raw = extract_tables(body)
        tables = []
        for t in tables_raw:
            h, r = parse_md_table(t)
            # Filter out template placeholder rows
            r = [row for row in r if row.get(list(row.keys())[0] if row else '', '') not in ('...', 'TBD', 'N板', 'N%')]
            if h and r:
                tables.append((h, r))

        # ── Route to appropriate renderer ──
        h = heading

        if heading_has(h, '大盘全景') or heading_has(h, '表1'):
            if tables:
                html += html_subheading("📊 表1：大盘全景", "s1a")
                html += html_table(*tables[0], cell_fn=cell_color)

        elif heading_has(h, '情绪高标') or heading_has(h, '表2'):
            if tables:
                html += html_subheading("📈 表2：情绪高标", "s1b")
                html += html_emotion_board(*tables[0], fm=fm)

        elif heading_has(h, '节点说明'):
            html += html_subheading("🔍 节点说明", "s1c")
            html += html_node_notes(body)

        elif heading_has(h, '涨停结构'):
            if tables:
                html += html_subheading("🏗️ 涨停结构", "s1d")
                html += html_table(*tables[0], cell_fn=cell_color)

        elif heading_has(h, '连板股') and not heading_has(h, '自选'):
            if tables:
                html += html_subheading("🔗 连板股")
                html += html_table(*tables[0], cell_fn=cell_color)

        elif heading_has(h, '自选池表现'):
            html += html_subheading("🎯 当日自选池表现", "s1e")
            # Find sector sub-headings in body text (standalone **bold** lines, not inline in tables)
            sector_blocks = re.split(r'^\*\*(.+?)\*\*\s*$', body, flags=re.MULTILINE)
            si = 1
            while si < len(sector_blocks):
                sname = sector_blocks[si].strip()
                sbody = sector_blocks[si+1] if si+1 < len(sector_blocks) else ""
                stables = extract_tables(sbody)
                for st in stables:
                    sh, sr = parse_md_table(st)
                    sr = [row for row in sr if row.get(list(row.keys())[0] if row else '', '') not in ('...',)]
                    if sh and sr:
                        html += f'<div class="sh3" style="font-size:14px">{sname}</div>'
                        html += html_table(sh, sr, cell_color)
                si += 2

        elif heading_has(h, '持仓与交易'):
            html += html_subheading("💰 持仓与交易", "s1f")
            for hdr, rows in tables:
                html += html_table(hdr, rows, cell_color)

        elif heading_has(h, '账户风控'):
            if tables:
                html += html_subheading("🛡️ 账户风控")
                html += html_table(*tables[0], cell_fn=cell_color)

        elif heading_has(h, '风格检测'):
            if tables:
                html += html_subheading("📐 风格检测", "s1g")
                html += html_table(*tables[0], cell_fn=cell_color)

        elif heading_has(h, '卖出追踪'):
            if tables:
                html += html_subheading("📤 卖出追踪")
                html += html_table(*tables[0], cell_fn=cell_color)

        elif heading_has(h, '趋势持仓复盘'):
            if tables:
                html += html_subheading("📈 趋势持仓复盘", "s1h")
                html += html_table(*tables[0], cell_fn=cell_color)

        elif heading_has(h, '窗口操作记录'):
            if tables:
                html += html_subheading("🪟 窗口操作记录", "s1i")
                html += html_table(*tables[0], cell_fn=cell_color)

        elif heading_has(h, '预期差'):
            # Render as text
            html += html_subheading("🎭 预期差与盘感")
            html += f'<div class="si">{md_text_to_html(body)}</div>'

        elif heading_has(h, '一句话结论'):
            html += html_subheading("💡 一句话结论", "s1j")
            html += f'<div class="sbx">{md_text_to_html(body.strip())}</div>'

    html += html_section_footer()
    return html


def parse_s2(text):
    """Parse §二 心得与教训."""
    html = html_section_header("s2", "§二 · 心得与教训", "")
    html += html_lesson_cards(text)
    html += html_section_footer()
    return html


def parse_s3(text):
    """Parse §三 次日预案."""
    html = html_section_header("s3", "§三 · 次日预案", "")

    # Extract key metadata lines
    style_line = re.search(r'\*\*风格分数\*\*[：:]\s*(.+)', text)
    alloc_line = re.search(r'\*\*资金分配\*\*[：:]\s*(.+)', text)
    cap_line = re.search(r'\*\*总仓位上限\*\*[：:]\s*(.+)', text)
    tone_line = re.search(r'\*\*总基调\*\*[：:]\s*(.+)', text)
    why_line = re.search(r'\*\*为什么\*\*[：:]\s*(.+)', text)
    expect_line = re.search(r'\*\*基准预期\*\*[：:]\s*(.+)', text)

    html += '<div class="stats-grid">'
    if style_line: html += f'<div class="stat-card"><div class="lbl">风格</div><div class="val amber">{style_line.group(1)[:30]}</div></div>'
    if alloc_line: html += f'<div class="stat-card"><div class="lbl">资金分配</div><div class="val">{alloc_line.group(1)[:30]}</div></div>'
    if cap_line: html += f'<div class="stat-card"><div class="lbl">仓位上限</div><div class="val amber">{cap_line.group(1)[:20]}</div></div>'
    html += '</div>'

    summary_parts = []
    if tone_line: summary_parts.append(f'<strong>总基调</strong>：{tone_line.group(1)}')
    if why_line: summary_parts.append(f'<strong>为什么</strong>：{why_line.group(1)}')
    if expect_line: summary_parts.append(f'<strong>基准预期</strong>：{expect_line.group(1)}')
    if summary_parts:
        html += f'<div class="sbx warn">{"<br>".join(summary_parts)}</div>'

    # Process ### blocks
    blocks = find_h3_blocks(text)
    for heading, body in blocks:
        body = body.strip()
        if not body:
            continue
        tables_raw = extract_tables(body)
        tables = []
        for t in tables_raw:
            hdr, rows = parse_md_table(t)
            rows = [r for r in rows if r.get(list(r.keys())[0] if r else '', '') not in ('...',)]
            if hdr and rows:
                tables.append((hdr, rows))

        h = heading

        if heading_has(h, '连板判定'):
            if tables:
                html += html_subheading("🔮 明日连板判定")
                html += html_table(*tables[0], cell_fn=cell_color)

        elif heading_has(h, '连板自选池'):
            html += html_subheading("🎯 连板自选池", "s3a")
            # Sector blocks
            sector_blocks = re.split(r'\*\*[①②③④⑤]\s*(.+?)\*\*.*?\n', body)
            si = 1
            while si < len(sector_blocks):
                sname = sector_blocks[si].strip()
                sbody = sector_blocks[si+1] if si+1 < len(sector_blocks) else ""
                stables = extract_tables(sbody)
                for st in stables:
                    sh, sr = parse_md_table(st)
                    if sh and sr:
                        html += f'<div class="sh3" style="font-size:14px">{sname}</div>'
                        html += html_table(sh, sr, cell_color)
                si += 2

        elif heading_has(h, '趋势自选池'):
            if tables:
                html += html_subheading("📈 趋势自选池", "s3b")
                html += html_table(*tables[0], cell_fn=cell_color)

        elif heading_has(h, '风险'):
            items = re.findall(r'\d+\.\s+(.+)', body)
            if items:
                html += html_subheading("⚠️ 风险")
                html += '<div class="tight-list">'
                for item in items:
                    html += f'<li>{md_text_to_html(item)}</li>'
                html += '</div>'

        elif heading_has(h, '不碰'):
            html += html_subheading("🚫 不碰")
            html += f'<div class="si">{md_text_to_html(body.strip())}</div>'

        elif heading_has(h, 'rules校验'):
            html += html_subheading("📏 Rules 校验")
            html += f'<div class="si">{md_text_to_html(body.strip())}</div>'

    html += html_section_footer()
    return html


def parse_s4(text):
    """Parse §四 红方对抗."""
    round_bodies = split_red_team_rounds(text)
    total_rounds = len(round_bodies)
    html = html_section_header("s4", "§四 · 红方对抗", f"{total_rounds}轮辩论")

    for round_id, round_label, round_anchor in [
        ("Round 1", "🔴 Round 1：洋米红方质疑", "s4a"),
        ("Round 2", "🔵 Round 2：蓝方回应（稳米）", "s4b"),
        ("Round 3", "🟢 Round 3：洋米终审", "s4c"),
    ]:
        html += html_subheading(round_label, round_anchor)
        round_text = round_bodies.get(round_id, "")
        if not round_text:
            continue

        # ── Round 1: full narrative + tables ──
        if round_id == "Round 1":
            html += md_text_with_tables_to_html(round_text)

        # ── Round 2: response table + summary ──
        elif round_id == "Round 2":
            html += md_text_with_tables_to_html(round_text)

        # ── Round 3: verdict + table ──
        elif round_id == "Round 3":
            verdict_text = ""
            verdict_re = re.compile(r'\*\*(终审定论|终稿定论)\*\*[：:]\s*(.*?)(?:\n\s*\n|$)', re.S)
            verdict_match = verdict_re.search(round_text)
            display_text = round_text
            if verdict_match:
                verdict_text = verdict_match.group(2).strip()
                display_text = f"{round_text[:verdict_match.start()]}{round_text[verdict_match.end():]}"
            html += md_text_with_tables_to_html(display_text)
            if verdict_text:
                html += f'<div class="verdict"><div class="vt">终审定论</div><div class="vb">{md_text_to_html(verdict_text)}</div></div>'

    html += html_section_footer()
    return html


def parse_sa(text):
    """Parse 附录A."""
    html = html_section_header("sa", "附录A · 盘前速查", "周一开盘只看这里")
    # Tables
    tables = extract_tables(text)
    for t in tables:
        headers, rows = parse_md_table(t)
        if headers:
            # Determine table label
            first_row = rows[0] if rows else {}
            if '成本' in headers:
                label = "📋 持仓处理"
            elif '温度标' in headers:
                label = "🎯 连板板块→操作映射"
            elif '观察标的' in headers:
                label = "📈 趋势板块→操作映射"
            else:
                label = ""
            if label:
                html += html_subheading(label)
            html += html_table(headers, rows, cell_color)

    # 操作指南 text
    op_guide = extract_between(text, '### 操作指南', '## 数据附录')
    if not op_guide:
        op_guide = extract_between(text, '### 操作指南', '---')
    if op_guide:
        html += html_subheading("📋 操作指南")
        html += f'<div class="si">{md_text_to_html(op_guide.strip())}</div>'

    html += html_section_footer()
    return html


def parse_data_appendix(text):
    """Parse 数据附录."""
    html = html_section_header("sd", "数据附录", "机器解析用")

    blocks = find_h3_blocks(text)
    for heading, body in blocks:
        body = body.strip()
        if not body:
            continue
        tables_raw = extract_tables(body)
        tables = []
        for t in tables_raw:
            hdr, rows = parse_md_table(t)
            if hdr and rows:
                tables.append((hdr, rows))

        h = heading

        if heading_has(h, '持仓明细'):
            if tables:
                html += html_subheading("持仓明细")
                html += html_table(*tables[0], cell_fn=cell_color)

        elif heading_has(h, '连板自选池'):
            if tables:
                html += html_subheading("连板自选池")
                html += html_table(*tables[0], cell_fn=cell_color)

        elif heading_has(h, '趋势自选池'):
            if tables:
                html += html_subheading("趋势自选池")
                html += html_table(*tables[0], cell_fn=cell_color)

        elif heading_has(h, '板块状态'):
            if tables:
                html += html_subheading("板块状态")
                html += html_table(*tables[0], cell_fn=cell_color)

        elif heading_has(h, '今日操作'):
            if tables:
                html += html_subheading("今日操作")
                html += html_table(*tables[0], cell_fn=cell_color)

        elif heading_has(h, '锚定股状态'):
            if tables:
                html += html_subheading("锚定股状态")
                html += html_table(*tables[0], cell_fn=cell_color)

    html += html_section_footer()
    return html


def generate_sidebar(fm, s0_label='昨日预案'):
    """Generate sidebar navigation."""
    return f"""<div class="sidebar" id="sidebar">
  <div class="label">导航</div>
  <a href="#s0">第〇部分 {s0_label}</a>
  <a href="#s1">§一 当日复盘</a>
  <a href="#s1a" class="s2">大盘全景</a>
  <a href="#s1b" class="s2">情绪高标</a>
  <a href="#s1c" class="s2">节点说明</a>
  <a href="#s1d" class="s2">涨停结构</a>
  <a href="#s1e" class="s2">自选池表现</a>
  <a href="#s1f" class="s2">持仓与交易</a>
  <a href="#s1g" class="s2">风格检测</a>
  <a href="#s1h" class="s2">趋势持仓复盘</a>
  <a href="#s1i" class="s2">窗口操作</a>
  <a href="#s1j" class="s2">结论</a>
  <a href="#s2">§二 心得与教训</a>
  <a href="#s3">§三 次日预案</a>
  <a href="#s3a" class="s2">连板自选池</a>
  <a href="#s3b" class="s2">趋势自选池</a>
  <a href="#s4">§四 红方对抗</a>
  <a href="#s4a" class="s2">Round 1 红方</a>
  <a href="#s4b" class="s2">Round 2 蓝方</a>
  <a href="#s4c" class="s2">Round 3 终审</a>
  <a href="#sa">附录A 盘前速查</a>
  <a href="#sd">数据附录</a>
</div>"""


def convert_md_to_html(md_path):
    """Main conversion function."""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    fm = parse_frontmatter(content)
    content = anonymize_current_holdings(content, fm)
    content = sanitize_public_review_text(content)

    # Parse date for filename
    date_str = fm.get('date', '')
    if not date_str:
        # fallback: extract from filename
        basename = os.path.basename(md_path)
        m = re.match(r'(\d{4})_(\d{1,2})_(\d{1,2})', basename)
        if m:
            date_str = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    weekday = fm.get('weekday', '')

    # Build HTML sections
    sections_html = []

    # §〇
    s0_text, rest = extract_section(content, '第〇部分：昨日预案')
    s0_label = '昨日预案'
    if not s0_text:
        s0_text, rest = extract_section(content, '第〇部分：当日操作指引')
        s0_label = '当日操作指引'
    if s0_text:
        sections_html.append(parse_s0(s0_text, label=s0_label))

    # §一
    s1_text, rest = extract_section(content, '一、当日复盘')
    if s1_text:
        sections_html.append(parse_s1(s1_text, fm))

    # §二
    s2_text, rest = extract_section(content, '二、心得与教训')
    if s2_text:
        sections_html.append(parse_s2(s2_text))

    # §三
    s3_text, rest = extract_section(content, '三、次日预案')
    if s3_text:
        sections_html.append(parse_s3(s3_text))

    # §四
    s4_text, rest = extract_section(content, '四、红方对抗')
    if s4_text:
        sections_html.append(parse_s4(s4_text))

    # 附录A
    sa_text, rest = extract_section(content, '附录A：次日盘前速查')
    if sa_text:
        sections_html.append(parse_sa(sa_text))

    # 数据附录
    sd_text, rest = extract_section(content, '数据附录')
    if sd_text:
        sections_html.append(parse_data_appendix(sd_text))

    # Assemble full HTML
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{date_str} {weekday} 复盘笔记</title>
<style>
{CSS}
</style>
</head>
<body>

{html_topbar(fm)}

<div class="layout">
{generate_sidebar(fm, s0_label)}

<div class="content">

{chr(10).join(sections_html)}

</div>
</div>

{JS_FOOTER}
<script>
(function(){{
  var from = new URLSearchParams(location.search).get('from');
  if (from && /^[A-Za-z0-9_-]+$/.test(from)) {{
    document.getElementById('back-home').href = '../index.html#' + from;
  }}
}})();
</script>
</body>
</html>"""

    # Write output
    output_path = REVIEW_NOTES / f"{date_str}.html"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✅ 已生成: {output_path}")
    return date_str, output_path


def shorten_pos(pos_raw):
    """Expose only the redacted public position state in archive cards."""
    return public_position_summary(pos_raw)


def desc_from_fm(fm):
    """Generate a short description from frontmatter."""
    赚钱 = fm.get('赚钱效应', '')
    emo_v = numeric_value(fm.get('情绪值', ''))
    parts = []
    if emo_v is not None and emo_v < 20:
        parts.append('冰点')
    if 赚钱 == '差':
        parts.append('赚钱效应差')
    if not parts:
        parts.append('')
    return ' · '.join(p for p in parts if p)


# ── Index updaters ──

def update_review_notes_index(date_str, fm):
    """Add entry to review-notes/index.html."""
    idx_path = REVIEW_NOTES / "index.html"
    with open(idx_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 同一天重复同步时刷新归档卡片内容，但不重复增加计数。
    existing_entry = f'href="{date_str}.html"' in content
    year_label = date_str[:4]
    month_label = date_str[5:7].lstrip('0')
    month_title = f'{year_label}年{month_label}月'

    weekday = fm.get('weekday', '')
    day = date_str[-2:].lstrip('0')
    sh_pct_raw = fm.get('上证涨幅', '0%')
    sh_pct = pct_text(sh_pct_raw, signed=True)
    zt = fm.get('涨停家数', '--')
    emo_raw = fm.get('情绪值', '--')
    emo = pct_text(emo_raw)
    pos = shorten_pos(fm.get('盘后持仓', '空仓'))
    emo_v = numeric_value(emo_raw)
    emo_cls = 'up' if emo_v is not None and emo_v < 25 else ('dn' if emo_v is not None and emo_v >= 50 else '')
    sh_cls = 'up' if sh_pct.startswith('+') else 'dn'
    pos_tag = 'tag-a' if '空仓' not in pos else 'tag-g'
    desc = desc_from_fm(fm)

    new_entry = f'''    <a href="{date_str}.html" class="day-card"><div class="dt">{day}<span class="wd"> {weekday}</span></div><div class="mm"><span>上证 <strong class="{sh_cls}">{sh_pct}</strong></span><span>涨停 {zt}</span><span>情绪 <strong class="{emo_cls}">{emo}</strong></span><span>{desc}</span><span class="tag {pos_tag}">持仓 {pos}</span></div><div class="ar">→</div></a>
'''

    if existing_entry:
        card_pattern = rf'<a href="{re.escape(date_str)}\.html" class="day-card">.*?</a>'
        content, replaced = re.subn(rf'\s*{card_pattern}\s*', '\n', content, count=1, flags=re.S)
        if not replaced:
            print(f"⚠️  已存在 {date_str}.html，但未找到归档日卡，跳过归档卡片刷新")

    if month_title not in content:
        month_block = f'''<!-- {month_title} -->
<div class="month-group">
  <div class="month-label" onclick="var s=this.nextElementSibling;this.classList.toggle('collapsed');s.style.display=this.classList.contains('collapsed')?'none':''"><span class="tog">▼</span>{month_title} <span class="cnt">0篇 · 进行中</span></div>
  <div class="day-list">
  </div>
</div>

'''
        content = re.sub(r'(<!-- \d{4}年\d+月 -->)', month_block + r'\1', content, count=1)

    month_pattern = rf'(<!-- {re.escape(month_title)} -->\s*<div class="month-group">.*?<div class="day-list">\s*)'
    content, inserted = re.subn(month_pattern, r'\1' + new_entry, content, count=1, flags=re.S)
    if not inserted:
        print(f"⚠️  未找到 {month_title} 归档分组，跳过归档卡片插入")

    # Recalculate record and month counts from current day cards.
    total_days = len(re.findall(r'<a href="\d{4}-\d{2}-\d{2}\.html" class="day-card"', content))
    content = re.sub(r'(全部记录 · )(\d+)(篇)', rf'\g<1>{total_days}\3', content, count=1)
    content = re.sub(r'(<strong>)(\d+)(</strong> 个交易日)', rf'\g<1>{total_days}\3', content, count=1)
    content = re.sub(r'(交易复盘系统 · )\d+(个交易日)', rf'\g<1>{total_days}\2', content, count=1)

    day_label = date_str[8:10].lstrip('0')
    content = re.sub(
        r'(<span><strong>\d+/\d+ – )\d+/\d+(</strong></span>)',
        rf'\g<1>{month_label}/{day_label}\2',
        content,
        count=1,
    )

    def refresh_month_count(match):
        block = match.group(0)
        card_count = len(re.findall(r'<a href="\d{4}-\d{2}-\d{2}\.html" class="day-card"', block))
        title_match = re.search(r'(\d{4}年\d+月)', block)
        suffix = ' · 进行中' if title_match and title_match.group(1) == month_title else ''
        return re.sub(r'<span class="cnt">.*?</span>', f'<span class="cnt">{card_count}篇{suffix}</span>', block, count=1)

    content = re.sub(r'<!-- \d{4}年\d+月 -->\s*<div class="month-group">.*?</div>\s*</div>', refresh_month_count, content, flags=re.S)

    with open(idx_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ 已更新: {idx_path}")


def extract_close_ratio(date_str):
    """Extract close up/down ratio from the generated review table when available."""
    html_path = REVIEW_NOTES / f"{date_str}.html"
    if not html_path.exists():
        return "--"
    html = html_path.read_text(encoding="utf-8")
    rows = re.findall(r"<tr><td>收盘</td>.*?</tr>", html, flags=re.S)
    if not rows:
        return "--"
    cells = re.findall(r"<td.*?>(.*?)</td>", rows[-1], flags=re.S)
    if len(cells) < 6:
        return "--"
    plain_cells = [re.sub(r"<.*?>", "", cell).strip() for cell in cells]

    # Newer review tables may fold the ratio into the sentiment/width cell
    # and append source-gap columns after the market facts.
    for cell in plain_cells:
        labeled = re.search(
            r"(?:涨跌比|涨跌|上涨\s*/\s*下跌)\s*[:：]?\s*(\d+)\s*/\s*(\d+)",
            cell,
        )
        if labeled:
            return f'<b class="upnum">{labeled.group(1)}</b>/<b class="dnnum">{labeled.group(2)}</b>'

    # Preserve the established six-column layout, where the ratio is cell 6.
    legacy_ratio = re.fullmatch(r"(\d+)\s*/\s*(\d+)", plain_cells[5])
    if legacy_ratio:
        return f'<b class="upnum">{legacy_ratio.group(1)}</b>/<b class="dnnum">{legacy_ratio.group(2)}</b>'

    return "--"


def strip_html_tags(value):
    return re.sub(r"<.*?>", "", value or "").strip()


def compact_period_title(title):
    title = re.sub(r"（.*?）", "", title or "").strip()
    return title or "阶段复盘"


def period_label(start_date, end_date):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    return f"{start.month}/{start.day}–{end.month}/{end.day}"


def compact_period_metric_label(start_date, end_date):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    if start.month == end.month:
        return f"{start.month}/{start.day}-{end.day}"
    return f"{start.month}/{start.day}-{end.month}/{end.day}"


def parse_period_review_path(path):
    m = re.match(r"^(weekly|monthly)-(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})\.html$", path.name)
    if not m:
        return None
    kind, year, start_month, start_day, end_month, end_day = m.groups()
    end_year = int(year)
    if int(end_month) < int(start_month):
        end_year += 1
    return {
        "kind": kind,
        "start": f"{year}-{start_month}-{start_day}",
        "end": f"{end_year:04d}-{end_month}-{end_day}",
    }


def extract_period_metric(html, labels, fallback="--"):
    for label in labels:
        m = re.search(rf"<span>{re.escape(label)}</span>\s*<strong[^>]*>(.*?)</strong>", html, flags=re.S)
        if m:
            return strip_html_tags(m.group(1)) or fallback
    return fallback


def build_period_review_card(path):
    info = parse_period_review_path(path)
    if not info:
        return None
    html = path.read_text(encoding="utf-8")
    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.S) or re.search(r"<title>(.*?)</title>", html, flags=re.S)
    title = compact_period_title(strip_html_tags(title_match.group(1)) if title_match else "")
    label = period_label(info["start"], info["end"])
    metric_label = compact_period_metric_label(info["start"], info["end"])
    start_id = info["start"].replace("-", "")
    end_id = info["end"].replace("-", "")
    kind_label = "周复盘" if info["kind"] == "weekly" else "月复盘"
    kind_cls = "review-kind-weekly" if info["kind"] == "weekly" else "review-kind-monthly"
    metric_period = "周期" if info["kind"] == "weekly" else "区间"
    metric_return = extract_period_metric(html, ["周度收益", "月度收益", "收益"])
    metric_days = extract_period_metric(html, ["交易日"], "阶段")
    metric_focus = extract_period_metric(html, ["风控事件", "月末仓位", "周末仓位"], kind_label)
    card_id = f"recent-review-{info['kind']}-{start_id}-{end_id}"
    return {
        "id": card_id,
        "kind": info["kind"],
        "date": info["end"],
        "html": f'''          <a id="{card_id}" href="review-notes/{path.name}?from={card_id}" class="recent-review-card period-review-card {info["kind"]}-review-card">
            <div class="recent-review-top"><span class="recent-date">{label}</span><span class="review-kind {kind_cls}">{kind_label}</span><span class="review-read">阅读 →</span></div>
            <div class="recent-review-title">{html_escape(title)}</div>
            <div class="review-metric-row"><span class="metric-structure"><em>{metric_period}</em><strong>{html_escape(metric_label)}</strong></span><span class="metric-strong"><em>收益</em><strong>{html_escape(metric_return)}</strong></span><span class="metric-warn"><em>交易日</em><strong>{html_escape(metric_days)}</strong></span><span class="metric-risk"><em>重点</em><strong>{html_escape(metric_focus)}</strong></span></div>
    </a>
''',
    }


def extract_recent_daily_cards(content):
    cards = []
    pattern = re.compile(
        r'<a id="recent-review-(\d{4})" href="review-notes/(\d{4}-\d{2}-\d{2})\.html\?from=recent-review-\1" class="recent-review-card">.*?</a>',
        re.S,
    )
    for match in pattern.finditer(content):
        cards.append({
            "id": f"recent-review-{match.group(1)}",
            "kind": "daily",
            "date": match.group(2),
            "html": match.group(0).strip() + "\n",
        })
    return cards


def extract_recent_period_cards(content):
    cards = []
    pattern = re.compile(
        r'<a id="(recent-review-(weekly|monthly)-\d{8}-\d{8})" href="review-notes/([^"?]+)\?from=\1" class="recent-review-card period-review-card [^"]+">.*?</a>',
        re.S,
    )
    for match in pattern.finditer(content):
        info = parse_period_review_path(Path(match.group(3)))
        if not info:
            continue
        cards.append({
            "id": match.group(1),
            "kind": match.group(2),
            "date": info["end"],
            "html": match.group(0).strip() + "\n",
        })
    return cards


def recent_review_grid_bounds(content):
    start = content.find('<div class="recent-review-grid"')
    if start < 0:
        return None
    inner_start = content.find(">", start)
    if inner_start < 0:
        return None
    inner_start += 1
    depth = 1
    for match in re.finditer(r"</?div\b[^>]*>", content[inner_start:], flags=re.I):
        tag = match.group(0)
        if tag.startswith("</"):
            depth -= 1
        else:
            depth += 1
        if depth == 0:
            return inner_start, inner_start + match.start()
    return None


def rebuild_recent_review_timeline(content, current_date, current_daily_card):
    cards_by_id = {}
    for card in extract_recent_daily_cards(content):
        if card["date"] != current_date:
            cards_by_id[card["id"]] = card
    for card in extract_recent_period_cards(content):
        cards_by_id[card["id"]] = card
    current_card_id = f"recent-review-{current_date[5:7]}{current_date[8:10]}"
    cards_by_id[current_card_id] = {
        "id": current_card_id,
        "kind": "daily",
        "date": current_date,
        "html": current_daily_card.strip() + "\n",
    }
    for pattern in ("weekly-*.html", "monthly-*.html"):
        for path in REVIEW_NOTES.glob(pattern):
            card = build_period_review_card(path)
            if card and card["id"] not in cards_by_id:
                cards_by_id[card["id"]] = card

    kind_priority = {"daily": 3, "weekly": 2, "monthly": 1}
    cards = sorted(
        cards_by_id.values(),
        key=lambda c: (datetime.strptime(c["date"], "%Y-%m-%d"), kind_priority.get(c["kind"], 0)),
        reverse=True,
    )[:6]

    bounds = recent_review_grid_bounds(content)
    if not bounds:
        return content
    inner_start, inner_end = bounds
    timeline_html = "\n" + "".join(card["html"] for card in cards) + "        "
    return content[:inner_start] + timeline_html + content[inner_end:]


def update_main_index(date_str, fm):
    """Update portal/index.html with latest 6 review cards."""
    idx_path = PORTAL / "index.html"
    with open(idx_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 同一天重复同步时，刷新首页卡片内容，但不重复增加归档计数。
    existing_entry = f'review-notes/{date_str}.html' in content

    # Update hero date
    month = date_str[5:7].lstrip('0')
    day = date_str[8:10].lstrip('0')
    content = re.sub(r'更新于 \d+月\d+日', f'更新于 {month}月{day}日', content)
    latest_label = f'{month}月{day}日'
    latest_href = f'review-notes/{date_str}.html'
    content = re.sub(
        r'href="review-notes/\d{4}-\d{2}-\d{2}\.html">阅读最新复盘',
        f'href="{latest_href}">阅读最新复盘',
        content,
    )
    content = re.sub(
        r'href="review-notes/\d{4}-\d{2}-\d{2}\.html"><strong>最新复盘</strong>',
        f'href="{latest_href}"><strong>最新复盘</strong>',
        content,
    )
    content = re.sub(r'(?:LATEST|最新) · \d+月\d+日', f'最新 · {latest_label}', content)
    content = re.sub(
        r'(<div class="trust-label">最新复盘</div><div class="trust-value">)\d+月\d+日(</div>)',
        rf'\g<1>{latest_label}\2',
        content,
    )
    content = re.sub(
        r'(<span>最新复盘</span><strong>)\d{4}-\d{2}-\d{2}(</strong>)',
        rf'\g<1>{date_str}\2',
        content,
    )
    content = re.sub(
        r'(<div class="period-line-text"><strong>\d{2}-\d{2}-\d{2}</strong><span>起点 <em>→</em> 最新复盘</span><strong>)\d{2}-\d{2}-\d{2}(</strong></div>)',
        rf'\g<1>{date_str[2:]}\2',
        content,
    )
    if not existing_entry:
        content = re.sub(
            r'(<div class="trust-label">日报归档</div><div class="trust-value">)(\d+)( 篇</div>)',
            lambda m: f"{m.group(1)}{int(m.group(2)) + 1}{m.group(3)}",
            content,
            count=1,
        )
        content = re.sub(
            r'(<div class="archive-item"><span>日报归档</span><strong>)(\d+)(</strong><em>篇</em></div>)',
            lambda m: f"{m.group(1)}{int(m.group(2)) + 1}{m.group(3)}",
            content,
            count=1,
        )
        content = re.sub(
            r'(<span class="chip">日报归档 )(\d+)( 篇</span>)',
            lambda m: f"{m.group(1)}{int(m.group(2)) + 1}{m.group(3)}",
            content,
            count=1,
        )
        content = re.sub(
            r'(<div class="review-stat"><span>日报归档</span><strong>)(\d+)(</strong><em>篇</em></div>)',
            lambda m: f"{m.group(1)}{int(m.group(2)) + 1}{m.group(3)}",
            content,
            count=1,
        )
    content = re.sub(
        r'(<div class="review-stat"><span>最新复盘</span><strong>)\d+月\d+日(</strong><em>日复盘</em></div>)',
        rf'\g<1>{latest_label}\2',
        content,
        count=1,
    )
    start_match = re.search(r'<span>(?:记录起点|季度起点)</span><strong>(\d{4}-\d{2}-\d{2})</strong>', content)
    if not start_match:
        start_match = re.search(
            r'<div class="period-line-text"><strong>(\d{2}-\d{2}-\d{2})</strong><span>起点 <em>→</em> 最新复盘</span><strong>\d{2}-\d{2}-\d{2}</strong></div>',
            content,
        )
    if start_match:
        start_date = start_match.group(1)
        if re.match(r'^\d{2}-\d{2}-\d{2}$', start_date):
            start_date = f'20{start_date}'
        days_span = (datetime.strptime(date_str, '%Y-%m-%d') - datetime.strptime(start_date, '%Y-%m-%d')).days
        weeks, days_left = divmod(max(days_span, 0), 7)
        span_text = f'{weeks} 周 {days_left} 天' if days_left else f'{weeks} 周'
        content = re.sub(
            r'(<div class="trust-label">记录跨度</div><div class="trust-value small">)[^<]+(</div>)',
            rf'\g<1>{span_text}\2',
            content,
            count=1,
        )
        content = re.sub(
            r'(<div class="period-span"><span>记录跨度</span><strong>)[^<]+(</strong></div>)',
            rf'\g<1>{span_text}\2',
            content,
            count=1,
        )
        content = re.sub(
            r'(<div class="period-span">记录跨度 )[^<]+(</div>)',
            rf'\g<1>{span_text}\2',
            content,
            count=1,
        )

    weekday = fm.get('weekday', '')
    sh_pct_raw = fm.get('上证涨幅', '0%')
    sh_pct = pct_text(sh_pct_raw, signed=True)
    zt = fm.get('涨停家数', '--')
    dt = fm.get('跌停家数', '--')
    emo_raw = fm.get('情绪值', '--')
    emo = pct_text(emo_raw)
    desc = desc_from_fm(fm)
    close_ratio = extract_close_ratio(date_str)

    emo_num = numeric_value(emo_raw)
    sh_metric_cls = 'metric-up' if sh_pct.startswith('+') else 'metric-down'
    emo_metric_cls = 'metric-risk' if emo_num is not None and emo_num < 25 else ('metric-warn' if emo_num is not None and emo_num < 45 else 'metric-strong')
    zt_metric_cls = 'metric-heat' if str(zt).isdigit() and int(zt) >= 80 else 'metric-warn'

    card_id = f"recent-review-{date_str[5:7]}{date_str[8:10]}"
    title = desc or '交易复盘'
    new_entry = f'''          <a id="{card_id}" href="review-notes/{date_str}.html?from={card_id}" class="recent-review-card">
            <div class="recent-review-top"><span class="recent-date">{month}月{day}日</span><span class="review-kind">日复盘</span><span class="review-read">阅读 →</span></div>
            <div class="recent-review-title">{title}</div>
            <div class="review-metric-row"><span class="{sh_metric_cls}"><em>上证</em><strong>{sh_pct}</strong></span><span class="metric-structure metric-pair"><em>涨跌比</em><strong>{close_ratio}</strong></span><span class="{zt_metric_cls} metric-pair"><em>涨跌停</em><strong><b class="upnum">{zt}</b>/<b class="dnnum">{dt}</b></strong></span><span class="{emo_metric_cls}"><em>情绪值</em><strong>{emo}</strong></span></div>
    </a>
'''

    content = rebuild_recent_review_timeline(content, date_str, new_entry)

    with open(idx_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ 已更新: {idx_path}")


# ── CLI ──

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    md_path = sys.argv[1]
    do_commit = '--commit' in sys.argv

    # Convert
    date_str, html_path = convert_md_to_html(md_path)

    # Re-parse for index updates
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    fm = parse_frontmatter(content)

    # Update indexes
    update_review_notes_index(date_str, fm)
    update_main_index(date_str, fm)

    # Optionally commit
    if do_commit:
        os.chdir(PORTAL)
        subprocess.run(['git', 'add', '-A'], check=True)
        subprocess.run(['git', 'commit', '-m',
            f'sync: {date_str} 复盘笔记 (auto)'], check=True)
        print(f"✅ 已 commit")

    print(f"\n完成! 打开: file://{html_path}")


if __name__ == '__main__':
    main()
