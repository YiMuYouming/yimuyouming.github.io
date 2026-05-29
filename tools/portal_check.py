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

# ── 需要返回入口的子页面 ──────────────────────────────────────────────────

BACK_LINK_REQUIRED = [
    (re.compile(r"review-notes/\d{4}-\d{2}-\d{2}\.html$"), "复盘笔记"),
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
        if not self._in_style:
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


def check_placeholders(scan: dict) -> list[str]:
    """检测占位/调试文案"""
    text = scan.get("text", "")
    if not text:
        return []

    for pattern in PLACEHOLDER_PATTERNS:
        m = pattern.search(text)
        if m:
            start = max(0, m.start() - 30)
            end = min(len(text), m.end() + 30)
            ctx = text[start:end].replace("\n", " ").strip()
            return [f"  占位/调试文案: ...{ctx}..."]
    return []


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

def get_files(sections_only: bool) -> list[Path]:
    if sections_only:
        bases = ["index.html", "review-notes/index.html", "report/index.html",
                 "insights/index.html", "methodology/index.html", "tools/index.html"]
        return [PORTAL / p for p in bases]
    return list(PORTAL.rglob("*.html"))


def run(args) -> int:
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

        ph = check_placeholders(scan)
        if ph:
            issues.append(("WARN", ph))

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

    if not all_issues:
        print("  检查完成，未发现问题。")
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


def main():
    p = argparse.ArgumentParser(description="Portal 发布前检查工具")
    p.add_argument("--fix", action="store_true", help="自动修复低风险问题（重复 id / 缺 title / 缺返回入口）")
    p.add_argument("--dry", action="store_true", help="预览修复，不写入（需配合 --fix）")
    p.add_argument("--sections", action="store_true", help="只检查入口页面")
    args = p.parse_args()

    if args.dry and not args.fix:
        print("错误: --dry 需要配合 --fix 使用")
        sys.exit(1)

    rc = run(args)
    sys.exit(rc)


if __name__ == "__main__":
    main()
