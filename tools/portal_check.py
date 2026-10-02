#!/usr/bin/env python3
"""Portal 发布前检查工具

对 portal 项目所有 HTML 进行自动化巡检，检查：
- 断链（href 指向不存在的文件）
- 重复 id
- 缺 <title>
- 缺返回入口（复盘笔记/报告/方法论等子页面缺少返回首页链接）
- 明显的说明性占位文案 / 调试文案

低风险问题可自动修复（需加 --fix）：
- 重复 id → 追加 -2/-3 后缀
- 缺 title → 从文件名推断
- 缺返回入口 → 插入返回首页链接

其他问题仅报告，提示手动处理。

用法：
  python3 tools/portal_check.py               # 只检查
  python3 tools/portal_check.py --fix        # 检查并自动修复
  python3 tools/portal_check.py --fix --dry   # 预览修复，不写入
  python3 tools/portal_check.py --sections    # 只检查入口页面
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from html.parser import HTMLParser

# ── 项目根目录 ──────────────────────────────────────────────────────────────

PORTAL = Path(__file__).resolve().parent.parent


# ── 占位 / 调试文案检测词 ──────────────────────────────────────────────────

PLACEHOLDER_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"待补充",
        r"\bTODO\b",
        r"TODO[:：]",
        r"占位",
        r"\bplaceholder\b",
        r"\bPLACEHOLDER\b",
        r"待定",
        r"待更新",
        r"测试数据",
        r"test data",
        r"dummy data",
        r"示例数据",
        r"假数据",
        r"fake data",
        r"coming soon",
        r"draft",
        r"DRAFT",
        r"草稿",
        r"此处待写",
        r"这里待补充",
        r"（后续补充）",
        r"（待填）",
        r"（待完善）",
        r"（待更新）",
        r"敬请期待",
        r"暂无内容",
        r"数据加载中",
        r"\bloading\b",
        r"加载中",
        r"占位符",
        r"\bdebug\b",
        r"\bDEBUG\b",
        r"console\.log",
        r"alert\(",
        r"debugger;",
    ]
]

# 已知的占位文案误报（路径正则 → 匹配文本上下文）
# 命中以下任一规则时，匹配项被静默抑制（计入 suppressed 但不输出）
FALSE_POSITIVE_CONTEXT: list[tuple[re.Pattern, re.Pattern, str]] = [
    # 1. CSS ::placeholder pseudo-selector
    (
        re.compile(r"\.html$"),
        re.compile(r":?: ?placeholder\b", re.IGNORECASE),
        "CSS ::placeholder pseudo-selector",
    ),
    # 2. JavaScript readyState === 'loading'
    (
        re.compile(r"^index\.html$"),
        re.compile(r"readyState\s*(===?|!==?)\s*['\"]loading['\"]", re.IGNORECASE),
        "JS readyState 'loading'",
    ),
    # 3. 复盘笔记中的合法"待补充"（交易计划/风控表格中的已知缺口标记）
    (
        re.compile(r"review-notes/"),
        re.compile(r"待补充[（\uFF08]"),
        "review-notes 交易计划合法术语",
    ),
    # 3b. 复盘笔记中表格单元格的"待更新"（非占位，是合法空值）
    (
        re.compile(r"review-notes/2026-03-26\.html"),
        re.compile(r"待更新"),
        "review-notes 竞价表格空值",
    ),
    # 4. 复盘笔记中的"待补充"（已给出行动说明的延续）
    (
        re.compile(r"review-notes/"),
        re.compile(r"补充规则[：:].*待补充|待补充[^\u4e00-\u9fff]*[）\)].*补充规则"),
        "review-notes 规则补充延续",
    ),
    # 5. 复盘笔记中的"占位冲突"（板块分类分析用词，非占位符）
    (
        re.compile(r"review-notes/"),
        re.compile(r"占位冲突"),
        "review-notes 板块分类用词",
    ),
    # 6. 炒股养家研究报告中的"待补充条款"（Trading Rules 对照分析表格标题）
    (
        re.compile(r"report/figure/炒股养家研究报告\.html"),
        re.compile(r"待补充条款"),
        "Trading Rules 对照分析表格标题",
    ),
    # 7. 复盘笔记中"待更新 trading-rules.md"（规则修订行动项）
    (
        re.compile(r"review-notes/2026-04-03\.html"),
        re.compile(r"→\s*待更新\s+trading-rules"),
        "复盘规则修订行动项",
    ),
    # 8. 复盘笔记中"待定 ：当前rules"（趋势评估中的待定分析）
    (
        re.compile(r"review-notes/2026-04-03\.html"),
        re.compile(r"待定\s+："),
        "趋势评估待定分析",
    ),
    # 9. 复盘笔记中"→待定"（窗口操作记录中的待定状态）
    (
        re.compile(r"review-notes/2026-05-07\.html"),
        re.compile(r"→待定"),
        "窗口操作记录待定状态",
    ),
    # 10. 复盘笔记中"待补充"（接冒号或不接）+ 规则/执行相关文字（规则补充行动项）
    (
        re.compile(r"review-notes/"),
        re.compile(r"待补充[：:]?\s*(执行时机|板块弱|情绪拐点|rules\s*§|补充[：:])[^。！？]{0,60}"),
        "规则补充执行时机",
    ),
    # 11. 周报中"待补充"紧跟"补充规则"（表格行动项）
    (
        re.compile(r"review-notes/weekly-2026-05-11_05-15\.html"),
        re.compile(r"待补充\s+补充规则"),
        "周报规则补充行动项",
    ),
    # 12. 复盘笔记中的规则状态短语 draft/unverified（非草稿页占位）
    (
        re.compile(r"review-notes/"),
        re.compile(r"draft/unverified"),
        "review-notes 规则状态短语",
    ),
]

# ── 占位文案白名单配置 ─────────────────────────────────────────────────────
#
# suppression_rules: 命中的匹配不输出（仍计入 suppressed 计数）
#   - path_re:   文件路径正则，None=任意路径
#   - pattern_re: 命中哪个 PLACEHOLDER_PATTERNS
#   - context_re: 匹配项周围上下文（原始文本），用于精确区分
#
SUPPRESSION_RULES: list[dict] = [
    # CSS ::placeholder pseudo-selector (4 files)
    {
        "path_re": re.compile(r"\.html$"),
        "pattern_re": re.compile(r":?:placeholder\b", re.IGNORECASE),
        "context_re": re.compile(r"::placeholder|:: ?placeholder", re.IGNORECASE),
    },
    # JavaScript readyState === 'loading' (index.html)
    {
        "path_re": re.compile(r"^index\.html$"),
        "pattern_re": re.compile(r"\bloading\b", re.IGNORECASE),
        "context_re": re.compile(r"readyState\s*===?\s*['\"]loading['\"]", re.IGNORECASE),
    },
]

# 已知误报摘要（用于日志）
SUPPRESSION_SUMMARY = {
    "CSS ::placeholder": "CSS ::placeholder pseudo-selector，非正文内容",
    "JS readyState loading": "document.readyState 属性值，非占位文案",
    "review-notes 待补充": "交易笔记中'待补充'是合法记录术语",
    "review-notes 占位": "交易笔记中'占位冲突'是描述板块分类问题的用词",
}


@dataclass
class CheckResult:
    severity: str
    file: Path
    check: str
    message: str
    suppressed: bool = False

BACK_LINK_REQUIRED = [
    (re.compile(r"review-notes/\d{4}-\d{2}-\d{2}\.html$"), "复盘笔记"),
    (re.compile(r"daily-notes/\d{4}-\d{2}-\d{2}\.html$"), "每日市场手记"),
    (re.compile(r"review-notes/weekly-\d{4}"), "周报"),
    (re.compile(r"review-notes/monthly-\d{4}"), "月报"),
    (re.compile(r"report/[a-z]+/.+\.html$"), "研究报告"),
    (re.compile(r"insights/.+\.html$"), "insights"),
    (re.compile(r"methodology/.+\.html$"), "方法论"),
]


# ── HTML 解析器 ───────────────────────────────────────────────────────────

class HTMLLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []    # [(href, line_no)]
        self.ids = []      # [(id_val, line_no)]
        self.title = None
        self.has_body = False
        self._in_style = False
        self._text_chunks = []
        self._raw_chunks = []  # style/script content for whitelist matching

    def handle_starttag(self, tag, attrs):
        if tag == "style":
            self._in_style = True
        elif tag in ("body",):
            self.has_body = True

        for name, val in attrs:
            if name == "href" and val:
                self.links.append((val, self.getpos()[0]))
            elif name == "id" and val:
                self.ids.append((val.strip(), self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag == "style":
            self._in_style = False

    def handle_data(self, data):
        if self._in_style:
            self._raw_chunks.append(data)
        else:
            chunk = data.strip()
            if chunk:
                self._text_chunks.append(chunk)

    def handle_comment(self, data):
        pass

    @property
    def text(self):
        return " ".join(self._text_chunks)


def parse_html(filepath: Path) -> dict:
    text = filepath.read_text(encoding="utf-8")
    parser = HTMLLinkParser()
    try:
        parser.feed(text)
    except Exception:
        return {"error": "parse failed", "text": "", "links": [], "ids": [], "title": None, "has_body": False}

    title_m = re.search(r"<title[^>]*>([^<]+)</title>", text, re.IGNORECASE)
    title = title_m.group(1).strip() if title_m else None

    return {
        "error": None,
        "text": parser.text,
        "links": parser.links,
        "ids": parser.ids,
        "title": title or parser.title,
        "has_body": parser.has_body,
        "raw_text": " ".join(parser._raw_chunks),
    }


# ── 检查函数 ──────────────────────────────────────────────────────────────

def check_broken_links(filepath: Path, scan: dict) -> list[str]:
    """检查 href 指向不存在的本地文件"""
    issues = []
    for href, line_no in scan["links"]:
        # 跳过外部/锚点/javascript
        if re.match(r"^(https?://|mailto:|tel:|javascript:|#)", href):
            continue

        # 去掉锚点和 query string
        base = href.split("#")[0].split("?")[0]
        if not base:
            continue
        # 跳过 href="./" 自身（有效的首页链接）
        if base.rstrip("/") == ".":
            continue

        # 相对路径解析
        try:
            target = (filepath.parent / base).resolve()
            rel = target.relative_to(PORTAL)
            if not target.exists():
                issues.append(f"  [{line_no}] 断链: {href}  (实际: {rel})")
            elif target.is_dir():
                issues.append(f"  [{line_no}] 链接目录（非文件）: {href}")
        except ValueError:
            pass  # 跨驱动器路径，跳过

    return issues


def check_duplicate_ids(scan: dict) -> list[str]:
    """检查重复 id"""
    issues = []
    seen = {}
    for id_val, line_no in scan["ids"]:
        if not id_val:
            continue
        if id_val in seen:
            issues.append(f"  [{line_no}] 重复 id='{id_val}' (首次出现在 {seen[id_val]})")
        else:
            seen[id_val] = line_no
    return issues


def check_missing_title(scan: dict) -> list[str]:
    if not scan.get("title"):
        return ["  缺少 <title> 标签"]
    return []


def check_missing_back_link(filepath: Path, scan: dict) -> list[str]:
    """检查子页面是否缺少返回首页链接"""
    rel = str(filepath.relative_to(PORTAL))
    matched_label = None
    for pattern, label in BACK_LINK_REQUIRED:
        if pattern.search(rel):
            matched_label = label
            break

    if not matched_label:
        return []

    depth = rel.count("/") - 1
    expected = ("../" * depth + "index.html") if depth > 0 else "./index.html"

    # 检查是否有指向 portal 根的链接（任意深度均可接受，只要有效）
    valid_roots = {"index.html", "./index.html", "../index.html", "../../index.html"}
    for href, _ in scan["links"]:
        base = href.split("#")[0].split("?")[0]
        # 只要链接指向 index.html，且深度不超过期望太多就算有效
        if base.rstrip("/index.html") in ("", ".") or base.rstrip("/") in ("..", "../.."):
            return []  # 找到了
        if base in valid_roots:
            return []

    return [f"  缺少返回首页链接（{matched_label}页，应有 {expected}）"]


def check_placeholders(filepath: Path, scan: dict, collect_suppressed: bool = False) -> tuple[list[str], list[dict]]:
    """检测占位/调试文案，返回 (issues, suppressed_items)

    在 parse_html 提取的可见文本上搜索（不含 HTML 标签/属性值），
    在可见文本和 CSS/script 原始内容上搜索，由 FALSE_POSITIVE_CONTEXT 规则过滤误报。
    suppressed_items: [{"file": str, "ctx": str, "reason": str}] 当 collect_suppressed=True 时填充
    """
    text = scan.get("text", "")
    raw_text = scan.get("raw_text", "")
    if not text and not raw_text:
        return [], []

    try:
        rel_path = str(filepath.relative_to(PORTAL))
    except ValueError:
        rel_path = filepath.name  # 外部临时文件用文件名
    html_text = filepath.read_text(encoding="utf-8")
    suppressed_items: list[dict] = []
    issues = []

    # 合并可见文本和 CSS/script 内容，统一检测
    combined_text = f"{text} {raw_text}"
    matched_patterns: set[int] = set()  # 避免同一 match 重复报告

    for pi, pattern in enumerate(PLACEHOLDER_PATTERNS):
        for m in pattern.finditer(combined_text):
            if pi in matched_patterns:
                continue
            matched_text = m.group(0)

            # 在原始 HTML 中取上下文（用于 FALSE_POSITIVE_CONTEXT 匹配）
            start = max(0, m.start() - 120)
            end = min(len(combined_text), m.end() + 120)
            ctx_in_combined = combined_text[start:end]
            pos = html_text.find(ctx_in_combined[:min(50, len(ctx_in_combined))])
            if pos >= 0:
                raw_start = max(0, pos - 120)
                raw_end = min(len(html_text), pos + len(ctx_in_combined) + 120)
                ctx = html_text[raw_start:raw_end]
            else:
                ctx = ctx_in_combined

            is_fp = False
            fp_reason = ""
            for path_re, ctx_re, reason in FALSE_POSITIVE_CONTEXT:
                if path_re.search(rel_path) and ctx_re.search(ctx):
                    is_fp = True
                    fp_reason = reason
                    break

            if is_fp:
                if collect_suppressed:
                    ctx_short = ctx.replace("\n", " ").strip()
                    suppressed_items.append({
                        "file": rel_path,
                        "ctx": f"...{ctx_short}...",
                        "reason": fp_reason,
                        "matched": matched_text,
                    })
                matched_patterns.add(pi)
                break  # 匹配上了但被抑制，跳到下一个 pattern

            ctx_short = ctx.replace("\n", " ").strip()
            issues.append(f"  占位/调试文案: ...{ctx_short}...")
            matched_patterns.add(pi)
            break  # 每个文件每个 pattern 只报第一个匹配

    return issues, suppressed_items


# ── 修复函数 ──────────────────────────────────────────────────────────────

def fix_duplicate_ids(html: str) -> tuple[str, bool]:
    """给重复 id 追加 -2/-3 后缀（从第二次出现开始修正）"""
    id_seen: dict[str, int] = {}
    fixed = []

    def replacer(m):
        tag_and_attrs = m.group(1)
        id_val = m.group(2)
        after = m.group(3)

        if id_val not in id_seen:
            id_seen[id_val] = 1
            return m.group(0)

        id_seen[id_val] += 1
        new_id = f"{id_val}-{id_seen[id_val]}"
        fixed.append(f"    id='{id_val}' → '{new_id}'")
        # Rebuild tag: preserve everything before id=
        tag_start = m.group(0).find("id=")
        before = m.group(0)[:tag_start]
        return f'{before}id="{new_id}"{after}"'

    new_html = re.sub(
        r'(<[^\s>]+[^>]*?)\sid="([^"]+)"([^"]*?)"',
        replacer,
        html,
    )

    if fixed:
        print(f"  重复 id 修复 {len(fixed)} 处:")
        for f in fixed:
            print(f)
    return new_html, bool(fixed)


def fix_missing_title(filepath: Path, html: str) -> tuple[str, bool]:
    """从文件名推断并添加 title"""
    if re.search(r"<title[^>]*>[^<]+</title>", html, re.IGNORECASE):
        return html, False

    fname = filepath.stem.replace("-", " ").replace("_", " ")
    new_title = f"<title>{fname} · 弈沐资本</title>"
    new_html = re.sub(
        r"(<head[^>]*>)",
        r"\1\n  " + new_title,
        html,
        count=1,
        flags=re.IGNORECASE,
    )
    return new_html, new_html != html


def fix_missing_back_link(filepath: Path, html: str) -> tuple[str, bool]:
    """给子页面插入返回首页链接"""
    rel = str(filepath.relative_to(PORTAL))

    matched = False
    for pattern, _ in BACK_LINK_REQUIRED:
        if pattern.search(rel):
            matched = True
            break

    if not matched:
        return html, False

    # 检查是否已有返回链接
    scan = parse_html(filepath)
    for href, _ in scan["links"]:
        base = href.split("#")[0].split("?")[0]
        if base.rstrip("/index.html") in ("", ".") or base in ("../index.html", "../../index.html"):
            return html, False

    depth = rel.count("/") - 1
    back_href = ("../" * depth + "index.html") if depth > 0 else "./index.html"

    back_a = f'<a class="back" href="{back_href}">← 返回首页</a>'

    # 插入到合适位置
    # 策略1: body 第一个 div 或 header
    m = re.search(r"(<body[^>]*>)", html, re.IGNORECASE)
    if m:
        new_html = html[:m.end()] + "\n" + back_a + "\n" + html[m.end():]
        return new_html, True

    return html, False


# ── 主流程 ────────────────────────────────────────────────────────────────


# ── 隐私红线检查（发布门禁，2026-09-28） ──────────────────────────────────
#
# 对「本次生成或修改」的 HTML 纯文本做检查，任一命中即阻断发布（sync_portal
# 收到非 0 退出码后停止推送）。历史页不在此范围（统一留到国庆按 PLAN §8.3
# 跑全量红线清单），由调用方用文件参数限定。
#
# 个股名单两个来源：
#   1. 8088 `/api/trades`：近 60 个交易日成交过的股票名称与 6 位代码
#      （该接口 `date=` 参数不生效，按 trade_date 客户端过滤）；
#   2. Vault ReviewNote frontmatter 的 `盘后持仓` 标的。
# 名单取不到时 fail closed：不验证就等于放行。
REDLINE_MACHINE_PATTERNS = [
    (re.compile(p), label)
    for p, label in [
        # 规则编号：`XXX-YYY-999`，也覆盖 `WIN-ICE-W1-001` 这类中间段含数字的形态
        (r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{3}\b", "规则编号"),
        (r"lesson_\d+", "lesson 编号"),
        (r"rules/", "rules/ 路径"),
        (r"§", "章节符号 §"),
        (r"\bR\d{1,2}\b", "红方编号 R#"),
        (r"红方", "红方"),
        (r"回执", "回执"),
        (r"sha256", "sha256"),
        (r"阅读投影", "阅读投影"),
        (r"可见时点", "可见时点"),
        (r"执行卡", "执行卡"),
        (r"门禁", "门禁"),
    ]
]
REDLINE_AMOUNT_PATTERNS = [
    (re.compile(r"\d+\s*股"), "股数"),
    (re.compile(r"[+\-−]?\d{1,3}(?:,\d{3})+(\.\d+)?"), "千分位金额"),
]
REDLINE_DIALOGUE_PATTERNS = [
    (re.compile(p), label)
    for p, label in [
        (r"与你", "对话体「与你」"),
        (r"你说", "对话体「你说」"),
        (r"弈沐原话", "对话体「弈沐原话」"),
    ]
]
REDLINE_RESIDUE_PATTERNS = [
    (re.compile(p), label)
    for p, label in [
        (r"若干笔", "脱敏残渣"),
        (r"内部集中度上限", "脱敏残渣"),
        (r"关键确认位", "脱敏残渣"),
        (r"风险处理动作", "脱敏残渣"),
        (r"可卖状态", "脱敏残渣"),
    ]
]
# 允许清单：账户层面的仓位百分比（首页实盘面板本来就公开仓位），例如
# 公开稿里的「46.66% 降到 10.41%」。只有完整「数字%」形态且不带千分位，
# 不会被金额模式命中；这里显式登记，避免以后加宽模式时误伤。
REDLINE_ALLOWED_CONTEXT = re.compile(r"\d+(?:\.\d+)?%")

# 写作原文豁免（W8 S5，开工单第二节第 6 点）：正文原样发布，不过红线。
# 生成器把写作区包进 `<div class="writing-body" data-public-writing="verbatim">`，
# 扫描器整段跳过——业绩区、每日公开页指标、周报事实区、研究报告照旧全查。
WRITING_SPAN_OPEN = re.compile(
    r'<div class="writing-body" data-public-writing="verbatim"[^>]*>', re.IGNORECASE
)

# 账户层面总额的白名单（审计回复 8 第二节第 8 条）：账户总额本来就是公开口径
# ——现网首页一直在公开，弈沐看过的预览里也有。真正要拦的是正文里的个股金额
# 与股数。所以白名单**不给"页面上的一切金额"**，只给这一个固定标记：
# 元素带上 data-public="account-total" 才跳过它的正文。
# 同样的数字出现在任何没有这个标记的地方（正文、表格、图表说明）照拦不误。
# 扫描时直接把这类元素的正文丢掉，所以它根本不会进入被扫的纯文本。
ACCOUNT_TOTAL_ELEMENT = re.compile(
    r"<\s*([a-zA-Z][\w-]*)([^>]*\bdata-public\s*=\s*[\"']account-total[\"'][^>]*)>"
    r"(.*?)<\s*/\s*\1\s*>",
    re.IGNORECASE | re.DOTALL,
)

REDLINE_TRADE_WINDOW_DATES = 60

# 本次同步链（sync_portal：首页数据 → 复盘详情页 → 手记）不生成的区块：
# 周/月复盘卡由 sync_weekly_review.py 单独产出，PORTAL_FIX_NOW §4 明确把
# 9-27 以前的历史页留给国庆全量红线清单、由弈沐决定。落在这些区块里的命中
# 记入 deferred 清单并打印，不阻断今晚发布；其余命中一律阻断。
REDLINE_DEFERRED_BLOCKS = [
    (re.compile(r'review-notes/index\.html$'),
     re.compile(r'<a href="(?:weekly|monthly)-[^"]*"[^>]*>.*?</a>', re.S | re.I)),
    (re.compile(r'index\.html$'),
     re.compile(r'<a[^>]*class="recent-review-card period-review-card[^"]*"[^>]*>.*?</a>', re.S | re.I)),
]


def _deferred_redline_spans(text: str, rel_path: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for path_re, block_re in REDLINE_DEFERRED_BLOCKS:
        if not path_re.search(rel_path):
            continue
        for match in block_re.finditer(text):
            spans.append((match.start(), match.end()))
    return spans


def _matching_div_close(html: str, start: int) -> int:
    """写作区结束的位置：按 div 嵌套配对找，别被写作正文里的内层 div 提前骗到。"""
    depth = 1
    for match in re.finditer(r"<\s*/?\s*div\b[^>]*>", html[start:], flags=re.I):
        depth += -1 if match.group(0).lstrip().startswith("</") else 1
        if depth == 0:
            return start + match.start()
    return -1


def _strip_tags_for_redline(html: str) -> tuple[str, list[int]]:
    """纯文本 + 每个字符在原始 HTML 中的位置。

    命中定位必须能映射回原始 HTML，才能判断它是否落在「本次同步链不生成」
    的历史区块里；只在纯文本上定位会在标签边界处丢失。 ``script`` / ``style``
    与注释整块跳过（内部不是可见文字），被跳过的区间不留字符。
    """
    kept: list[str] = []
    positions: list[int] = []
    index = 0
    length = len(html)
    block_pattern = re.compile(r"\s*/?>", re.I)
    while index < length:
        # 写作原文的标记要活过去标签这道关：整段豁免靠它定位，标签被剥掉就找不到了。
        opening = WRITING_SPAN_OPEN.match(html, index)
        if opening:
            closer = _matching_div_close(html, opening.end())
            # 收尾的 </div> 也要留在文本里：_scan_redline_hits 靠它判断豁免段到哪儿结束，
            # 少一个字符就会把后面的事实区一起吞掉。
            segment_end = (closer + len("</div>")) if closer != -1 else length
            for offset in range(index, segment_end):
                kept.append(html[offset])
                positions.append(offset)
            index = segment_end
            continue
        if html.startswith("<!--", index):
            close = html.find("-->", index)
            index = length if close < 0 else close + 3
            continue
        # 账户总额的标记元素必须在通用标签分支**之前**判：不然开标签先被
        # 通用分支吃掉，轮到正文时已经不知道它属于哪个元素。命中就把整段
        # （含标签与正文）跳过，它的正文因此不会进入被扫的纯文本。
        marked = ACCOUNT_TOTAL_ELEMENT.match(html, index)
        if marked:
            index = marked.end()
            continue
        if html.startswith("<", index):
            tag_end = html.find(">", index)
            if tag_end < 0:
                break
            tag_name_match = re.match(r"<\s*([a-zA-Z]+)", html[index:tag_end + 1])
            tag_name = (tag_name_match.group(1).lower() if tag_name_match else "")
            if tag_name in {"script", "style"}:
                close = re.search(
                    rf"</\s*{tag_name}\s*>", html[tag_end:], flags=re.I
                )
                index = (
                    length
                    if close is None
                    else tag_end + close.end()
                )
                continue
            index = tag_end + 1
            continue
        kept.append(html[index])
        positions.append(index)
        index += 1
    return "".join(kept), positions


def load_traded_symbols(source: str = "cloud", remote: str | None = None):
    """Return ``(names, codes)`` traded in the most recent 60 trading dates."""
    try:
        from sync_pnl_data import BridgeAPI, DEFAULT_REMOTE
    except Exception as exc:  # pragma: no cover - import wiring
        raise RuntimeError(f"redline_trade_source_unavailable:{type(exc).__name__}") from exc
    api = BridgeAPI(source=source, remote=remote or DEFAULT_REMOTE)
    try:
        rows = api.fetch("/api/trades")
    except Exception as exc:
        raise RuntimeError(f"redline_trade_source_unavailable:{type(exc).__name__}") from exc
    if not isinstance(rows, list):
        raise RuntimeError("redline_trade_source_unavailable:not_a_list")
    dates = sorted({str(row.get("trade_date") or "") for row in rows if row.get("trade_date")})
    window = set(dates[-REDLINE_TRADE_WINDOW_DATES:])
    names, codes = set(), set()
    for row in rows:
        if str(row.get("trade_date") or "") not in window:
            continue
        name = str(row.get("name") or "").strip()
        code = str(row.get("code") or "").strip()
        if name:
            names.add(name)
        if re.fullmatch(r"\d{6}", code):
            codes.add(code)
    if not names and not codes:
        raise RuntimeError("redline_trade_source_empty")
    return sorted(names), sorted(codes)


def load_position_symbols(note_path: Path | None):
    """Frontmatter `盘后持仓` 标的（名称与代码），取自 Vault ReviewNote。"""
    if note_path is None or not Path(note_path).is_file():
        return [], []
    try:
        text = Path(note_path).read_text(encoding="utf-8")
    except OSError:
        return [], []
    match = re.search(r"(?m)^盘后持仓\s*[:：]\s*(.+)$", text)
    if not match:
        return [], []
    raw = match.group(1).strip().strip('"').strip("'")
    names = re.findall(r"[\u4e00-\u9fffA-Za-z]{2,}", raw)
    codes = re.findall(r"\b\d{6}\b", raw)
    return names, codes


def check_redlines_static(text: str) -> list[str]:
    """Static red lines only (no per-account name/code lists).

    Used by generators to decide whether a scraped legacy summary may stay in
    a live aggregate index.
    """
    return check_redlines(text, [], [])


def _scan_redline_hits(text: str, names, codes) -> list[tuple[int, int, str]]:
    """Return ``(start, end, description)`` for each red-line hit."""
    hits: list[tuple[int, int, str]] = []
    allowed_spans = [
        (m.start(), m.end())
        for m in REDLINE_ALLOWED_CONTEXT.finditer(text)
    ]
    for opener in WRITING_SPAN_OPEN.finditer(text):
        closer = _matching_div_close(text, opener.end())
        allowed_spans.append(
            (opener.start(),
             (closer + len("</div>")) if closer != -1 else len(text))
        )

    def _covered(start: int, end: int) -> bool:
        return any(a <= start and end <= b for a, b in allowed_spans)

    def _scan(patterns, prefix):
        for pattern, label in patterns:
            for m in pattern.finditer(text):
                if _covered(m.start(), m.end()):
                    continue
                hits.append((m.start(), m.end(),
                             f"{prefix}:{label}: …{text[max(0, m.start() - 12):m.end() + 12]}…"))

    _scan(REDLINE_MACHINE_PATTERNS, "机器话")
    _scan(REDLINE_AMOUNT_PATTERNS, "金额股数")
    _scan(REDLINE_DIALOGUE_PATTERNS, "对话体")
    _scan(REDLINE_RESIDUE_PATTERNS, "脱敏残渣")
    for name in names:
        for m in re.finditer(re.escape(name), text):
            hits.append((m.start(), m.end(),
                         f"个股名称:{name}: …{text[max(0, m.start() - 12):m.end() + 12]}…"))
    for code in codes:
        for m in re.finditer(rf"(?<!\d){re.escape(code)}(?!\d)", text):
            hits.append((m.start(), m.end(),
                         f"个股代码:{code}: …{text[max(0, m.start() - 12):m.end() + 12]}…"))
    return hits


def check_redlines(text: str, names, codes) -> list[str]:
    """Return red-line hit descriptions for one page's visible text."""
    return [hit for _start, _end, hit in _scan_redline_hits(text, names, codes)]



