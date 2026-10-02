#!/usr/bin/env python3
"""Build the portal's writing index from Vault ``公开写作/`` frontmatter (W8 S1).

门户只读 ``data/writing-index.json`` 和它指向的文件，不遍历 Vault（开工单 W8 第二节第 2 点）。
只收 ``status: published``；frontmatter 缺字段的进 ``issues``，不发布，也不猜。

这是铁律 1 的例外入口：写作原文原样发布，不抽字段、不删敏。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

INDEX_SCHEMA = "writing_index.v1"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "data" / "writing-index.json"

VALID_STATUS = ("draft", "published")
REQUIRED_BY_KIND = {
    "daily": ("date",),
    "essay": ("title",),
    "weekly": ("week",),
}


def _frontmatter(text: str) -> dict[str, str]:
    """Parse the leading ``---`` block into a flat string mapping."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1] in " \t":
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _kind(frontmatter: dict[str, str]) -> str:
    declared = frontmatter.get("kind")
    if declared:
        return declared
    # 文章目录里的文件没有 kind，靠 type=essay 区分；其余按目录名。
    return "essay" if frontmatter.get("type") == "essay" else "daily"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _entry(rel: str, path: Path, frontmatter: dict[str, str]) -> dict[str, Any]:
    kind = _kind(frontmatter)
    return {
        "path": rel,
        "kind": kind,
        "date": frontmatter.get("date") or frontmatter.get("created", ""),
        "title": frontmatter.get("title", ""),
        "series": frontmatter.get("series", ""),
        "status": frontmatter.get("status", ""),
        "published_at": frontmatter.get("published_at", ""),
        "week": frontmatter.get("week", ""),
        "sha256": _sha256(path),
    }


def build_index(root: Path, *, generated_at: str = "") -> dict[str, Any]:
    """Scan ``root`` (Vault ``公开写作/``) and return the index payload."""
    base = Path(root)
    entries: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for path in sorted(base.rglob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        rel = path.relative_to(base).as_posix()
        frontmatter = _frontmatter(path.read_text(encoding="utf-8"))
        if not frontmatter:
            continue
        status = frontmatter.get("status", "")
        if status == "draft":
            continue
        if status not in VALID_STATUS:
            issues.append({
                "path": rel,
                "reason": "status_unknown",
                "missing": [f"status={status or '(缺失)'}"],
            })
            continue
        entry = _entry(rel, path, frontmatter)
        missing = [field for field in REQUIRED_BY_KIND.get(entry["kind"], ()) if not entry.get(field)]
        if status == "published" and not entry["published_at"]:
            missing.append("published_at")
        if missing:
            issues.append({"path": rel, "reason": "required_field_missing", "missing": missing})
            continue
        if status != "published":
            continue
        entries.append(entry)
    # ``generated_at`` stays empty and ``source_root`` is deliberately absent:
    # the index is a committed artifact, so it must be byte-identical on every
    # machine for ``--check`` to mean anything, and it must not carry a local
    # absolute path into git.
    payload = {
        "schema": INDEX_SCHEMA,
        "entries": sorted(entries, key=lambda item: item["path"]),
        "issues": sorted(issues, key=lambda item: item["path"]),
    }
    if generated_at:
        payload["generated_at"] = generated_at
    return payload


def render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="公开写作索引（W8）")
    parser.add_argument("--root", required=True, help="Vault 公开写作/ 目录")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="输出 JSON（默认 data/writing-index.json）")
    parser.add_argument("--check", action="store_true", help="只比对，不写盘；有差异退出码 1")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_index(Path(args.root).expanduser())
    rendered = render(payload)
    out = Path(args.out)
    if args.check:
        if not out.is_file():
            print(f"writing_index_missing:{out}", file=sys.stderr)
            return 1
        if out.read_text(encoding="utf-8") != rendered:
            print(f"writing_index_stale:{out}（重新生成后再提交）", file=sys.stderr)
            return 1
        print(f"writing index up to date: {len(payload['entries'])} 条，{len(payload['issues'])} 个 issues")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(rendered, encoding="utf-8")
    print(f"writing index: {len(payload['entries'])} 条已发布，{len(payload['issues'])} 个 issues → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())