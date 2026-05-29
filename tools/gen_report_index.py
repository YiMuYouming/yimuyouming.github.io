#!/usr/bin/env python3
"""从 report/reports.json 生成 report/index.html

用法:
  python3 tools/gen_report_index.py           # 生成到 report/index.html
  python3 tools/gen_report_index.py --dry    # 预览输出，不写入
  python3 tools/gen_report_index.py --watch  # 监控清单变化，自动重生成

维护说明：
- 新增报告 → 编辑 report/reports.json，添加条目
- 修改分类 → 调整 folderId 字段
- 修改展示文案 → 调整 reports.json 中的 title/description/tagLabel
"""

import argparse
import json
import sys
from pathlib import Path

PORTAL = Path(__file__).resolve().parent.parent
REPORT_JSON = PORTAL / "report" / "reports.json"
OUTPUT_HTML = PORTAL / "report" / "index.html"

# ── 报告库文件夹元数据 ───────────────────────────────────────────────────

FOLDER_META = {
    "market": {
        "eyebrow": "Folder 01",
        "title": "6月市场报告",
        "subtitle": "新发布 · 月度配置框架",
        "count": 0,   # 动态
    },
    "figure": {
        "eyebrow": "Folder 02",
        "title": "游资人物库",
        "subtitle": "12 篇 · 交易风格与风险边界",
        "count": 0,
    },
    "tools": {
        "eyebrow": "Folder 03",
        "title": "知识与对手研究",
        "subtitle": "2 篇 · 工具方法",
        "count": 0,
    },
    "may-market": {
        "eyebrow": "Folder 04",
        "title": "五月市场沉淀",
        "subtitle": "2 篇 · 六月前置材料",
        "count": 0,
    },
}

FOLDER_CARD = {
    "market": {
        "label": "6月市场报告",
        "count": "篇",
        "desc": "六月主线排序、个股调研、评分矩阵和仓位节奏。",
    },
    "figure": {
        "label": "游资人物库",
        "count": "篇",
        "desc": "龙头、连板、趋势、造势、风险样本的完整人物研究。",
    },
    "tools": {
        "label": "知识与对手研究",
        "count": "篇",
        "desc": "龙虎榜工具、量化对手画像和盘口识别方法。",
    },
    "may-market": {
        "label": "五月市场沉淀",
        "count": "篇",
        "desc": "五月主线圆桌与潜在个股分析，作为六月前置材料。",
    },
}

TAG_LABELS = {
    "new": "新发布",
    "figure": "人物",
    "tool": "对手研究",
    "risk": "风险样本",
}


# ── HTML 模板 ────────────────────────────────────────────────────────────

