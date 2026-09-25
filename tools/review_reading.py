"""Adapter for explicit review_reading.v1 sidecars and transition frontmatter.

The canonical input is a date-scoped JSON sidecar bound to the current source
ReviewNote revision. An inline frontmatter projection remains a compatibility
path while producers migrate; unmarked historical notes are unchanged.
"""

from __future__ import annotations

import json
import hashlib
import math
import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any


SCHEMA = "review_reading.v1"
POSITION_UNKNOWN = "__review_reading_position_unknown__"
STATUS_VALUES = frozenset({
    "available", "missing", "explicit_empty", "conflict", "quality_unknown", "malformed",
})
NON_VALUE_STATUSES = frozenset({
    "missing", "conflict", "quality_unknown", "malformed",
})
MARKET_STATE_VALUES = frozenset({"冰点", "低迷", "主升", "强势", "高潮", "退潮"})
PROFIT_EFFECT_VALUES = frozenset({"好", "一般", "差"})
PROFIT_EFFECT_MISSING_VALUES = frozenset({"", "N", "n", "-", "未知", "未提供"})
INDEPENDENT_SOURCE_FIELDS = frozenset({
    "market.profit_effect",
    "market.emotion",
    "market.sh_index_pct",
    "market.limit_up_count",
    "market.limit_down_count",
    "account.post_close_positions",
})
SOURCE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

SIDECAR_ROOT_KEYS = frozenset({
    "schema", "source_id", "source_revision", "market", "account", "sections",
})
SECTION_FIELDS = (
    ("today_happened", "1. 今天发生了什么"),
    ("judgment_and_actions", "2. 我的判断和动作"),
    ("looking_back", "3. 回头看"),
    ("next_step", "4. 下一步"),
)

FIELD_MAP = (
    ("market", "market_state", "市场状态"),
    ("market", "profit_effect", "赚钱效应"),
    ("market", "emotion", "情绪值"),
    ("market", "sh_index_pct", "上证涨幅"),
    ("market", "limit_up_count", "涨停家数"),
    ("market", "limit_down_count", "跌停家数"),
    ("account", "post_close_positions", "盘后持仓"),
)


class UnsupportedReviewReading(ValueError):
    """The opt-in projection is malformed or declares an unknown schema."""


def _valid_source_ref(ref: Any) -> bool:
    if not isinstance(ref, Mapping):
        return False
    if not {"source_id", "revision", "locator"}.issubset(ref):
        return False
    if not set(ref).issubset({"source_id", "revision", "locator", "line"}):
        return False
    source_id = ref.get("source_id")
    if not isinstance(source_id, str) or not SOURCE_ID_RE.fullmatch(source_id):
        return False
    revision = ref.get("revision")
    if not isinstance(revision, str) or not SHA256_RE.fullmatch(revision):
        return False
    locator = ref.get("locator")
    if not isinstance(locator, str) or not locator.strip() or len(locator) > 180:
        return False
    line = ref.get("line")
    return line is None or (isinstance(line, int) and not isinstance(line, bool) and line > 0)


