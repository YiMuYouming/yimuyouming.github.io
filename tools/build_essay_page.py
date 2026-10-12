#!/usr/bin/env python3
"""Render published long-form essays (Vault ``公开写作/文章/``) into ``essays/<slug>.html``.

写作原文发布：正文一个字不改、不删敏，这里只做排版（Markdown → HTML）。
图片按正文里的相对路径从 Vault 拷到 ``essays/<slug>/``，页面只引用拷贝。

用法：
  # 正式：按写作索引生成全部已发布长文
  python3 tools/build_essay_page.py --writing-index data/writing-index.json --writing-root <Vault 公开写作>
  # 预览：单篇，草稿也能出页，页面带「预览 · 未发布」
  python3 tools/build_essay_page.py --source <文章.md> --preview --out out/essay-preview/essays
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT_ROOT / "essays"
DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


# ---------------------------------------------------------------- frontmatter

def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not match:
        return {}, text
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line[:1] in " \t#":
            continue
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.split(" #", 1)[0].strip().strip('"').strip("'")
    return meta, text[match.end():]


# ---------------------------------------------------------------- markdown

_INLINE_RE = re.compile(
    r"(?P<code>`[^`]+`)"
    r"|(?P<bold>\*\*[^*]+\*\*)"
    r"|(?P<italic>(?<!\*)\*[^*\n]+\*(?!\*))"
    r"|(?P<link>\[[^\]]+\]\([^)\s]+\))"
)


def _esc(text: str) -> str:
    return html.escape(text, quote=False)


def inline(text: str) -> str:
    out, pos = [], 0
    for m in _INLINE_RE.finditer(text):
        out.append(_esc(text[pos:m.start()]))
        token = m.group(0)
        if m.group("code"):
            out.append("<code>" + _esc(token[1:-1]) + "</code>")
        elif m.group("bold"):
            out.append("<strong>" + _esc(token[2:-2]) + "</strong>")
        elif m.group("italic"):
            out.append("<em>" + _esc(token[1:-1]) + "</em>")
        else:
            label, url = re.match(r"\[([^\]]+)\]\(([^)\s]+)\)", token).groups()
            out.append(f'<a href="{html.escape(url)}">{_esc(label)}</a>')
        pos = m.end()
    out.append(_esc(text[pos:]))
    return "".join(out)


IMG_MD = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")
IMG_WIKI = re.compile(r"^!\[\[([^\]|]+)(?:\|([^\]]*))?\]\]$")


def render_markdown(body: str, *, resolve_image) -> tuple[str, list[str]]:
    """Return (html, headings). ``resolve_image(src) -> public url``."""
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    blocks = [b.strip("\n") for b in re.split(r"\n\s*\n", body) if b.strip()]
    out: list[str] = []
    headings: list[str] = []
    figure_no = 0
    for block in blocks:
        lines = [ln.rstrip() for ln in block.splitlines() if ln.strip()]
        first = lines[0]
        if len(lines) == 1 and re.fullmatch(r"-{3,}|\*{3,}", first.strip()):
            out.append("<hr>")
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", first)
        if heading and len(lines) == 1:
            level = len(heading.group(1))
            text = heading.group(2).strip()
            if level == 2:
                headings.append(text)
            out.append(f"<h{level}>{inline(text)}</h{level}>")
            continue
        if len(lines) == 1 and (IMG_MD.match(first) or IMG_WIKI.match(first)):
            m = IMG_MD.match(first)
            alt, src = (m.group(1), m.group(2)) if m else (
                IMG_WIKI.match(first).group(2) or "", IMG_WIKI.match(first).group(1))
            figure_no += 1
            url = resolve_image(src.strip())
            cap = f"<figcaption>{_esc(alt)}</figcaption>" if alt else ""
            out.append(f'<figure><a href="{url}" target="_blank" rel="noopener"><img src="{url}" alt="{html.escape(alt)}" loading="lazy"></a>{cap}</figure>')
            continue
        if all(ln.startswith(">") for ln in lines):
            inner = "<br>".join(inline(ln.lstrip("> ").rstrip()) for ln in lines)
            out.append(f"<blockquote><p>{inner}</p></blockquote>")
            continue
        if all(re.match(r"^[-*]\s+", ln) for ln in lines):
            items = "".join("<li>" + inline(re.sub(r"^[-*]\s+", "", ln)) + "</li>" for ln in lines)
            out.append(f"<ul>{items}</ul>")
            continue
        if all(re.match(r"^\d+\.\s+", ln) for ln in lines):
            items = "".join("<li>" + inline(re.sub(r"^\d+\.\s+", "", ln)) + "</li>" for ln in lines)
            out.append(f"<ol>{items}</ol>")
            continue
        # 整段只有一个加粗句：作为小标题（排版层面，文字不动）
        if len(lines) == 1 and re.fullmatch(r"\*\*[^*]+\*\*", first):
            out.append(f'<h3 class="sub">{_esc(first[2:-2])}</h3>')
            continue
        # 段内单换行在原文里是有意的断句，保留为换行
        out.append("<p>" + "<br>".join(inline(ln) for ln in lines) + "</p>")
    return "\n".join(out), headings


def drop_leading_h1(body: str, title: str) -> str:
    stripped = body.lstrip()
    m = re.match(r"^#\s+(.+)\n", stripped)
    if m and m.group(1).strip() == title.strip():
        return stripped[m.end():]
    return body


def count_chars(body: str) -> int:
    text = re.sub(r"<!--.*?-->|!\[[^\]]*\]\([^)]*\)|[#>*`\-]", "", body, flags=re.DOTALL)
    cjk = len(re.findall(r"[一-鿿]", text))
    words = len(re.findall(r"[A-Za-z0-9]+", text))
    return cjk + words


# ---------------------------------------------------------------- page

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · 弈沐资本</title>
<meta name="description" content="{summary_attr}">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Noto+Serif+SC:wght@400;600;700&display=swap" rel="stylesheet">
<style>
:root{{--ink:#1f2328;--sub:#6b7280;--faint:#9ca3af;--line:#e5e7eb;--paper:#faf9f7;--accent:#b45309;--mark:rgba(217,119,6,.16)}}
*{{box-sizing:border-box}}
html{{-webkit-text-size-adjust:100%}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Noto Serif SC","Songti SC",serif;line-height:1.7;font-feature-settings:"palt" 0}}
a{{color:inherit}}
.bar{{max-width:1040px;margin:0 auto;padding:22px 16px 0;display:flex;align-items:baseline;justify-content:space-between;gap:12px;font-size:14px}}
.bar a{{text-decoration:none;color:var(--ink);letter-spacing:.06em;font-weight:600}}
.bar span{{color:var(--sub);font-size:13px}}
.preview{{display:inline-block;margin-left:10px;font-size:12px;font-weight:400;letter-spacing:0;border:1px dashed var(--accent);color:var(--accent);border-radius:999px;padding:1px 9px}}
.col{{max-width:680px;margin:0 auto;padding:0 16px}}
header.head{{padding:72px 0 34px;border-bottom:1px solid var(--line);margin-bottom:44px}}
.kicker{{font-family:"JetBrains Mono",monospace;font-size:12px;letter-spacing:.14em;color:var(--accent);text-transform:uppercase}}
h1.title{{font-size:clamp(28px,6vw,40px);line-height:1.3;font-weight:700;letter-spacing:.02em;margin:14px 0 16px;text-wrap:balance}}
.deck{{font-size:17px;color:var(--sub);line-height:1.8;margin:0 0 22px}}
.meta{{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13px;color:var(--sub)}}
.meta b{{color:var(--ink);font-weight:600}}
.writing-body{{font-size:17.5px;line-height:2;counter-reset:sec;text-align:justify}}
.writing-body p{{margin:0 0 1.3em}}
.writing-body > p:first-child{{font-size:21px;line-height:1.85;font-weight:600;text-align:left;margin-bottom:1.6em}}
.writing-body h2{{font-size:23px;line-height:1.4;margin:2.8em 0 1em;font-weight:700;letter-spacing:.02em;counter-increment:sec}}
.writing-body h2::before{{content:counter(sec,decimal-leading-zero);display:block;font-family:"JetBrains Mono",monospace;font-size:12px;font-weight:500;letter-spacing:.14em;color:var(--accent);margin-bottom:6px}}
.writing-body h3{{font-size:19px;margin:2em 0 .8em}}
.writing-body h3.sub{{font-size:18.5px;line-height:1.6;margin:2.2em 0 .9em;padding-left:14px;border-left:3px solid var(--accent)}}
.writing-body strong{{font-weight:700;background:linear-gradient(transparent 62%,var(--mark) 0)}}
.writing-body code{{font-family:"JetBrains Mono",monospace;font-size:.86em;background:#f1efeb;border-radius:4px;padding:1px 5px}}
.writing-body hr{{border:0;width:56px;height:1px;background:var(--faint);margin:3.2em 0 2.4em}}
.writing-body blockquote{{margin:1.6em 0;padding:2px 0 2px 20px;border-left:2px solid var(--accent);color:var(--sub)}}
.writing-body blockquote p{{margin:0}}
.writing-body ul,.writing-body ol{{margin:0 0 1.3em;padding-left:1.4em}}
.writing-body li{{margin:.3em 0}}
.writing-body figure{{margin:2.6em 0 2.8em;width:min(920px,calc(100vw - 32px));position:relative;left:50%;transform:translateX(-50%)}}
.writing-body figure img{{display:block;width:100%;height:auto;border:1px solid var(--line);border-radius:12px;background:#f7f5f3}}
.writing-body figcaption{{margin-top:12px;text-align:center;font-size:13px;color:var(--sub);letter-spacing:.04em}}
.writing-body > p:last-child::after{{content:"";display:inline-block;width:.55em;height:.55em;background:var(--accent);margin-left:.5em;vertical-align:.08em}}
footer{{margin-top:72px;padding:26px 0 64px;border-top:1px solid var(--line);font-size:13px;color:var(--faint);display:flex;justify-content:space-between;align-items:baseline;gap:16px;flex-wrap:wrap}}
footer a.home{{color:var(--ink);text-decoration:none;font-weight:600;letter-spacing:.04em}}
footer p{{margin:0}}
@media(max-width:600px){{
  header.head{{padding:44px 0 26px;margin-bottom:32px}}
  .writing-body{{font-size:16.5px;line-height:1.95;text-align:left}}
  .writing-body > p:first-child{{font-size:19px}}
  .writing-body h2{{font-size:21px}}
  .writing-body figure img{{border-radius:8px}}
}}
</style>
</head>
<body>
<div class="bar"><a href="{home}">弈沐资本</a><span>成长与思想 · 长文{preview}</span></div>
<main class="col">
<header class="head">
  <div class="kicker">Essay · {date_dot}</div>
  <h1 class="title">{title}</h1>
  {deck}
  <div class="meta"><span><b>弈沐</b></span><span>约 {chars} 字 · 读完约 {minutes} 分钟</span>{asof}</div>
</header>
<article>
<div class="writing-body" data-public-writing="verbatim">
{body}
</div>
</article>
<footer>
  <a class="home" href="{home}">← 弈沐资本</a>
  <p>个人实盘记录与思考，不构成投资建议。</p>
</footer>
</main>
</body>
</html>
"""