HTML_HEAD = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>投研资源 · 弈沐资本</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@500;600;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#F7F5F3;--card:#FFFFFF;--paper:#FBFAF8;--soft:#F5F2EE;--line:#E5E2DE;--line2:#F0EEEC;--text:#2D2926;--muted:#5C5652;--faint:#8A8480;--accent:#D97706;--accent2:#B45309;--green:#059669;--blue:#2563EB;--purple:#7C3AED}
body{font:15px/1.6 system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}a:hover{color:var(--accent2)}
.page{max-width:1040px;margin:0 auto;padding:32px 32px 72px}
.top{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid var(--line2)}
.back{font-size:13px;color:var(--muted)}
.eyebrow{font-size:11px;color:var(--accent);font-weight:800;letter-spacing:.18em;margin-bottom:6px;text-transform:uppercase}
h1,h2{font-family:'Noto Serif SC',serif;color:var(--text)}h1{font-size:32px;line-height:1.22}h2{font-size:23px;line-height:1.25}
.desc{font-size:13px;color:var(--faint);margin-top:8px;max-width:620px}
.summary-strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:18px}
.summary-item{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.summary-item strong{display:block;font-size:22px;line-height:1.1}.summary-item span{display:block;margin-top:4px;font-size:12px;color:var(--faint)}
.folder-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:16px 0 28px}
.folder-card{position:relative;display:block;min-height:154px;border:1px solid var(--line);border-radius:15px;background:linear-gradient(145deg,#fff,var(--paper));padding:16px;color:var(--text);box-shadow:0 10px 26px rgba(45,41,38,.04);overflow:hidden;transition:all .15s}
.folder-card:hover{border-color:rgba(217,119,6,.42);box-shadow:0 18px 38px rgba(45,41,38,.08);color:var(--text);transform:translateY(-1px)}
.folder-card::before{content:"";position:absolute;left:16px;top:17px;width:42px;height:29px;border-radius:8px 8px 6px 6px;background:rgba(217,119,6,.16);box-shadow:inset 0 0 0 1px rgba(217,119,6,.18)}
.folder-card::after{content:"";position:absolute;left:20px;top:12px;width:22px;height:10px;border-radius:6px 6px 0 0;background:rgba(217,119,6,.24)}
.folder-count{float:right;font-size:11px;font-weight:900;color:var(--accent);background:rgba(217,119,6,.1);border-radius:999px;padding:2px 8px}
.folder-card strong{display:block;clear:both;margin-top:40px;font-size:16px}.folder-card span:last-child{display:block;margin-top:7px;font-size:12px;color:var(--muted);line-height:1.55}
.library-section{scroll-margin-top:24px;margin-top:24px}
.section-head{display:flex;align-items:flex-end;justify-content:space-between;gap:14px;margin-bottom:10px}
.section-head p{font-size:12px;color:var(--faint)}
.file-list{display:grid;gap:8px}
.file-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;align-items:center;border:1px solid var(--line);border-radius:13px;background:rgba(255,255,255,.82);padding:13px 15px;color:var(--text);box-shadow:0 8px 20px rgba(45,41,38,.03)}
.file-row:hover{border-color:rgba(217,119,6,.42);box-shadow:0 14px 30px rgba(45,41,38,.06);color:var(--text)}
.file-title{display:block;font-weight:800;font-size:15px;line-height:1.35}.file-meta{display:block;margin-top:4px;font-size:12px;color:var(--faint);line-height:1.5}
.file-tag{justify-self:end;white-space:nowrap;border-radius:999px;background:var(--soft);color:var(--muted);font-size:11px;font-weight:800;padding:3px 9px}.file-tag.new{background:rgba(5,150,105,.12);color:var(--green)}.file-tag.tool{background:rgba(37,99,235,.1);color:var(--blue)}.file-tag.figure{background:rgba(217,119,6,.1);color:var(--accent)}.file-tag.risk{background:rgba(124,58,237,.1);color:var(--purple)}
@media(max-width:900px){.summary-strip,.folder-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:640px){.page{padding:24px 20px 48px}.top,.section-head{display:block}.back{display:inline-block;margin-top:10px}.summary-strip,.folder-grid{grid-template-columns:1fr}.file-row{grid-template-columns:1fr}.file-tag{justify-self:start}h1{font-size:27px}}
</style>
</head>
<body>
<main class="page">
  <div class="top">
    <div>
      <div class="eyebrow">Research Library</div>
      <h1>投研资源</h1>
      <p class="desc">这里是文档库首页。先按主题文件夹进入，再阅读单篇报告，避免精选文档和归档文件混在同一层。</p>
    </div>
    <a id="back-home" class="back" href="../index.html#research-reports">返回首页</a>
  </div>
"""

HTML_FOOTER = """
</main>
<script>
(function(){
  var from = new URLSearchParams(location.search).get('from');
  if (from && /^[A-Za-z0-9_-]+$/.test(from)) {
    document.getElementById('back-home').href = '../index.html#' + from;
  }
})();
</script>
</body>
</html>
"""


# ── 生成逻辑 ────────────────────────────────────────────────────────────

def load_reports() -> list[dict]:
    with open(REPORT_JSON, encoding="utf-8") as f:
        return json.load(f)


def group_by_folder(reports: list[dict]) -> dict[str, list[dict]]:
    groups = {}
    for r in reports:
        fid = r.get("folderId", r.get("folder"))
        groups.setdefault(fid, []).append(r)
    return groups


def render_summary(reports: list[dict]) -> str:
    total = len(reports)
    folder_count = len({r.get("folderId", r.get("folder")) for r in reports})
    figure_count = sum(1 for r in reports if r.get("folderId") == "figure")
    market_count = sum(1 for r in reports if r.get("folderId") == "market" and r.get("tag") == "new")

    return f"""
  <div class="summary-strip" aria-label="投研资源统计">
    <div class="summary-item"><strong>{total}</strong><span>已发布报告</span></div>
    <div class="summary-item"><strong>{folder_count}</strong><span>主题文件夹</span></div>
    <div class="summary-item"><strong>{figure_count}</strong><span>游资人物研究</span></div>
    <div class="summary-item"><strong>{market_count}</strong><span>6 月市场报告</span></div>
  </div>
"""


def render_folder_grid(groups: dict[str, list[dict]]) -> str:
    rows = []
    for fid in ["market", "figure", "tools", "may-market"]:
        items = groups.get(fid, [])
        if not items:
            continue
        meta = FOLDER_CARD.get(fid, {})
        label = meta.get("label", fid)
        count = len(items)
        desc = meta.get("desc", "")
        rows.append(
            f'<a class="folder-card" href="#{fid}">'
            f'<span class="folder-count">{count} {meta.get("count","篇")}</span>'
            f'<strong>{label}</strong>'
            f'<span>{desc}</span>'
            f'</a>'
        )
    return (
        f'\n  <div class="folder-grid" aria-label="文档库文件夹">\n    '
        + "\n    ".join(rows)
        + '\n  </div>'
    )


def render_section(fid: str, reports: list[dict]) -> str:
    meta = FOLDER_META.get(fid, {})
    eyebrow = meta.get("eyebrow", "")
    title = meta.get("title", fid)
    subtitle = meta.get("subtitle", "")
    count = len(reports)

    file_rows = []
    for r in reports:
        tag = r.get("tag", "")
        tag_class = f" {tag}" if tag else ""
        tag_label = r.get("tagLabel", "")
        tag_text = f'<span class="file-tag{tag_class}">{tag_label}</span>' if tag_label else ""
        desc = r.get("description", "")
        title_text = r.get("title", "")
        folder = r.get("folder", "")
        filename = r.get("filename", "")
        href = f"{folder}/{filename}"

        file_rows.append(
            f'<a class="file-row" href="{href}">'
            f'<span><span class="file-title">{title_text}</span>'
            f'<span class="file-meta">{desc}</span></span>'
            f'{tag_text}'
            f'</a>'
        )

    return (
        f'<section class="library-section" id="{fid}">\n'
        f'    <div class="section-head"><div><div class="eyebrow">{eyebrow}</div><h2>{title}</h2></div><p>{subtitle}</p></div>\n'
        f'    <div class="file-list">\n      '
        + "\n      ".join(file_rows)
        + f'\n    </div>\n'
        f'  </section>'
    )


def _join_sections(sections: list[str]) -> str:
    """拼接各 section，section 之间保持一个空行分隔，且有 2 空格缩进"""
    result = ""
    for i, sec in enumerate(sections):
        if i == 0:
            result += sec
        else:
            result += "\n\n  " + sec
    return result


def generate(reports: list[dict]) -> str:
    groups = group_by_folder(reports)
    sections = []
    for fid in ["market", "figure", "tools", "may-market"]:
        items = groups.get(fid, [])
        if items:
            sections.append(render_section(fid, items).rstrip())

    return (
        HTML_HEAD
        + render_summary(reports)
        + render_folder_grid(groups).rstrip("\n")
        + "\n\n  "
        + _join_sections(sections)
        + HTML_FOOTER
    )


# ── 入口 ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="从 reports.json 生成 report/index.html")
    parser.add_argument("--dry", action="store_true", help="预览输出，不写入")
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_HTML,
        help=f"输出路径（默认: {OUTPUT_HTML}）",
    )
    args = parser.parse_args()

    reports = load_reports()
    print(f"读取 {len(reports)} 篇报告")

    html = generate(reports)

    if args.dry:
        print(f"\n--- {args.output} ---")
        print(html[:2000])
        if len(html) > 2000:
            print(f"\n... ({len(html)} chars total)")
        return

    args.output.write_text(html, encoding="utf-8")
    print(f"已生成 {args.output} ({len(html)} chars)")


if __name__ == "__main__":
    main()