def read_sidecar(
    path: str | Path,
    *,
    source_path: str | Path,
    source_date: str,
) -> dict[str, Any]:
    """Read a date-bound sidecar and bind it to the exact current ReviewNote bytes."""
    candidate = Path(path)
    if not candidate.is_absolute():
        raise UnsupportedReviewReading("review_reading_sidecar_path_must_be_absolute")
    try:
        sidecar_path = candidate.resolve(strict=True)
        source_bytes = Path(source_path).read_bytes()
    except OSError as exc:
        raise UnsupportedReviewReading("review_reading_sidecar_or_source_missing") from exc
    if not sidecar_path.is_file():
        raise UnsupportedReviewReading("review_reading_sidecar_not_file")
    try:
        parsed_date = date.fromisoformat(source_date)
    except (TypeError, ValueError) as exc:
        raise UnsupportedReviewReading("review_reading_source_date_invalid") from exc
    if parsed_date.isoformat() != source_date:
        raise UnsupportedReviewReading("review_reading_source_date_invalid")

    source_revision = hashlib.sha256(source_bytes).hexdigest()
    # Contract §6: a projection file is
    #   <source_revision>[.<generator_version>.<evidence_fingerprint>].<schema>.json
    # The versioned form is authoritative; the bare form is the legacy product.
    versioned = re.fullmatch(
        rf"{re.escape(source_revision)}\.[0-9A-Za-z._-]+\.{re.escape(SCHEMA)}\.json",
        sidecar_path.name,
    )
    legacy = sidecar_path.name == f"{source_revision}.{SCHEMA}.json"
    if not (versioned or legacy):
        raise UnsupportedReviewReading("review_reading_sidecar_path_mismatch")
    expected_suffix = (
        "Market_Watch",
        "artifacts",
        "review-reading",
        str(parsed_date.year),
        source_date,
    )
    if tuple(sidecar_path.parts[-(len(expected_suffix) + 1):-1]) != expected_suffix:
        raise UnsupportedReviewReading("review_reading_sidecar_path_mismatch")
    try:
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UnsupportedReviewReading("invalid_review_reading_sidecar_json") from exc
    if not isinstance(payload, Mapping) or set(payload) != SIDECAR_ROOT_KEYS:
        raise UnsupportedReviewReading("invalid_review_reading_sidecar_shape")
    payload = dict(payload)
    if payload.get("schema") != SCHEMA:
        raise UnsupportedReviewReading(
            f"unsupported_review_reading_schema:{payload.get('schema') or 'missing'}"
        )
    source_id = payload.get("source_id")
    if not isinstance(source_id, str) or not SOURCE_ID_RE.fullmatch(source_id):
        raise UnsupportedReviewReading("review_reading_source_id_invalid")
    revision = payload.get("source_revision")
    if not isinstance(revision, str) or not SHA256_RE.fullmatch(revision):
        raise UnsupportedReviewReading("review_reading_source_revision_invalid")
    if revision != source_revision:
        raise UnsupportedReviewReading("review_reading_source_revision_mismatch")
    market = payload.get("market")
    account = payload.get("account")
    if not isinstance(market, Mapping) or set(market) != {
        "market_state", "profit_effect", "emotion", "sh_index_pct", "limit_up_count", "limit_down_count"
    }:
        raise UnsupportedReviewReading("review_reading_market_fields_invalid")
    if not isinstance(account, Mapping) or set(account) != {"post_close_positions"}:
        raise UnsupportedReviewReading("review_reading_account_fields_invalid")
    if any(
        not isinstance(entry, Mapping)
        for entry in [*market.values(), *account.values()]
    ):
        raise UnsupportedReviewReading("review_reading_field_envelope_invalid")
    sections = payload.get("sections")
    expected_sections = {field for field, _ in SECTION_FIELDS}
    if not isinstance(sections, Mapping) or set(sections) != expected_sections:
        raise UnsupportedReviewReading("review_reading_sections_invalid")
    if any(not isinstance(sections[field], str) for field in expected_sections):
        raise UnsupportedReviewReading("review_reading_section_body_invalid")
    return payload