SITE_HREF = re.compile(r"""<a\b[^>]*\bhref\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


def check_site_links(files: list[Path]) -> list[str]:
    """站内 href 必须指到一个真实存在的文件，否则报死链（审计回复 10 第二节第 11 条）。

    只查站内相对链接：外部 http(s)、`#锚点`、`mailto:` 一律跳过。
    目录链接按"该目录下必须有 index.html"判断——线上 GitHub Pages 上
    `/weekly/` 只有在 `weekly/index.html` 存在时才打得开。
    """
    problems: list[str] = []
    for path in files:
        if not path.is_file() or path.suffix != ".html":
            continue
        html = path.read_text(encoding="utf-8", errors="replace")
        for href in SITE_HREF.findall(html):
            target = href.strip()
            if not target or target.startswith(("#", "http://", "https://",
                                                "mailto:", "javascript:", "data:")):
                continue
            target = target.split("#", 1)[0].split("?", 1)[0]
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            if resolved.is_dir():
                resolved = resolved / "index.html"
            if not resolved.exists():
                rel = str(path.relative_to(PORTAL)) if PORTAL in path.parents else str(path)
                problems.append(f"{rel} → {href}")
    return problems


def run_redline(files: list[Path], args) -> int:
    """Privacy red-line gate: any hit blocks the publish."""
    print(f"\n{'='*60}")
    print("Portal 隐私红线检查（发布门禁）")
    print(f"根目录: {PORTAL}")
    print(f"检查文件: {len(files)} 个")
    print(f"个股名单来源: 8088 /api/trades（近 {REDLINE_TRADE_WINDOW_DATES} 个交易日）"
          " + ReviewNote frontmatter 盘后持仓")
    print(f"{'='*60}\n")

    try:
        names, codes = load_traded_symbols(
            source=getattr(args, "redline_source", "cloud"),
            remote=getattr(args, "redline_remote", None),
        )
    except RuntimeError as exc:
        print(f"  ERROR 个股名单不可用（fail closed）: {exc}")
        return 2
    note_names, note_codes = load_position_symbols(
        Path(args.review_note) if getattr(args, "review_note", None) else None
    )
    names = sorted(set(names) | set(note_names))
    codes = sorted(set(codes) | set(note_codes))
    print(f"  个股名单: {len(names)} 个名称 / {len(codes)} 个代码")

    all_hits: dict[Path, list[str]] = {}
    deferred: dict[Path, list[str]] = {}
    for fp in sorted(files):
        try:
            html = fp.read_text(encoding="utf-8")
        except OSError as exc:
            all_hits[fp] = [f"无法读取: {exc}"]
            continue
        text, positions = _strip_tags_for_redline(html)
        rel = str(fp.relative_to(PORTAL)) if PORTAL in fp.parents else str(fp)
        located_hits = _scan_redline_hits(text, names, codes)
        if not located_hits:
            continue
        spans = _deferred_redline_spans(html, rel)
        keep, defer = [], []
        for start, end, description in located_hits:
            raw_start = positions[start] if start < len(positions) else 0
            raw_end = positions[end - 1] + 1 if 0 < end <= len(positions) else raw_start
            if any(a <= raw_start and raw_end <= b for a, b in spans):
                defer.append(description)
            else:
                keep.append(description)
        if defer:
            deferred[fp] = defer
        if keep:
            all_hits[fp] = keep

    if deferred:
        print(f"\n  注: {sum(len(v) for v in deferred.values())} 条命中落在本次同步链不生成的"
              "历史区块（周/月复盘卡，由 sync_weekly_review.py 产出，PORTAL_FIX_NOW §4 "
              "留待国庆全量红线清单），不阻断本次发布：")
        for fp, hits in deferred.items():
            rel = fp.relative_to(PORTAL) if PORTAL in fp.parents else fp
            print(f"    {rel}: {len(hits)} 条")

    # 站内死链与红线一样阻断发布（审计回复 10 第二节第 11 条）：
    # 页脚挂一个 404 的链接，读者点进去才发现，比不挂更糟。
    dead_links = check_site_links([fp for fp in files if fp.suffix == ".html"])
    if dead_links:
        print(f"\n{'─'*60}")
        print(f"  DEAD LINK — {len(dead_links)} 处站内链接指向不存在的文件（阻断发布）")
        print(f"{'─'*60}")
        for item in dead_links[:40]:
            print(f"    {item}")
        if len(dead_links) > 40:
            print(f"    …另有 {len(dead_links) - 40} 处")

    if not all_hits and not dead_links:
        print("\n  红线检查零命中，站内链接全部可达，可以发布。")
        return 0
    if not all_hits:
        return 1

    print(f"\n{'─'*60}")
    print(f"  RED LINE — {len(all_hits)} 个文件命中（阻断发布）")
    print(f"{'─'*60}")
    for fp, hits in all_hits.items():
        rel = fp.relative_to(PORTAL) if PORTAL in fp.parents or fp == PORTAL else fp
        print(f"\n  {rel}")
        for hit in hits[:20]:
            print(f"    {hit}")
        if len(hits) > 20:
            print(f"    …另有 {len(hits) - 20} 条")
    return 1


def get_files(sections_only: bool) -> list[Path]:
    if sections_only:
        bases = ["index.html", "review-notes/index.html", "report/index.html",
                 "insights/index.html", "methodology/index.html", "tools/index.html"]
        return [PORTAL / p for p in bases]
    return list(PORTAL.rglob("*.html"))


def run(args) -> int:
    redline_files: list[Path] = []
    if args.redline:
        candidates = [Path(item) for item in (args.files or [])]
        if candidates:
            redline_files = [
                path if path.is_absolute() else PORTAL / path for path in candidates
            ]
        else:
            redline_files = get_files(args.sections)
    if args.redline:
        return run_redline(redline_files, args)
    files = get_files(args.sections)
    print(f"\n{'='*60}")
    print(f"Portal 发布前检查  {datetime.now():%Y-%m-%d %H:%M}")
    print(f"根目录: {PORTAL}")
    print(f"检查文件: {len(files)} 个")
    if args.sections:
        print("模式: 仅入口页面")
    if args.fix and args.dry:
        print("模式: 修复预览（不写入）")
    elif args.fix:
        print("模式: 检查 + 自动修复")
    print(f"{'='*60}\n")

    all_issues: dict[Path, list] = {}
    fixed_files: list[str] = []
    suppressed_total = 0
    verbose_suppressions: list[dict] = []

    for fp in sorted(files):
        rel = fp.relative_to(PORTAL)
        try:
            html = fp.read_text(encoding="utf-8")
        except Exception as e:
            all_issues.setdefault(rel, []).append(("ERROR", [f"  无法读取: {e}"]))
            continue

        scan = parse_html(fp)
        if scan["error"]:
            all_issues.setdefault(rel, []).append(("ERROR", [f"  解析错误: {scan['error']}"]))
            continue

        issues: list = []

        broken = check_broken_links(fp, scan)
        if broken:
            issues.append(("ERROR", broken))

        dup = check_duplicate_ids(scan)
        if dup:
            issues.append(("ERROR", dup))

        if not scan.get("title"):
            issues.append(("WARN", ["  缺少 <title>"]))

        back = check_missing_back_link(fp, scan)
        if back:
            issues.append(("WARN", back))

        ph, sp_items = check_placeholders(fp, scan, args.verbose)
        if ph:
            issues.append(("WARN", ph))
        suppressed_total += len(sp_items)
        if args.verbose and sp_items:
            for item in sp_items:
                verbose_suppressions.append(item)

        if issues:
            all_issues[rel] = issues

        # 自动修复
        if args.fix and not args.dry and issues:
            new_html = html
            changed = False

            new_html, c = fix_duplicate_ids(new_html)
            changed = changed or c

            new_html, c = fix_missing_title(fp, new_html)
            changed = changed or c

            new_html, c = fix_missing_back_link(fp, new_html)
            changed = changed or c

            if changed:
                fp.write_text(new_html, encoding="utf-8")
                fixed_files.append(str(rel))
                # fix 模式下，能自动修的问题不出现在报告中
                cleaned = []
                for sev, lines in issues:
                    if sev == "ERROR" and any("重复 id" in l for l in lines):
                        continue  # 已自动修复
                    if sev == "WARN" and "缺少 <title>" in lines[0]:
                        continue  # 已自动修复
                    if sev == "WARN" and "返回首页链接" in lines[0]:
                        continue  # 已自动修复
                    cleaned.append((sev, lines))
                if cleaned:
                    all_issues[rel] = cleaned
                else:
                    all_issues.pop(rel, None)

    # ── 报告 ─────────────────────────────────────────────────────────────

    if suppressed_total > 0:
        print(f"\n  注: 白名单抑制 {suppressed_total} 条（加 --verbose 查看详情）")

    if not all_issues:
        if args.verbose and verbose_suppressions:
            print(f"\n{'─'*60}")
            print(f"  抑制详情（--verbose）")
            print(f"{'─'*60}")
            current_file = ""
            for item in verbose_suppressions:
                if item["file"] != current_file:
                    print(f"\n  {item['file']}")
                    current_file = item["file"]
                print(f"    [{item['reason']}] ...{item['ctx'][1:-1]}...")
        print("\n  检查完成，未发现问题。")
        return 0

    errors = {k: v for k, v in all_issues.items() if any(s == "ERROR" for s, _ in v)}
    warns = {k: v for k, v in all_issues.items() if all(s == "WARN" for s, _ in v)}

    if errors:
        print(f"{'─'*60}")
        print(f"  ERROR — {len(errors)} 个文件（阻断发布）")
        print(f"{'─'*60}")
        for rel, file_issues in errors.items():
            print(f"\n  {rel}")
            for sev, lines in file_issues:
                for line in lines:
                    print(f"    {line}")

    if warns:
        print(f"\n{'─'*60}")
        print(f"  WARN — {len(warns)} 个文件（非阻断）")
        print(f"{'─'*60}")
        for rel, file_issues in warns.items():
            print(f"\n  {rel}")
            for sev, lines in file_issues:
                for line in lines:
                    print(f"    {line}")

    if args.verbose and verbose_suppressions:
        print(f"\n{'─'*60}")
        print(f"  抑制详情（--verbose）")
        print(f"{'─'*60}")
        current_file = ""
        for item in verbose_suppressions:
            if item["file"] != current_file:
                print(f"\n  {item['file']}")
                current_file = item["file"]
            print(f"    [{item['reason']}] ...{item['ctx'][1:-1]}...")

    total_issues = sum(len(v) for v in all_issues.values())
    print(f"\n{'─'*60}")
    print(f"  汇总")
    print(f"  检查文件: {len(files)}")
    print(f"  ERROR 文件: {len(errors)}")
    print(f"  WARN 文件: {len(warns)}")
    print(f"  总问题数: {total_issues}")

    if fixed_files:
        print(f"\n  自动修复: {len(fixed_files)} 个文件")
        for f in fixed_files:
            print(f"    ✓ {f}")

    if args.fix and not args.dry:
        print(f"\n  注: 低风险问题已自动修复（重复 id / 缺 title / 缺返回入口）")
        print(f"      如需预览，请加 --dry 运行")

    return len(errors)


def self_test() -> bool:
    """端到端自检：走 parse_html + check_placeholders 实际检测路径

    验证：
    - 真实占位文案（TODO / placeholder / debugger / console.log）被检出
    - 白名单内容（CSS ::placeholder / JS readyState === 'loading'）被抑制
    """
    import tempfile

    # 每个用例: (html_content, filepath_name, should_catch, should_suppress, description)
    test_cases = [
        # 1. 真实 TODO:
        (
            "<html><head><title>Test</title></head><body>TODO: 记得修复这个 bug</body></html>",
            "test_todo.html",
            True, False,
            "正文中的 TODO:"
        ),
        # 2. 真实 placeholder
        (
            "<html><head><title>Test</title></head><body>请填写 placeholder 字段</body></html>",
            "test_placeholder.html",
            True, False,
            "正文中的 placeholder"
        ),
        # 3. 真实 debugger;
        (
            "<html><head><title>Test</title></head><body>debugger; 请调试</body></html>",
            "test_debugger.html",
            True, False,
            "正文中的 debugger;"
        ),
        # 4. 真实 console.log
        (
            "<html><head><title>Test</title></head><body>console.log('debug') 这里有调试代码</body></html>",
            "test_consolelog.html",
            True, False,
            "正文中的 console.log"
        ),
        # 5. CSS ::placeholder（应被白名单抑制）
        (
            "<html><head><title>Test</title><style>input::placeholder{color:gray}</style></head>"
            "<body>正常内容</body></html>",
            "test_css_placeholder.html",
            False, True,
            "CSS ::placeholder → 应被抑制"
        ),
        # 6. JS readyState === 'loading'（应被白名单抑制）
        (
            "<html><head><title>Test</title></head><body><script>"
            "if (document.readyState === 'loading') { init(); }"
            "</script></body></html>",
            "index.html",   # 必须精确匹配白名单路径规则
            False, True,
            "JS readyState === 'loading' → 应被抑制"
        ),
    ]

    import tempfile

    print("\n=== portal_check 自检（端到端） ===")
    all_pass = True

    for html_content, fname, expect_catch, expect_suppress, desc in test_cases:
        # 所有测试文件写入 temp dir（避免覆盖 PORTAL 下真实文件）
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / fname
            tmp.write_text(html_content, encoding="utf-8")
            scan = parse_html(tmp)
            issues, suppressed = check_placeholders(tmp, scan, collect_suppressed=True)

            caught = len(issues) > 0
            was_suppressed = len(suppressed) > 0

            ok = (caught == expect_catch) and (was_suppressed == expect_suppress)
            if ok:
                print(f"  ✓ {desc}")
            else:
                print(f"  ✗ {desc}")
                print(f"    期望: caught={expect_catch}, suppressed={expect_suppress}")
                print(f"    实际: caught={caught}, suppressed={was_suppressed}")
                if issues:
                    print(f"    issues: {issues}")
                if suppressed:
                    print(f"    suppressed: {len(suppressed)} items")
                all_pass = False

    print(f"\n{'✓ 全部通过' if all_pass else '✗ 有失败项'}.")
    return all_pass


def main():
    p = argparse.ArgumentParser(description="Portal 发布前检查工具")
    p.add_argument("--fix", action="store_true", help="自动修复低风险问题（重复 id / 缺 title / 缺返回入口）")
    p.add_argument("--dry", action="store_true", help="预览修复，不写入（需配合 --fix）")
    p.add_argument("--sections", action="store_true", help="只检查入口页面")
    p.add_argument("--verbose", action="store_true", help="显示被白名单抑制的条目详情")
    p.add_argument("--self-test", action="store_true", help="运行占位文案检测自检")
    p.add_argument(
        "--redline",
        action="store_true",
        help="隐私红线门禁：命中即阻断（个股名/代码、金额股数、机器话、对话体、脱敏残渣）",
    )
    p.add_argument(
        "files",
        nargs="*",
        help="限定红线检查的文件（相对 portal 根或绝对路径）；不给则检查全部 HTML",
    )
    p.add_argument(
        "--redline-source",
        choices=["cloud", "local"],
        default=os.environ.get("PORTAL_DATA_SOURCE", "cloud"),
        help="个股名单数据源：cloud=Hermes；local=本地 bridge",
    )
    p.add_argument(
        "--redline-remote",
        default=os.environ.get("PORTAL_REMOTE"),
        help="cloud 模式 SSH 目标",
    )
    p.add_argument(
        "--review-note",
        help="附带其 frontmatter 盘后持仓标的的 Vault ReviewNote 路径",
    )
    args = p.parse_args()

    if args.dry and not args.fix:
        print("错误: --dry 需要配合 --fix 使用")
        sys.exit(1)

    if args.self_test:
        sys.exit(0 if self_test() else 1)

    rc = run(args)
    sys.exit(rc)


if __name__ == "__main__":
    main()
