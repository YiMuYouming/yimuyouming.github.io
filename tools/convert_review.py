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
.debate-row .dr-body.partial{background:rgba(217,119,6,.04);border-left:3px solid var(--amber)}"""

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
    pos = fm.get('盘后持仓', '空仓')

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
    thead = '<thead><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr></thead>'
    tbody = '<tbody>'
    for row in rows:
        tbody += '<tr>'
        for h in headers:
            v = row.get(h, '')
            if cell_fn:
                v = cell_fn(h, v)
            tbody += f'<td>{v}</td>'
        tbody += '</tr>'
    tbody += '</tbody>'
    return f'<div class="tw"><table>{thead}{tbody}</table></div>'


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


def md_text_to_html(text):
    """Convert markdown text block to HTML, preserving paragraphs/lists/quotes."""
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
        para = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
        para = re.sub(r'`([^`]+)`', r'<code>\1</code>', para)
        out.append(f'<div class="para">{para}</div>')
        i += 1

    if in_list:
        out.append('</ol>')
    if in_quote:
        out.append('</div>')

    return '\n'.join(out)


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


# ── Section parsers ──

def parse_s0(text):
    """Parse §〇 昨日预案."""
    html = html_section_header("s0", "第〇部分 · 昨日预案", "昨日终审定稿")
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


def parse_s1(text):
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
                html += html_table(*tables[0], cell_fn=cell_color)

        elif heading_has(h, '节点说明'):
            html += html_subheading("🔍 节点说明", "s1c")
            html += '<div class="node-grid">'
            node_names = ['竞价', '早盘', '午盘']
            for idx, node_name in enumerate(node_names):
                # Extract between this node and the next node (or end)
                parts = body.split(f'**{node_name}**')
                if len(parts) < 2:
                    continue
                after = parts[1]
                if idx + 1 < len(node_names):
                    next_marker = f'**{node_names[idx+1]}**'
                    next_pos = after.find(next_marker)
                    if next_pos != -1:
                        node_text = after[:next_pos]
                    else:
                        node_text = after[:800]
                else:
                    node_text = after[:800]
                if node_text:
                    node_text = node_text.strip().lstrip('\n- 说明：').lstrip('\n- 结论：').lstrip('\n说明：').lstrip('\n结论：')
                    lines = node_text.strip().split('\n')
                    body_text = '<br>'.join(l.strip() for l in lines)
                    html += f'<div class="node-card"><div class="nhead">{node_name}</div><div class="nbody">{md_text_to_html(body_text)}</div></div>'
            html += '</div>'

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
    items = re.findall(r'\d+\.\s+\*\*\[.+?\].+?(?=\n\d+\.\s+\*\*\[|$)', text, re.DOTALL)
    if not items:
        items = [text.strip()]
    html += '<ol class="tight-list">'
    for item in items:
        html += f'<li>{md_text_to_html(item.strip())}</li>'
    html += '</ol>'
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
    total_rounds = len(re.findall(r'### Round [123]', text))
    html = html_section_header("s4", "§四 · 红方对抗", f"{total_rounds}轮辩论")

    # Split entire text into rounds by ### Round boundaries
    round_splits = re.split(r'^### (Round [123])[：:].*$', text, flags=re.MULTILINE)
    # round_splits: [pre, 'Round 1', r1_body, 'Round 2', r2_body, 'Round 3', r3_body]
    round_bodies = {}
    for i in range(1, len(round_splits), 2):
        round_id = round_splits[i].strip()
        round_body = round_splits[i+1] if i+1 < len(round_splits) else ""
        round_bodies[round_id] = round_body.strip()

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
            # Render everything: first pass md→html, then overlay tables
            html += md_text_to_html(round_text)
            # Add tables that md_text_to_html missed (it doesn't handle tables)
            for t in extract_tables(round_text):
                hdr, rows = parse_md_table(t)
                if hdr and rows:
                    html += html_table(hdr, rows, cell_color)

        # ── Round 2: response table + summary ──
        elif round_id == "Round 2":
            html += md_text_to_html(round_text)
            r2_tables = extract_tables(round_text)
            if r2_tables:
                hdr, rows = parse_md_table(r2_tables[0])
                if hdr:
                    html += html_subheading("逐条回应")
                    html += html_table(hdr, rows, cell_color)

        # ── Round 3: verdict + table ──
        elif round_id == "Round 3":
            html += md_text_to_html(round_text)
            # Verdict box
            for vt_key in ['**终审定论**', '**终稿定论**']:
                verdict_text = extract_between(round_text, vt_key, '---')
                if not verdict_text:
                    verdict_text = extract_between(round_text, vt_key, '\n\n')
                if verdict_text:
                    html += f'<div class="verdict"><div class="vt">终审定论</div><div class="vb">{md_text_to_html(verdict_text.strip())}</div></div>'
                    break
            # Tables
            for t in extract_tables(round_text):
                hdr, rows = parse_md_table(t)
                if hdr and rows:
                    html += html_table(hdr, rows, cell_color)

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


def generate_sidebar(fm):
    """Generate sidebar navigation."""
    return f"""<div class="sidebar" id="sidebar">
  <div class="label">导航</div>
  <a href="#s0">第〇部分 昨日预案</a>
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
    if s0_text:
        sections_html.append(parse_s0(s0_text))

    # §一
    s1_text, rest = extract_section(content, '一、当日复盘')
    if s1_text:
        sections_html.append(parse_s1(s1_text))

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
{generate_sidebar(fm)}

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
    """Shorten position string for card display: '北华+领益'."""
    if not pos_raw or pos_raw == '空仓':
        return '空仓'
    # Extract stock abbreviations
    names = [n for n in re.findall(r'([一-鿿]+)', pos_raw) if n not in ('股', '空仓')]
    short = '+'.join(n[:2] for n in names[:2])
    return short if short else pos_raw[:10]


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
    ratio = re.sub(r"<.*?>", "", cells[5]).strip()
    m = re.match(r"^(\d+)\s*/\s*(\d+)$", ratio)
    if m:
        return f'<b class="upnum">{m.group(1)}</b>/<b class="dnnum">{m.group(2)}</b>'
    return ratio or "--"


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

    if existing_entry:
        card_pattern = rf'<a id="{re.escape(card_id)}" href="review-notes/{re.escape(date_str)}\.html\?from={re.escape(card_id)}" class="recent-review-card">.*?</a>'
        content, replaced = re.subn(card_pattern, new_entry.rstrip(), content, count=1, flags=re.S)
        if not replaced:
            print(f"⚠️  已存在 {date_str}.html，但未找到首页近期复盘卡片，跳过卡片刷新")
    else:
        # Insert after the homepage recent-review grid.
        content = re.sub(r'(<div class="recent-review-grid">\s*)', r'\1' + new_entry, content, count=1)

        # Keep only 6 most recent entries
        day_rows = list(re.finditer(r'<a id="recent-review-\d{4}" href="review-notes/\d{4}-\d{2}-\d{2}\.html\?from=recent-review-\d{4}" class="recent-review-card">', content))
        if len(day_rows) > 6:
            # Remove the last (oldest) entry
            last = day_rows[-1]
            # Find the closing </a> for this entry
            close_pos = content.find('</a>', last.end())
            content = content[:last.start()] + content[close_pos + 5:]

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
