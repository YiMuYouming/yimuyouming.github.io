"""Adapter for explicit review_reading.v1 sidecars and transition frontmatter.

The canonical input is a date-scoped JSON sidecar bound to the current source
ReviewNote revision. An inline frontmatter projection remains a compatibility
path while producers migrate; unmarked historical notes are unchanged.
"""

from __future__ import annotations

import json
import hashlib
import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any


SCHEMA = "review_reading.v1"
POSITION_UNKNOWN = "__review_reading_position_unknown__"
STATUS_VALUES = frozenset({"available", "missing", "explicit_empty", "conflict"})
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
    if isinstance(ref, str):
        return bool(ref.strip())
    if not isinstance(ref, Mapping):
        return False
    source_id = ref.get("source_id")
    if not isinstance(source_id, str) or not SOURCE_ID_RE.fullmatch(source_id):
        return False
    revision = ref.get("revision")
    if revision is not None and (
        not isinstance(revision, str) or not SHA256_RE.fullmatch(revision)
    ):
        return False
    section_id = ref.get("section_id")
    if section_id is not None and (
        not isinstance(section_id, str) or not section_id.strip() or len(section_id) > 180
    ):
        return False
    return True


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
    expected_name = f"{source_revision}.{SCHEMA}.json"
    expected_suffix = (
        "Market_Watch",
        "artifacts",
        "review-reading",
        str(parsed_date.year),
        source_date,
        expected_name,
    )
    if tuple(sidecar_path.parts[-len(expected_suffix):]) != expected_suffix:
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


def _normalize_field(entry: Any, path: str) -> dict[str, Any]:
    if entry is None:
        return {"value": None, "status": "missing", "source_refs": [], "_source_gap_reason": "source_gap"}
    if not isinstance(entry, Mapping):
        raise UnsupportedReviewReading(f"invalid_review_reading_field:{path}")
    if not {"value", "status", "source_refs"}.issubset(entry):
        raise UnsupportedReviewReading(f"incomplete_review_reading_field:{path}")
    status = str(entry.get("status") or "").strip()
    if status not in STATUS_VALUES:
        raise UnsupportedReviewReading(f"invalid_review_reading_status:{path}:{status}")
    source_refs = entry.get("source_refs")
    if not isinstance(source_refs, list) or any(not _valid_source_ref(ref) for ref in source_refs):
        raise UnsupportedReviewReading(f"invalid_review_reading_source_refs:{path}")
    refs = [dict(ref) if isinstance(ref, Mapping) else ref for ref in source_refs]
    group, field = path.split(".", 1)
    value = entry.get("value")
    if status == "available" and not _has_confirmed_value(group, field, value):
        return {"value": None, "status": "missing", "source_refs": refs, "_source_gap_reason": "unconfirmed_value_semantics"}
    if status == "explicit_empty" and path == "account.post_close_positions":
        if value not in (None, "", [], {}, "空仓"):
            return {"value": None, "status": "conflict", "source_refs": refs, "_source_gap_reason": "explicit_empty_conflict"}
    if status in {"available", "explicit_empty"} and not any(refs):
        return {"value": None, "status": "missing", "source_refs": refs, "_source_gap_reason": "source_refs_missing"}
    if status == "missing":
        return {"value": None, "status": status, "source_refs": refs, "_source_gap_reason": "source_gap"}
    if status == "conflict":
        return {"value": None, "status": status, "source_refs": refs, "_source_gap_reason": "source_conflict"}
    return {
        "value": value,
        "status": status,
        "source_refs": refs,
    }


def _has_confirmed_value(group: str, field: str, value: Any) -> bool:
    """Accept only types that match current Portal field semantics."""
    if group == "account" and field == "post_close_positions":
        return isinstance(value, str) and bool(value.strip()) and value.strip() != "空仓"
    if field in {"market_state", "profit_effect"}:
        return isinstance(value, str) and bool(value.strip())
    if field in {"emotion", "sh_index_pct"}:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if field in {"limit_up_count", "limit_down_count"}:
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0
    return False


def adapt_frontmatter(frontmatter: Mapping[str, Any]) -> dict[str, Any]:
    """Map an explicitly declared projection into existing Portal field names.

    Unprojected frontmatter is copied unchanged. Once opted in, omitted market
    fields become ``--`` and never fall back to legacy values; an omitted or
    conflicted position is marked for review instead of being called empty.
    Raw position data stays in the internal field used by the existing
    anonymizer and is only rendered through the existing public summary. The
    proposed contract does not define position-item fields, so only the current
    ReviewNote string form is considered available; other shapes become gaps.
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
    for group, field, legacy_key in FIELD_MAP:
        path = f"{group}.{field}"
        entry = _normalize_field(projection[group].get(field), path)
        normalized[group][field] = entry
        if entry["status"] in {"missing", "conflict"}:
            source_gaps.append({
                "field": path,
                "status": "unknown",
                "reason": entry.pop("_source_gap_reason", "source_gap"),
                "source_refs": list(entry["source_refs"]),
            })
        if entry["status"] == "available":
            mapped_value = entry["value"]
        elif field == "post_close_positions":
            mapped_value = "空仓" if entry["status"] == "explicit_empty" else POSITION_UNKNOWN
        else:
            mapped_value = "--"
        result[legacy_key] = mapped_value

    result.pop("review_reading", None)
    result["_review_reading_v1"] = normalized
    result["_review_reading_source_gaps"] = source_gaps
    return result
