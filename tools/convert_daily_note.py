#!/usr/bin/env python3
"""Generate public Daily Notes pages from Vault ReviewNotes.

Daily Notes are a public reading layer, not a content SSOT. Market Watch may
draft candidates in its watch note, but the source of truth for this converter
is the Vault ReviewNote:

- §一 `### 一句话结论` -> 今日一句话 and home summary card.
- §二 `### 今日认知` first item -> 今日一个认知.
- §三 `**总基调**` or `### 明日观察` -> 明日只看什么.
- frontmatter market fields -> 今日市场状态.

The generator builds a public-safe page from the ReviewNote; the operator can
pass a short feeling paragraph and review the generated page before publishing.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from html import escape as html_escape
from pathlib import Path

import convert_review


PORTAL = Path(__file__).resolve().parent.parent
DAILY_NOTES = PORTAL / "daily-notes"


DISCLAIMER = "个人交易系统复盘与认知记录，不构成投资建议。"


@dataclass
class DailyNote:
    date: str
    weekday: str
    title: str
    summary: str
    market_status: str
    market_facts: list[str]
    cognition_title: str
    cognition_evidence: str
    cognition_action: str
    system_voice: str
    watch_items: list[str]
    tag: str

    def as_dict(self) -> dict:
        return {
            "date": self.date,
            "weekday": self.weekday,
            "title": self.title,
            "summary": self.summary,
            "market_status": self.market_status,
            "market_facts": self.market_facts,
            "cognition_title": self.cognition_title,
            "cognition_evidence": self.cognition_evidence,
            "cognition_action": self.cognition_action,
            "system_voice": self.system_voice,
            "watch_items": self.watch_items,
            "tag": self.tag,
        }


NOTE_CSS = """*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#F7F5F3;--paper:#FFFFFF;--paper2:#FAFAF9;--line:#E5E2DE;--line2:#F0EEEC;--text:#2D2926;--muted:#5C5652;--faint:#8A8480;--accent:#D97706;--accent2:#B45309;--red:#DC2626;--green:#059669;--blue:#2563EB}
html{scroll-behavior:smooth}
body{font:15px/1.7 system-ui,-apple-system,"Noto Sans SC",sans-serif;background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
.note-topbar{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:12px;padding:13px 22px;background:rgba(247,245,243,.88);border-bottom:1px solid var(--line);backdrop-filter:blur(12px)}
.note-topbar a{font-size:13px;color:var(--muted);border:1px solid var(--line);border-radius:7px;padding:4px 10px;background:rgba(255,255,255,.58)}
.note-topbar strong{font-size:15px;color:var(--accent)}
.daily-note-shell{max-width:960px;margin:0 auto;padding:30px 24px 70px}
.note-hero{position:relative;overflow:hidden;border:1px solid var(--line);border-radius:18px;background:linear-gradient(145deg,#fff,#FBF8F3);padding:30px 30px 26px;box-shadow:0 22px 58px rgba(45,41,38,.075)}
.note-hero::before{content:"";position:absolute;left:0;top:0;bottom:0;width:5px;background:linear-gradient(180deg,var(--accent),rgba(13,120,111,.72))}
.note-kicker{font-size:11px;font-weight:900;letter-spacing:.18em;text-transform:uppercase;color:var(--accent);margin-bottom:12px}
.note-hero h1{font-family:"Noto Serif SC","Noto Serif",serif;font-size:34px;line-height:1.24;max-width:760px;letter-spacing:0}
.note-meta{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px}
.note-seal{display:inline-flex;align-items:center;border:1px solid rgba(217,119,6,.22);border-radius:999px;background:rgba(217,119,6,.08);padding:3px 10px;font-size:12px;font-weight:800;color:var(--accent)}
.note-thesis{margin-top:18px;font-family:"Noto Serif SC","Noto Serif",serif;font-size:20px;line-height:1.65;color:var(--text);max-width:820px}
.note-grid{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:18px;margin-top:22px;align-items:start}
.note-main{display:grid;gap:16px}
.note-panel,.note-market-aside{border:1px solid var(--line);border-radius:16px;background:rgba(255,255,255,.82);box-shadow:0 14px 34px rgba(45,41,38,.045)}
.note-panel{padding:22px}
.note-panel h2,.note-market-aside h2{font-family:"Noto Serif SC","Noto Serif",serif;font-size:21px;line-height:1.3;margin-bottom:12px}
.note-panel p{color:var(--muted);margin-top:8px}
.note-market-aside{padding:16px;position:sticky;top:70px}
.note-market-aside ul{display:grid;gap:9px;list-style:none}
.note-market-aside li{border-top:1px solid var(--line2);padding-top:9px;font-size:13px;color:var(--muted)}
.note-market-aside li:first-child{border-top:0;padding-top:0}
.note-cognition-card{position:relative;overflow:hidden;background:linear-gradient(180deg,#fff,#FCFAF7);border:1px solid rgba(229,226,222,.96);border-radius:17px;padding:24px;box-shadow:0 18px 45px rgba(45,41,38,.055)}
.note-cognition-card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:5px;background:var(--blue)}
.note-label{font-size:11px;font-weight:900;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);margin-bottom:7px}
.note-principle{font-family:"Noto Serif SC","Noto Serif",serif;font-size:24px;line-height:1.42;font-weight:800;margin-bottom:15px}
.note-evidence{background:rgba(245,242,238,.76);border:1px solid rgba(229,226,222,.9);border-radius:12px;padding:13px 14px;color:var(--muted);line-height:1.75}
.note-action{margin-top:12px;background:rgba(217,119,6,.07);border:1px solid rgba(217,119,6,.2);border-radius:12px;padding:12px 14px;color:var(--text)}
.note-system-voice{border-left:4px solid var(--accent);background:linear-gradient(145deg,rgba(217,119,6,.07),#fff)}
.note-watch-list{counter-reset:watch;display:grid;gap:10px;list-style:none}
.note-watch-list li{counter-increment:watch;position:relative;border:1px solid var(--line);border-radius:12px;background:var(--paper2);padding:12px 13px 12px 42px;color:var(--muted)}
.note-watch-list li::before{content:counter(watch);position:absolute;left:13px;top:12px;width:20px;height:20px;border-radius:8px;background:rgba(217,119,6,.12);color:var(--accent);display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:900}
.note-disclaimer{font-size:12px;color:var(--faint);border-top:1px solid var(--line);margin-top:22px;padding-top:18px}
.note-footer{padding:22px;text-align:center;color:var(--faint);font-size:12px}
.daily-archive-list{display:grid;gap:10px;margin-top:20px}
.daily-archive-card{display:block;border:1px solid var(--line);border-radius:14px;background:#fff;padding:16px;color:var(--text);box-shadow:0 10px 26px rgba(45,41,38,.04)}
.daily-archive-card:hover{border-color:rgba(217,119,6,.42);box-shadow:0 16px 34px rgba(45,41,38,.08)}
.daily-archive-card time{display:block;font-size:12px;font-weight:900;color:var(--accent);margin-bottom:5px}
.daily-archive-card strong{font-family:"Noto Serif SC","Noto Serif",serif;font-size:20px}
.daily-archive-card span{display:block;margin-top:7px;color:var(--muted);font-size:13px}
@media(max-width:760px){.note-topbar{padding:11px 16px;flex-wrap:wrap}.daily-note-shell{padding:18px 16px 54px}.note-hero{padding:24px 20px}.note-hero h1{font-size:28px}.note-thesis{font-size:18px}.note-grid{grid-template-columns:1fr}.note-market-aside{position:static}.note-panel,.note-cognition-card{padding:18px}.note-principle{font-size:21px}}
@media(max-width:420px){.note-hero h1{font-size:25px}.note-thesis{font-size:17px}.note-seal{white-space:normal}.note-watch-list li{padding-left:38px}}
"""


HOME_CSS = """.daily-notes-showcase{background:linear-gradient(180deg,rgba(255,255,255,.62),rgba(247,245,243,.9))}
.daily-notes-shell{position:relative;overflow:hidden;border:1px solid var(--line);border-radius:22px;background:rgba(255,255,255,.82);padding:18px;box-shadow:0 20px 48px rgba(45,41,38,.06)}
.daily-notes-shell::before{content:"";position:absolute;inset:0 0 auto;height:4px;background:linear-gradient(90deg,rgba(217,119,6,.55),rgba(217,119,6,0))}
.daily-notes-feature{display:grid;grid-template-columns:minmax(0,1.08fr) minmax(280px,.72fr);gap:14px;align-items:stretch}
.daily-note-latest,.daily-note-mini{position:relative;overflow:hidden;transition:border-color .16s ease,box-shadow .16s ease,transform .16s ease}
.daily-note-latest{display:flex;flex-direction:column;border:1px solid rgba(217,119,6,.2);border-radius:18px;background:linear-gradient(145deg,#fff,#FBF8F3);padding:22px;color:var(--text);min-height:260px;box-shadow:0 16px 34px rgba(45,41,38,.045)}
.daily-note-latest::before,.daily-note-mini::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:linear-gradient(180deg,rgba(217,119,6,.52),rgba(217,119,6,.08))}
.daily-note-latest:hover,.daily-note-mini:hover{border-color:rgba(217,119,6,.46);box-shadow:0 18px 38px rgba(45,41,38,.08);color:var(--text);transform:translateY(-1px)}
.daily-note-latest time,.daily-note-mini time{font-size:11px;font-weight:900;letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}
.daily-note-latest strong{font-family:"Noto Serif SC",serif;font-size:27px;line-height:1.3;margin:16px 0 12px}
.daily-note-latest span{font-size:14px;color:var(--muted);line-height:1.7}
.daily-note-latest em{margin-top:auto;font-style:normal;font-size:11px;font-weight:900;color:var(--accent);background:rgba(217,119,6,.08);border:1px solid rgba(217,119,6,.16);border-radius:999px;padding:3px 10px;align-self:flex-start}
.daily-note-mini-grid{display:grid;grid-template-columns:1fr;gap:12px}
.daily-note-mini{display:flex;flex-direction:column;gap:10px;border:1px solid rgba(217,119,6,.16);border-radius:18px;background:linear-gradient(145deg,#fff,#FDF9F3);padding:20px 20px 18px 22px;color:var(--text);min-height:260px;box-shadow:0 14px 32px rgba(45,41,38,.045)}
.daily-note-mini strong{font-family:"Noto Serif SC",serif;font-size:21px;line-height:1.35}.daily-note-mini-summary{font-size:13px;color:var(--muted);line-height:1.65}.daily-note-mini-tag{margin-top:auto;font-style:normal;font-size:11px;font-weight:900;color:var(--accent);background:rgba(217,119,6,.08);border:1px solid rgba(217,119,6,.16);border-radius:999px;padding:3px 10px;align-self:flex-start}
@media(max-width:940px){.daily-notes-feature{grid-template-columns:1fr}.daily-note-mini{min-height:220px}}
@media(max-width:720px){.daily-notes-shell{padding:14px;border-radius:20px}.daily-note-latest,.daily-note-mini{min-height:220px}.daily-note-latest strong{font-size:23px}.daily-note-mini strong{font-size:21px}}
"""


def sanitize_public_text(text: str) -> str:
    """Remove execution details unsuitable for public Daily Notes."""
    cleaned_lines: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.search(r"TICKET-|成本价|@\s*\d|已买|已卖|\d+\s*股", line, re.I):
            continue
        if re.search(r"(明日买入|买入|加仓|减仓|清仓|卖出).*(\d+\s*股|突破|@\s*\d)", line, re.I):
            continue
        line = re.sub(r"TICKET-[A-Za-z0-9_-]+", "交易记录", line)
        line = re.sub(r"\d+\s*股", "若干仓位", line)
        line = re.sub(r"成本价\s*[0-9.]+", "成本信息", line)
        line = re.sub(r"跌破\s*(?:\d+(?:m|分钟)\s*)?MA\d+\s*[0-9.]+", "跌破短周期保护位", line, flags=re.I)
        line = re.sub(r"MA\d+\s*[0-9.]+", "短周期保护位", line, flags=re.I)
        line = re.sub(r"(收回|突破|跌破|站回|守住|守|回踩|防守|止损线|修复线)\s*[0-9]+(?:\.[0-9]+)?", r"\1关键确认位", line)
        line = re.sub(r"[0-9]+(?:\.[0-9]+)?\s*成本线", "关键确认位", line)
        line = re.sub(r"成本线", "关键确认位", line)
        line = re.sub(r"成本下(?:方)?", "关键位下方", line)
        line = re.sub(r"候选补入[^；。]+", "候选清单保留在内部复盘", line)
        line = re.sub(r"站上\s*[0-9.]+", "站上关键确认位", line)
        line = re.sub(r"低开超过\s*[0-9]+(?:\.[0-9]+)?%", "低开明显", line)
        line = re.sub(r"[0-9]+(?:\.[0-9]+)?\s*以上", "关键位以上", line)
        line = re.sub(r"\d+(?:\.\d+)?\s*%", "关键比例", line)
        line = re.sub(r"(?<![\d.-])\d{1,4}\.\d+(?!\s*%)", "关键位置", line)
        line = re.sub(r"明日买入", "明日观察", line)
        line = re.sub(r"新买入|买入", "开仓", line)
        line = re.sub(r"加仓", "提高暴露", line)
        line = re.sub(r"减仓|清仓|卖出", "降低风险", line)
        line = re.sub(r"(?:再)?减\s*[0-9]+(?:\s*[-~—]\s*[0-9]+)?", "降低部分风险", line)
        line = re.sub(r"降低风险\s*[0-9]+(?:\s*[-~—]\s*[0-9]+)?", "降低部分风险", line)
        line = re.sub(r"\d{1,2}:\d{2}", "盘中", line)
        line = re.sub(
            r"(海光信息|海光|中信证券|中信|药明康德|药明|海兰信|南大光电|南大|雅克科技|雅克|澜起科技|中微公司|聚和材料|聚和|太极实业|太极|徐工机械|徐工|华工科技|华工|江丰电子|江丰|金宏气体|金宏|长电科技|长电|兆易创新|兆易|方正科技|方正|通富微电|新易盛|中际旭创|天孚通信|中国卫星|上海瀚讯|盛路通信)",
            "标的",
            line,
        )
        line = re.sub(r"(?:标的\s*/\s*)+标的", "持仓标的", line)
        line = re.sub(r"标的和标的", "持仓标的", line)
        line = re.sub(r"组合仓位", "组合风险暴露", line)
        line = re.sub(r"标的补仓", "持仓动作", line)
        line = re.sub(r"(标的提高暴露、)+标的提高暴露", "标的提高暴露", line)
        line = re.sub(r"\s+关键位置", "关键位置", line)
        line = re.sub(r"\s+关键比例", "关键比例", line)
        line = re.sub(r"\s+", " ", line).strip(" -")
        if line:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def strip_source_guidance(text: str) -> str:
    """Drop ReviewNote operator guidance that should not become public copy."""
    kept: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if "Portal 今日一句话来源" in line:
            continue
        if "一句话讲清当日市场状态和系统判断" in line:
            continue
        if "不写 ticket" in line or "精确买卖指令" in line:
            continue
        kept.append(raw)
    return "\n".join(kept).strip()


def first_sentence(text: str, fallback: str) -> str:
    text = strip_source_guidance(text)
    text = sanitize_public_text(convert_review.strip_html_tags(text) if "<" in text else text)
    text = re.sub(r"^[>\-\d.、\s]+", "", text).strip()
    text = re.sub(r"^\*{1,2}(.*?)\*{1,2}$", r"\1", text, flags=re.S).strip()
    if not text:
        return fallback
    parts = re.split(r"[。！？]\s*", text, maxsplit=1)
    return parts[0].strip() + "。"


def clean_cognition_title(title: str) -> str:
    return re.sub(
        r"^\[(?:认知|教训|议题|流程纪律|账户纪律|风险信号)\]\s*",
        "",
        title or "",
    ).strip(" 。；;")


def extract_date(md_path: Path, fm: dict) -> str:
    date = fm.get("date", "")
    if date:
        return date
    m = re.match(r"(\d{4})_(\d{1,2})_(\d{1,2})", md_path.name)
    if not m:
        raise ValueError(f"Cannot infer date from {md_path}")
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def extract_one_line(s1_text: str, fm: dict) -> str:
    blocks = convert_review.find_h3_blocks(s1_text)
    for heading, body in blocks:
        if "一句话结论" in heading:
            return first_sentence(body, "")
    status = fm.get("市场状态") or convert_review.desc_from_fm(fm) or "市场进入需要降速观察的一天"
    return f"{status}里，先确认系统约束，再处理主观判断。"


def extract_first_cognition(s2_text: str) -> tuple[str, str, str]:
    bracket_bold_title = re.search(
        r"^\d+\.\s+\[(?P<kind>认知)\]\s*\*\*(?P<title>.+?)\*\*\s*[—-]\s*(?P<body>.*?)(?=\n\d+\.\s+\[|\Z)",
        s2_text,
        re.M | re.S,
    )
    if bracket_bold_title:
        title = clean_cognition_title(bracket_bold_title.group("title"))
        body = sanitize_public_text(bracket_bold_title.group("body").strip())
        return title, body, convert_review.infer_lesson_action("认知", title, body)

    bracket_tagged = re.search(
        r"^\d+\.\s+\[(?P<kind>认知)\]\s*(?P<title>.+?)(?:[。；;]|$)(?P<body>.*?)(?=\n\d+\.\s+\[|\Z)",
        s2_text,
        re.M | re.S,
    )
    if bracket_tagged:
        title = clean_cognition_title(bracket_tagged.group("title"))
        body = sanitize_public_text((bracket_tagged.group("body") or "").strip())
        if not body:
            body = title
        return title, body, convert_review.infer_lesson_action("认知", title, body)

    tagged = re.search(
        r"^\d+\.\s+\*\*\[(?P<kind>认知)\]\s*(?P<title>.+?)\*\*\s*[—-]\s*(?P<body>.*?)(?=\n\d+\.\s+\*\*\[|\Z)",
        s2_text,
        re.M | re.S,
    )
    if tagged:
        title = clean_cognition_title(tagged.group("title"))
        body = sanitize_public_text(tagged.group("body").strip())
        return title, body, convert_review.infer_lesson_action("认知", title, body)

    tagged_bold_inline = re.search(
        r"^\d+\.\s+\*\*\[(?P<kind>认知)\]\s*(?P<title>.+?)\*\*\s*(?P<body>.*?)(?=^\d+\.\s+\*\*|^###|\Z)",
        s2_text,
        re.M | re.S,
    )
    if tagged_bold_inline:
        title = clean_cognition_title(tagged_bold_inline.group("title"))
        body = sanitize_public_text(tagged_bold_inline.group("body").strip())
        if not body:
            body = title
        return title, body, convert_review.infer_lesson_action("认知", title, body)

    numbered_bold = re.search(
        r"^\d+\.\s+\*\*(?P<title>.+?)\*\*\s*(?P<body>.*?)(?=^\d+\.\s+\*\*|^###|\Z)",
        s2_text,
        re.M | re.S,
    )
    if numbered_bold:
        title = clean_cognition_title(numbered_bold.group("title"))
        body = sanitize_public_text(numbered_bold.group("body").strip())
        if not body:
            body = title
        return title, body, convert_review.infer_lesson_action("认知", title, body)

    numbered_inline = re.search(
        r"^\d+\.\s+\*\*(?P<title>.+?)\*\*\s*[：:]\s*(?P<body>.*?)(?=^\d+\.\s+\*\*|^###|\Z)",
        s2_text,
        re.M | re.S,
    )
    if numbered_inline:
        title = clean_cognition_title(numbered_inline.group("title"))
        body = sanitize_public_text(numbered_inline.group("body").strip())
        return title, body, convert_review.infer_lesson_action("认知", title, body)

    plain_numbered = re.search(
        r"^\d+\.\s+(?P<title>[^：:\n]+)[：:]\s*(?P<body>.*?)(?=^\d+\.\s+|^###|\Z)",
        s2_text,
        re.M | re.S,
    )
    if plain_numbered:
        title = clean_cognition_title(plain_numbered.group("title"))
        body = sanitize_public_text(plain_numbered.group("body").strip())
        return title, body or title, convert_review.infer_lesson_action("认知", title, body)

    untagged = re.search(
        r"(?:^###\s+今日认知\s*)?\*\*\d+\.\s+(?P<title>.+?)\*\*\s*\n+(?P<body>.*?)(?=^(?:\*\*\d+\.|###)|\Z)",
        s2_text,
        re.M | re.S,
    )
    if untagged:
        title = clean_cognition_title(untagged.group("title"))
        body = sanitize_public_text(untagged.group("body").strip())
        return title, body, convert_review.infer_lesson_action("认知", title, body)

    return (
        "先把当天经验压成可复用原则",
        "今天的复盘还没有抽出单条公开认知，发布前应由人工补一句真实判断。",
        "发布前先把这条经验转成明天可检查的一句话。",
    )


def extract_watch_items(s3_text: str) -> list[str]:
    items: list[str] = []
    capture = False
    for raw in s3_text.splitlines():
        line = raw.strip()
        if re.match(r"^###\s+.*(观察|关注)", line):
            capture = True
            continue
        if capture and line.startswith("### "):
            break
        if not capture and not re.match(r"^\d+[.、]\s+", line):
            continue
        if re.match(r"^\d+[.、]\s+", line):
            item = re.sub(r"^\d+[.、]\s+", "", line).strip()
            safe = sanitize_public_text(item)
            if safe:
                items.append(safe)
        if len(items) >= 3:
            break
    if not items:
        tone = re.search(r"\*\*总基调\*\*[：:]\s*(.+)", s3_text)
        if tone:
            items.append(first_sentence(tone.group(1), "先看市场承接是否恢复。"))
    return items[:3] or ["先看市场承接是否恢复，再决定是否提高进攻性。"]


def public_position_summary(position: str) -> str:
    if not position or "空仓" in position:
        return "持仓状态以空仓或低暴露方式呈现。"
    return "持仓状态以公开摘要呈现，不展开标的、数量和成本。"


def build_daily_note(md_path: str | Path, user_feeling: str = "") -> DailyNote:
    md_path = Path(md_path)
    content = md_path.read_text(encoding="utf-8")
    fm = convert_review.parse_frontmatter(content)
    date = extract_date(md_path, fm)
    weekday = fm.get("weekday", "")
    s1_text, _ = convert_review.extract_section(content, "一、当日复盘")
    s2_text, _ = convert_review.extract_section(content, "二、心得与教训")
    s3_text, _ = convert_review.extract_section(content, "三、次日预案")

    one_line = extract_one_line(s1_text, fm)
    cog_title, cog_body, cog_action = extract_first_cognition(s2_text)
    market_status = fm.get("市场状态") or convert_review.desc_from_fm(fm) or "观察"
    summary = one_line
    title = cog_title if cog_title else market_status
    tag = "系统门禁" if re.search(r"系统|门禁|规则", f"{title} {cog_body}") else "市场手记"

    market_facts = [
        f"市场状态：{sanitize_public_text(market_status)}。",
        f"情绪值：{convert_review.pct_text(fm.get('情绪值', '--'))}。",
        f"上证涨幅：{convert_review.pct_text(fm.get('上证涨幅', '--'), signed=True)}。",
        f"涨跌停：{fm.get('涨停家数', '--')} / {fm.get('跌停家数', '--')}。",
        public_position_summary(fm.get("盘后持仓", "")),
    ]

    feeling = sanitize_public_text(user_feeling)
    if feeling:
        system_voice = f"{feeling} 系统的价值不是给出更激进的解释，而是把交易动作压回到门禁、风险和复盘证据上。"
    else:
        system_voice = "系统今天的作用，是把主观解释压回到市场状态、风险门禁和复盘证据上，帮助人少做情绪化动作。"

    return DailyNote(
        date=date,
        weekday=weekday,
        title=sanitize_public_text(title),
        summary=sanitize_public_text(summary),
        market_status=sanitize_public_text(market_status),
        market_facts=market_facts,
        cognition_title=sanitize_public_text(cog_title),
        cognition_evidence=sanitize_public_text(cog_body),
        cognition_action=sanitize_public_text(cog_action),
        system_voice=system_voice,
        watch_items=extract_watch_items(s3_text),
        tag=sanitize_public_text(tag),
    )


def esc(value: str) -> str:
    return html_escape(value or "", quote=False)


def rich_text(value: str) -> str:
    text = esc(value)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return text


def render_list(items: list[str]) -> str:
    return "\n".join(f"<li>{rich_text(item)}</li>" for item in items if item)


def render_daily_note_page(note: DailyNote) -> str:
    date_label = note.date
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(note.date)} 每日市场手记 · 弈沐资本</title>
<style>
{NOTE_CSS}
</style>
</head>
<body>
<div class="note-topbar">
  <a id="back-home" href="../index.html#daily-notes">返回首页</a>
  <a href="index.html">全部手记</a>
  <strong>每日市场手记</strong>
</div>
<main class="daily-note-shell">
  <section class="note-hero">
    <div class="note-kicker">Daily Market Note</div>
    <h1>{esc(note.title)}</h1>
    <div class="note-meta">
      <span class="note-seal">{esc(date_label)} {esc(note.weekday)}</span>
      <span class="note-seal">{esc(note.market_status)}</span>
      <span class="note-seal">{esc(note.tag)}</span>
    </div>
    <p class="note-thesis"><strong>今日一句话：</strong>{rich_text(note.summary)}</p>
  </section>

  <div class="note-grid">
    <article class="note-main">
      <section class="note-cognition-card">
        <div class="note-label">今日一个认知</div>
        <div class="note-principle">{esc(note.cognition_title)}</div>
        <div class="note-label">当日证据</div>
        <div class="note-evidence">{rich_text(note.cognition_evidence)}</div>
        <div class="note-label">下次动作</div>
        <div class="note-action">{rich_text(note.cognition_action)}</div>
      </section>

      <section class="note-panel note-system-voice">
        <h2>系统今天做了什么</h2>
        <p>{rich_text(note.system_voice)}</p>
      </section>

      <section class="note-panel">
        <h2>明日只看什么</h2>
        <ol class="note-watch-list">
          {render_list(note.watch_items)}
        </ol>
      </section>

      <section class="note-panel">
        <h2>边界声明</h2>
        <p>{DISCLAIMER}</p>
      </section>
    </article>

    <aside class="note-market-aside">
      <h2>今日市场状态</h2>
      <ul>
        {render_list(note.market_facts)}
      </ul>
    </aside>
  </div>
  <div class="note-disclaimer">{DISCLAIMER}</div>
</main>
<footer class="note-footer">弈沐资本 · YiMu Capital · Daily Notes</footer>
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


def read_existing_notes() -> list[dict]:
    notes = []
    if not DAILY_NOTES.exists():
        return notes
    for path in DAILY_NOTES.glob("20*.html"):
        html = path.read_text(encoding="utf-8")
        title_match = re.search(r"<h1>(.*?)</h1>", html, re.S)
        summary_match = re.search(r'<p class="note-thesis"><strong>今日一句话：</strong>(.*?)</p>', html, re.S)
        tag_match = re.findall(r'<span class="note-seal">(.*?)</span>', html, re.S)
        notes.append(
            {
                "date": path.stem,
                "title": convert_review.strip_html_tags(title_match.group(1)) if title_match else path.stem,
                "summary": convert_review.strip_html_tags(summary_match.group(1)) if summary_match else "",
                "tag": convert_review.strip_html_tags(tag_match[-1]) if tag_match else "市场手记",
            }
        )
    return notes


def note_card_html(note: dict, prefix: str = "") -> str:
    href = f'{prefix}{note["date"]}.html'
    return (
        f'<a class="daily-archive-card" href="{href}">'
        f'<time>{esc(note["date"])}</time>'
        f'<strong>{esc(note["title"])}</strong>'
        f'<span>{esc(note.get("summary", ""))}</span>'
        "</a>"
    )


def update_daily_notes_index(note: DailyNote) -> None:
    DAILY_NOTES.mkdir(parents=True, exist_ok=True)
    notes_by_date = {n["date"]: n for n in read_existing_notes()}
    notes_by_date[note.date] = {
        "date": note.date,
        "title": note.title,
        "summary": note.summary,
        "tag": note.tag,
    }
    notes = sorted(notes_by_date.values(), key=lambda n: n["date"], reverse=True)
    cards = "\n".join(note_card_html(n) for n in notes)
    latest = notes[0] if notes else {"date": "--", "title": "每日市场手记", "summary": ""}
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日市场手记 · 弈沐资本</title>
<style>
{NOTE_CSS}
</style>
</head>
<body>
<div class="note-topbar">
  <a href="../index.html#daily-notes">返回首页</a>
  <strong>每日市场手记</strong>
</div>
<main class="daily-note-shell">
  <section class="note-hero">
    <div class="note-kicker">Daily Notes Archive</div>
    <h1>每日市场手记</h1>
    <div class="note-meta">
      <span class="note-seal">共 {len(notes)} 篇</span>
      <span class="note-seal">最新 {esc(latest["date"])}</span>
    </div>
    <p class="note-thesis">把每天的市场状态、系统约束和真实交易感受，压缩成可公开阅读的短手记。</p>
  </section>
  <section class="daily-archive-list">
    {cards}
  </section>
</main>
<footer class="note-footer">弈沐资本 · YiMu Capital · Daily Notes</footer>
</body>
</html>"""
    (DAILY_NOTES / "index.html").write_text(html, encoding="utf-8")


def inject_home_css(content: str) -> str:
    if "/* DAILY_NOTES_CSS_START */" in content:
        return re.sub(
            r"/\* DAILY_NOTES_CSS_START \*/.*?/\* DAILY_NOTES_CSS_END \*/",
            f"/* DAILY_NOTES_CSS_START */\n{HOME_CSS}\n/* DAILY_NOTES_CSS_END */",
            content,
            flags=re.S,
        )
    return content.replace("</style>", f"/* DAILY_NOTES_CSS_START */\n{HOME_CSS}\n/* DAILY_NOTES_CSS_END */\n</style>", 1)


def home_section_html(notes: list[dict]) -> str:
    latest = notes[0]
    mini_cards = "\n".join(
        f'''          <a class="daily-note-mini daily-note-secondary" href="daily-notes/{esc(n["date"])}.html?from=daily-notes">
            <time>{esc(n["date"])}</time>
            <strong>{esc(n["title"])}</strong>
            <span class="daily-note-mini-summary">{esc(n.get("summary", ""))}</span>
            <em class="daily-note-mini-tag">{esc(n.get("tag", "市场手记"))}</em>
          </a>'''
        for n in notes[1:5]
    )
    if not mini_cards:
        mini_cards = f'''          <a class="daily-note-mini daily-note-secondary" href="daily-notes/index.html">
            <time>Archive</time>
            <strong>全部市场手记</strong>
            <span class="daily-note-mini-summary">按日期查看公开摘要层</span>
            <em class="daily-note-mini-tag">归档</em>
          </a>'''
    return f"""<!-- DAILY_NOTES_SECTION_START -->
  <section class="section daily-notes-showcase" id="daily-notes">
    <div class="wrap">
      <div class="section-head">
        <div><div class="eyebrow">Daily Notes</div><h2>每日市场手记</h2></div>
        <a class="research-detail-link" href="daily-notes/index.html">进入手记归档 →</a>
      </div>
      <div class="daily-notes-shell">
        <div class="daily-notes-feature">
          <a class="daily-note-latest" href="daily-notes/{esc(latest["date"])}.html?from=daily-notes">
            <time>{esc(latest["date"])}</time>
            <strong>{esc(latest["title"])}</strong>
            <span>{esc(latest.get("summary", ""))}</span>
            <em>{esc(latest.get("tag", "市场手记"))}</em>
          </a>
          <div class="daily-note-mini-grid">
{mini_cards}
          </div>
        </div>
      </div>
    </div>
  </section>
<!-- DAILY_NOTES_SECTION_END -->"""


def insert_home_section(content: str, section: str) -> str:
    if "<!-- DAILY_NOTES_SECTION_START -->" in content:
        return re.sub(
            r"<!-- DAILY_NOTES_SECTION_START -->.*?<!-- DAILY_NOTES_SECTION_END -->",
            section,
            content,
            flags=re.S,
        )
    reviews = re.search(r'<section class="section" id="reviews">.*?</section>', content, re.S)
    if reviews:
        return content[: reviews.end()] + "\n\n" + section + content[reviews.end() :]
    return content.replace("</main>", section + "\n</main>", 1)


def update_home_daily_notes(note: DailyNote) -> None:
    idx_path = PORTAL / "index.html"
    if not idx_path.exists():
        return
    content = idx_path.read_text(encoding="utf-8")
    notes_by_date = {n["date"]: n for n in read_existing_notes()}
    notes_by_date[note.date] = {
        "date": note.date,
        "title": note.title,
        "summary": note.summary,
        "tag": note.tag,
    }
    notes = sorted(notes_by_date.values(), key=lambda n: n["date"], reverse=True)
    content = inject_home_css(content)
    content = insert_home_section(content, home_section_html(notes))
    workspace_link = (
        '<a class="workspace-card" id="workspace-daily-notes" href="daily-notes/index.html">'
        "<strong>每日市场手记</strong><span>公开摘要与交易感受</span></a>"
    )
    if "workspace-daily-notes" not in content:
        content = content.replace('<div class="workspace-grid">', '<div class="workspace-grid">\n        ' + workspace_link, 1)
    idx_path.write_text(content, encoding="utf-8")


def write_daily_note_page(note: DailyNote) -> Path:
    DAILY_NOTES.mkdir(parents=True, exist_ok=True)
    path = DAILY_NOTES / f"{note.date}.html"
    path.write_text(render_daily_note_page(note), encoding="utf-8")
    return path


def convert_review_to_daily_note(md_path: str | Path, user_feeling: str = "") -> dict:
    note = build_daily_note(md_path, user_feeling=user_feeling)
    write_daily_note_page(note)
    update_daily_notes_index(note)
    update_home_daily_notes(note)
    print(f"✅ 已生成 Daily Note: {DAILY_NOTES / (note.date + '.html')}")
    return note.as_dict()


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 tools/convert_daily_note.py <ReviewNote.md> [user feeling]")
        sys.exit(1)
    md_path = sys.argv[1]
    feeling = " ".join(sys.argv[2:]).strip()
    convert_review_to_daily_note(md_path, user_feeling=feeling)


if __name__ == "__main__":
    main()