def projection_notice(path: str | Path, source_revision: str, day: str) -> str:
    """Expose timing uncertainty without leaking private index paths or hashes."""
    import importlib.util
    path = Path(path).resolve()
    index_path = path.parent / '_index.json'
    if not index_path.exists() and not index_path.is_symlink():
        return '历史阅读投影；当时可见时点未核实。'
    try:
        module_path = Path(__file__).resolve().parents[2] / 'Market_Watch/scripts/review_reading_index.py'
        spec = importlib.util.spec_from_file_location('_portal_projection_index', module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        market_root = path.parents[4]
        index = module.load_index(market_root, day)
        record = next(v for v in index['days'][day]['by_source_revision'][source_revision]['versions']
                      if (market_root / v['path']).resolve() == path)
    except Exception as exc:
        raise UnsupportedReviewReading('review_reading_provenance_invalid') from exc
    if record['post_hoc']:
        return '事后修订：本页包含补录或重新核对的内容，不代表交易当时已经可见。'
    if record.get('revision_reason') == 'generator_upgrade':
        return '阅读格式升级；源笔记和事实文件版本未变。'
    return '阅读投影；当时可见时点未核实。' if record.get('event_at') == 'unknown' else '阅读投影已记录事实时点。'


def render_sidecar_sections(sections: Mapping[str, str]) -> str:
    """Adapt stable sidecar section keys to the existing Portal Markdown parser."""
    blocks = []
    for field, heading in SECTION_FIELDS:
        body = sections[field].strip()
        blocks.append(f"## {heading}\n\n{body}" if body else f"## {heading}")
    return "\n\n".join(blocks) + "\n"


def _parse_projection(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise UnsupportedReviewReading("invalid_review_reading_json") from exc
    if not isinstance(raw, Mapping):
        raise UnsupportedReviewReading("invalid_review_reading_object")
    projection = dict(raw)
    schema = str(projection.get("schema") or "").strip()
    if schema != SCHEMA:
        raise UnsupportedReviewReading(f"unsupported_review_reading_schema:{schema or 'missing'}")
    for group in ("market", "account"):
        value = projection.get(group, {})
        if not isinstance(value, Mapping):
            raise UnsupportedReviewReading(f"invalid_review_reading_group:{group}")
        projection[group] = dict(value)
    return projection


def _degraded_field(
    status: str,
    refs: list[dict[str, Any]],
    reason: str,
) -> dict[str, Any]:
    return {
        "value": None,
        "status": status,
        "source_refs": refs,
        "_source_gap_reason": reason,
    }


def _normalize_value(path: str, value: Any) -> tuple[str, Any]:
    """Return (status, normalized value) for the shared v1.2 field contract."""
    if path == "market.market_state":
        if isinstance(value, str) and value.strip() in MARKET_STATE_VALUES:
            return "available", value.strip()
        return "malformed", None
    if path == "market.profit_effect":
        if not isinstance(value, str):
            return "malformed", None
        text = value.strip()
        if text in PROFIT_EFFECT_MISSING_VALUES:
            return "missing", None
        if text == "待核":
            return "quality_unknown", None
        match = re.fullmatch(r"(好|一般|差)\s*(?:[\(（].*[\)）])?", text)
        if match:
            return "available", match.group(1)
        return "malformed", None
    if path in {"market.emotion", "market.sh_index_pct"}:
        normalized: int | float = value
        if isinstance(value, str):
            match = re.fullmatch(r"([-+]?(?:\d+\.?\d*|\.\d+))\s*%", value.strip())
            if not match:
                return "malformed", None
            normalized = float(match.group(1))
        if (
            not isinstance(normalized, (int, float))
            or isinstance(normalized, bool)
            or not math.isfinite(float(normalized))
        ):
            return "malformed", None
        if path == "market.emotion" and not 0 <= float(normalized) <= 100:
            return "malformed", None
        return "available", float(normalized)
    if path in {"market.limit_up_count", "market.limit_down_count"}:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return "available", value
        return "malformed", None
    if path == "account.post_close_positions":
        if not isinstance(value, list) or not value:
            return "malformed", None
        for position in value:
            if (
                not isinstance(position, Mapping)
                or not {"name", "qty", "cost"}.issubset(position)
                or not set(position).issubset({"name", "qty", "cost"})
                or not isinstance(position.get("name"), str)
                or not position["name"].strip()
                or not isinstance(position.get("qty"), (int, float))
                or isinstance(position.get("qty"), bool)
                or not math.isfinite(float(position["qty"]))
                or float(position["qty"]) < 0
                or not isinstance(position.get("cost"), (int, float))
                or isinstance(position.get("cost"), bool)
                or not math.isfinite(float(position["cost"]))
                or float(position["cost"]) < 0
            ):
                return "malformed", None
        return "available", [dict(position) for position in value]
    return "malformed", None


def _normalize_field(
    entry: Any,
    path: str,
    *,
    source_id: Any = None,
    source_revision: Any = None,
) -> dict[str, Any]:
    if entry is None:
        return _degraded_field("missing", [], "source_gap")
    if not isinstance(entry, Mapping) or set(entry) != {"value", "status", "source_refs"}:
        return _degraded_field("malformed", [], "field_envelope_invalid")
    raw_status = entry.get("status")
    status = str(raw_status or "").strip()
    source_refs = entry.get("source_refs")
    if status not in STATUS_VALUES:
        return _degraded_field("quality_unknown", [], "unknown_status")
    if not isinstance(source_refs, list) or any(not _valid_source_ref(ref) for ref in source_refs):
        return _degraded_field("quality_unknown", [], "source_refs_invalid")
    refs = [dict(ref) for ref in source_refs]
    if status in NON_VALUE_STATUSES:
        reason = "source_gap" if status == "missing" else f"{status}_value_hidden"
        return _degraded_field(status, refs, reason)
    if status == "explicit_empty":
        if path == "account.post_close_positions" and entry.get("value") == [] and refs:
            return {"value": [], "status": status, "source_refs": refs}
        return _degraded_field("malformed", refs, "explicit_empty_invalid")
    if not refs:
        return _degraded_field("quality_unknown", refs, "source_refs_missing")
    if path in INDEPENDENT_SOURCE_FIELDS and isinstance(source_id, str) and isinstance(source_revision, str):
        independent = any(
            ref["source_id"] != source_id or ref["revision"] != source_revision
            for ref in refs
        )
        if not independent:
            return _degraded_field("quality_unknown", refs, "independent_source_ref_missing")
    value_status, value = _normalize_value(path, entry.get("value"))
    if value_status != "available":
        return _degraded_field(value_status, refs, "value_invalid")
    return {"value": value, "status": "available", "source_refs": refs}


def _position_summary(positions: list[dict[str, Any]]) -> str:
    """Build the private adapter input consumed by existing Portal redaction."""
    return "；".join(
        f"{position['name']} {position['qty']}@{position['cost']}"
        for position in positions
    )


def adapt_frontmatter(frontmatter: Mapping[str, Any]) -> dict[str, Any]:
    """Map an explicitly declared projection into existing Portal field names.

    Unprojected frontmatter is copied unchanged. Once opted in, omitted market
    fields become ``--`` and never fall back to legacy values; an omitted or
    conflicted position is marked for review instead of being called empty.
    Raw position data stays in the internal field used by the existing
    anonymizer and is only rendered through the existing public summary.
    """
    result = dict(frontmatter or {})
    projection = _parse_projection(result.get("review_reading"))
    if projection is None:
        return result

    normalized: dict[str, Any] = {"schema": SCHEMA, "market": {}, "account": {}}
    for metadata in ("source_id", "source_revision", "sections"):
        if metadata in projection:
            normalized[metadata] = projection[metadata]
    source_gaps: list[dict[str, Any]] = []
    source_id = projection.get("source_id")
    source_revision = projection.get("source_revision")
    for group, field, legacy_key in FIELD_MAP:
        path = f"{group}.{field}"
        entry = _normalize_field(
            projection[group].get(field),
            path,
            source_id=source_id,
            source_revision=source_revision,
        )
        normalized[group][field] = entry
        if entry["status"] not in {"available", "explicit_empty"}:
            source_gaps.append({
                "field": path,
                "status": "quality_unknown",
                "reason": entry.pop("_source_gap_reason", "source_gap"),
                "source_refs": list(entry["source_refs"]),
            })
        if entry["status"] == "available":
            mapped_value = (
                _position_summary(entry["value"])
                if path == "account.post_close_positions"
                else entry["value"]
            )
        elif field == "post_close_positions":
            mapped_value = "空仓" if entry["status"] == "explicit_empty" else POSITION_UNKNOWN
        else:
            mapped_value = "--"
        result[legacy_key] = mapped_value

    result.pop("review_reading", None)
    result["_review_reading_v1"] = normalized
    result["_review_reading_source_gaps"] = source_gaps
    return result