def slug_for(meta: dict[str, str], source: Path) -> str:
    if meta.get("slug"):
        return re.sub(r"[^A-Za-z0-9-]+", "-", meta["slug"]).strip("-").lower()
    m = DATE_RE.search(source.stem) or DATE_RE.search(meta.get("created", ""))
    if not m:
        raise ValueError(f"essay_slug_missing:{source.name}（文件名需以 YYYY-MM-DD 开头或写 slug）")
    return "-".join(m.groups())


def build_essay(source: Path, out_dir: Path, *, preview: bool = False, home: str = "../index.html",
                slug: str | None = None) -> dict[str, Any]:
    text = source.read_text(encoding="utf-8")
    meta, body = split_frontmatter(text)
    status = meta.get("status", "")
    if status != "published" and not preview:
        raise ValueError(f"essay_not_published:{source.name}（status={status or '缺失'}）")
    title = meta.get("title") or source.stem
    slug = slug or slug_for(meta, source)
    body = drop_leading_h1(body, title)
    asset_dir = out_dir / slug

    def resolve(src: str) -> str:
        if re.match(r"^[a-z]+://", src):
            return html.escape(src)
        candidates = [source.parent / src, source.parent / "附件" / src]
        found = next((c for c in candidates if c.is_file()), None)
        if found is None:
            raise ValueError(f"essay_image_missing:{src}")
        asset_dir.mkdir(parents=True, exist_ok=True)
        # 发布用 ASCII 文件名（fig1.png …）：中文名经 URL 编码后，门户的链接检查器会判成死链
        name = f"fig{len(covers) + 1}{found.suffix.lower()}"
        shutil.copy2(found, asset_dir / name)
        return f"{quote(slug)}/{name}"

    covers: list[str] = []

    def resolve_and_track(src: str) -> str:
        url = resolve(src)
        covers.append(url)
        return url

    body_html, _ = render_markdown(body, resolve_image=resolve_and_track)
    lede_match = re.search(r"<p>(.*?)</p>", body_html, re.DOTALL)
    lede = re.sub(r"<[^>]+>", "", (lede_match.group(1) if lede_match else "").replace("<br>", "\n"))
    chars = count_chars(body)
    date = meta.get("published_at") or meta.get("created") or slug[:10]
    asof = meta.get("data_asof", "").split("（")[0].split("(")[0].strip()
    summary = meta.get("summary", "")
    page = PAGE.format(
        title=_esc(title),
        summary_attr=html.escape(summary),
        home=home,
        preview='<span class="preview">预览 · 未发布</span>' if preview and status != "published" else "",
        date_dot=_esc(date.replace("-", ".")),
        deck=f'<p class="deck">{_esc(summary)}</p>' if summary else "",
        chars=str(chars),
        minutes=max(1, round(chars / 400)),
        asof=f"<span>数据截至 {_esc(asof)}</span>" if asof else "",
        body=body_html,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{slug}.html"
    target.write_text(page, encoding="utf-8")
    rel = out_dir.name
    return {
        "slug": slug, "title": title, "date": date, "summary": summary,
        "lede": html.unescape(lede), "chars": chars,
        "href": f"{rel}/{slug}.html",
        "cover": f"{rel}/{covers[0]}" if covers else "",
        "target": str(target),
    }


def essays_from_index(index_path: Path, root: Path) -> list[Path]:
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    return [root / e["path"] for e in payload.get("entries", [])
            if e.get("kind") == "essay" and e.get("status") == "published"]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="生成长文页（公开写作/文章 → essays/）")
    p.add_argument("--source", help="单篇文章 .md")
    p.add_argument("--writing-index", help="data/writing-index.json：生成其中全部已发布长文")
    p.add_argument("--writing-root", help="Vault 公开写作/ 目录（配合 --writing-index）")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--preview", action="store_true", help="允许草稿出页，页面标「预览 · 未发布」")
    p.add_argument("--home", default="../index.html")
    p.add_argument("--manifest", default=str(PROJECT_ROOT / "data" / "essays.json"),
                   help="首页读的长文清单（标题、首段、封面）")
    args = p.parse_args(argv)
    sources: list[Path] = []
    if args.source:
        sources.append(Path(args.source).expanduser())
    if args.writing_index:
        if not args.writing_root:
            p.error("--writing-index 需要同时给 --writing-root")
        sources += essays_from_index(Path(args.writing_index), Path(args.writing_root).expanduser())
    if not args.source and not args.writing_index:
        p.error("给 --source 或 --writing-index")
    records = []
    try:
        for src in sources:
            rec = build_essay(src, Path(args.out), preview=args.preview, home=args.home)
            print(f"essay: {src.name} → {rec.pop('target')}")
            records.append(rec)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    records.sort(key=lambda r: (r["date"], r["slug"]), reverse=True)
    manifest = Path(args.manifest)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"schema": "essays.v1", "essays": records},
                                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"essays manifest: {len(records)} 篇 → {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
