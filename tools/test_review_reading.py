"""Regression coverage for the opt-in review_reading.v1 Portal adapter."""

import pathlib
import json
import hashlib
import re
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_daily_note
import convert_review
import review_reading
import sync_portal


FIELD_PATHS = (
    "market.market_state",
    "market.profit_effect",
    "market.emotion",
    "market.sh_index_pct",
    "market.limit_up_count",
    "market.limit_down_count",
    "account.post_close_positions",
)
TOOLS_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = TOOLS_DIR / "schemas" / "review_reading.v1.schema.json"
FIXTURE_PATH = TOOLS_DIR / "fixtures" / "review_reading.v1.json"
PROJECTION_FIXTURE_PATH = TOOLS_DIR / "fixtures" / "review_reading.v1.projection.json"
SOURCE_NOTE_PATH = TOOLS_DIR / "fixtures" / "review_reading.v1.source.md"


EXTERNAL_REF = {
    "source_id": "market-snapshot-2026-09-03-close",
    "revision": "b" * 64,
    "locator": "facts.field",
}


def _entry(value, status="available", *, source_refs=None):
    return {
        "value": value,
        "status": status,
        "source_refs": [dict(EXTERNAL_REF)] if source_refs is None else source_refs,
    }


def _projection(omit=()):
    fixture = deepcopy(json.loads(PROJECTION_FIXTURE_PATH.read_text(encoding="utf-8")))
    projection = {
        "schema": fixture["schema"],
        "source_id": "review-2026-09-03",
        "source_revision": "a" * 64,
        "market": fixture["market"],
        "account": fixture["account"],
    }
    for dotted in omit:
        group, key = dotted.split(".", 1)
        projection[group].pop(key, None)
    for group in ("market", "account"):
        for entry in projection[group].values():
            entry["source_refs"] = [dict(EXTERNAL_REF)]
    if "market_state" in projection["market"]:
        projection["market"]["market_state"]["value"] = "低迷"
    if "post_close_positions" in projection["account"]:
        projection["account"]["post_close_positions"] = {
            "value": [{"name": "秘密股份", "qty": 1200, "cost": 7.10}],
            "status": "available",
            "source_refs": [dict(EXTERNAL_REF)],
        }
    return projection


def _write_sidecar(note_path, *, source_date=None, mutate=None):
    payload = deepcopy(json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))
    revision = hashlib.sha256(note_path.read_bytes()).hexdigest()
    if source_date is None:
        match = re.search(r"(?m)^date:\s*(\d{4}-\d{2}-\d{2})\s*$", note_path.read_text(encoding="utf-8"))
        if not match:
            raise AssertionError("fixture source note must declare an ISO date")
        source_date = match.group(1)
    payload["source_revision"] = revision
    payload["market"]["market_state"]["value"] = "主升"
    payload["account"]["post_close_positions"]["value"] = []
    if mutate:
        mutate(payload)
    sidecar_path = (
        note_path.parent
        / "Market_Watch"
        / "artifacts"
        / "review-reading"
        / source_date[:4]
        / source_date
        / f"{revision}.review_reading.v1.json"
    )
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return sidecar_path, payload, revision


def _serialized_projection(projection=None):
    source = _projection() if projection is None else projection
    return json.dumps(source, ensure_ascii=False, separators=(",", ":"))


def _legacy_note(cognition=True):
    cognition_section = (
        "### 今日认知\n\n1. [认知] 旧格式先等确认 — 先确认再行动。\n\n"
        if cognition
        else "### 今日认知\n\n（无新增认知）\n\n"
    )
    return """---
date: 2026-09-02
weekday: 周三
市场状态: 旧格式市场状态
赚钱效应: 一般
情绪值: 55
上证指数: 3200
上证涨幅: 0.25
涨停家数: 30
跌停家数: 8
盘后持仓: 旧持仓 100@10
---
## 一、当日复盘
### 一句话结论
旧格式结论。
## 二、心得与教训
""" + cognition_section + """## 三、次日预案
**总基调**：旧格式保持观察。
### 明日观察
1. 观察市场承接。
"""


def _new_note(projection=None, cognition=True):
    cognition_block = (
        "### 今日认知\n\n1. [认知] 新格式先等确认 — 复盘证据支持这个判断。\n\n"
        if cognition
        else "### 今日认知\n\n（无新增认知）\n\n"
    )
    serialized = _serialized_projection(projection)
    return f"""---
date: 2026-09-03
weekday: 周四
note_schema: yimu.review.v2
stage_final: done
上证指数: 3500
review_reading: {serialized}
---
## 1. 今天发生了什么
### 一句话结论
新格式结论。
## 2. 我的判断和动作
弈沐先观察，等待事实确认。
## 3. 回头看
{cognition_block}## 4. 下一步
**总基调**：按确认后的计划观察。
### 明日观察
1. 观察承接是否延续。
## 折叠：机器附录（自动生成）

PRIVATE_MACHINE_LEDGER private-hash
"""


class PortalSyncReadingSidecarTests(unittest.TestCase):
    def test_default_sync_passes_the_bound_sidecar_to_both_converters(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            market_root = root / "Market_Watch"
            note = root / "2026_9_24_Thursday_ReviewNote.md"
            note.write_text(
                "---\ndate: 2026-09-24\nstage_final: done\n---\n## 一、当日复盘\n",
                encoding="utf-8",
            )
            revision = hashlib.sha256(note.read_bytes()).hexdigest()
            sidecar = (
                market_root / "artifacts" / "review-reading" / "2026" / "2026-09-24"
                / f"{revision}.review_reading.v1.json"
            )
            sidecar.parent.mkdir(parents=True)
            sidecar.write_text("{}", encoding="utf-8")
            review_output = root / "review-notes" / "2026-09-24.html"
            daily_output = root / "daily-notes" / "2026-09-24.html"
            review_output.parent.mkdir()
            daily_output.parent.mkdir()
            review_output.touch()
            daily_output.touch()
            calls = []

            def run(command, **kwargs):
                calls.append([str(item) for item in command])
                return Mock(returncode=0)

            with patch.object(sync_portal, "find_review_note", return_value=note), \
                    patch.object(sync_portal, "read_pnl_last_date", return_value="2026-09-24"), \
                    patch.object(sync_portal, "review_page", return_value=review_output), \
                    patch.object(sync_portal, "daily_note_page", return_value=daily_output), \
                    patch.object(sync_portal, "MARKET_WATCH_ROOT", market_root, create=True), \
                    patch.object(sync_portal.subprocess, "run", side_effect=run):
                code = sync_portal.main(["--date", "2026-09-24"])

        self.assertEqual(0, code)
        converter_calls = [
            call for call in calls
            if any(Path(item).name in {"convert_review.py", "convert_daily_note.py"} for item in call)
        ]
        self.assertEqual(2, len(converter_calls))
        for call in converter_calls:
            self.assertIn("--reading-sidecar", call)
            self.assertEqual(str(sidecar), call[call.index("--reading-sidecar") + 1])

    def test_default_sync_discovers_sealed_sidecar_from_resolved_review_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            market_root = root / "Market_Watch"
            note = root / "2026_9_18_Friday_ReviewNote.md"
            note.write_text(
                "---\ndate: 2026-09-18\nstage_final: done\n"
                "daily_bundle_ref: private-generation\n---\n阅读稿\n",
                encoding="utf-8",
            )
            sealed = root / "sealed_review.md"
            sealed.write_text("SEALED SNAPSHOT\n", encoding="utf-8")
            revision = hashlib.sha256(sealed.read_bytes()).hexdigest()
            sidecar = (
                market_root / "artifacts" / "review-reading" / "2026" / "2026-09-18"
                / f"{revision}.review_reading.v1.json"
            )
            sidecar.parent.mkdir(parents=True)
            sidecar.touch()

            with patch.object(sync_portal, "MARKET_WATCH_ROOT", market_root), \
                    patch("daily_bundle_input.resolve_bundle_reading", return_value={
                        "review_path": sealed,
                    }):
                discovered = sync_portal.find_reading_sidecar(note, "2026-09-18")

        self.assertEqual(sidecar, discovered)


class ReviewReadingAdapterTests(unittest.TestCase):
    def test_schema_and_fixture_define_all_seven_source_bound_fields(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        expected_market = {
            "market_state",
            "profit_effect",
            "emotion",
            "sh_index_pct",
            "limit_up_count",
            "limit_down_count",
        }

        self.assertEqual(schema["properties"]["schema"]["const"], "review_reading.v1")
        self.assertEqual(
            set(schema["required"]),
            {"schema", "source_id", "source_revision", "market", "account", "sections"},
        )
        self.assertEqual(set(schema["properties"]), set(schema["required"]))
        self.assertEqual(set(schema["properties"]["market"]["required"]), expected_market)
        self.assertEqual(set(schema["properties"]["market"]["properties"]), expected_market)
        self.assertEqual(schema["properties"]["account"]["required"], ["post_close_positions"])
        self.assertEqual(set(schema["properties"]["account"]["properties"]), {"post_close_positions"})
        self.assertEqual(schema["properties"]["source_revision"]["pattern"], "^[0-9a-f]{64}$")
        self.assertIn("Inline ReviewNote frontmatter remains", schema["$comment"])
        self.assertIn("not serialized", schema["$comment"])
        envelope = schema["$defs"]["sourceBoundValue"]
        self.assertEqual(set(envelope["required"]), {"value", "status", "source_refs"})
        # Status vocabulary now lives in one place ($defs.status) so producer,
        # live consumer and Portal cannot drift apart again.
        self.assertEqual(
            envelope["properties"]["status"]["$ref"], "#/$defs/status"
        )
        self.assertEqual(
            set(schema["$defs"]["status"]["enum"]),
            {
                "available", "missing", "explicit_empty", "conflict",
                "quality_unknown", "malformed",
            },
        )
        self.assertEqual(
            envelope["properties"]["source_refs"]["items"]["$ref"],
            "#/$defs/sourceRef",
        )
        # Contract v1.2: a source ref must be a structured object. Strings such
        # as "source://daily-close" are not acceptable evidence any more.
        source_ref = schema["$defs"]["sourceRef"]
        self.assertEqual(source_ref["type"], "object")
        self.assertFalse(source_ref["additionalProperties"])
        self.assertEqual(
            set(source_ref["required"]), {"source_id", "revision", "locator"}
        )
        self.assertEqual(
            source_ref["properties"]["source_id"]["$ref"], "#/$defs/sourceId"
        )
        self.assertEqual(fixture["schema"], "review_reading.v1")
        self.assertEqual(fixture["source_id"], "review-2026-09-11")
        self.assertRegex(fixture["source_revision"], r"^[0-9a-f]{64}$")
        self.assertEqual(set(fixture), set(schema["required"]))
        self.assertEqual(hashlib.sha256(SOURCE_NOTE_PATH.read_bytes()).hexdigest(), fixture["source_revision"])
        source_date = re.search(
            r"(?m)^date:\s*(\d{4}-\d{2}-\d{2})\s*$",
            SOURCE_NOTE_PATH.read_text(encoding="utf-8"),
        ).group(1)
        self.assertEqual(source_date, "2026-09-11")
        self.assertEqual(set(fixture["market"]), expected_market)
        self.assertEqual(set(fixture["account"]), {"post_close_positions"})
        self.assertEqual(
            set(fixture["sections"]),
            {"today_happened", "judgment_and_actions", "looking_back", "next_step"},
        )
        self.assertIn("### 一句话结论", fixture["sections"]["today_happened"])
        self.assertIn("### 今日认知", fixture["sections"]["looking_back"])
        self.assertIn("### 明日观察与处理", fixture["sections"]["next_step"])
        # Contract v1.2: each field is typed individually (string counts and
        # off-vocabulary states are rejected), not one generic envelope.
        field_refs = {
            "market_state": "#/$defs/marketStateValue",
            "profit_effect": "#/$defs/profitEffectValue",
            "emotion": "#/$defs/emotionValue",
            "sh_index_pct": "#/$defs/shIndexPctValue",
            "limit_up_count": "#/$defs/countValue",
            "limit_down_count": "#/$defs/countValue",
        }
        for path in FIELD_PATHS:
            group, field = path.split(".", 1)
            if group == "market" and field in field_refs:
                expected = field_refs[field]
            else:
                expected = "#/$defs/postClosePositionsValue"
            self.assertEqual(
                schema["properties"][group]["properties"][field]["$ref"], expected
            )
            value = fixture[group][field]
            self.assertEqual(set(value), {"value", "status", "source_refs"})
            self.assertIn(value["status"], schema["$defs"]["status"]["enum"])
            self.assertIsInstance(value["source_refs"], list)
            self.assertTrue(value["source_refs"])

    def test_schema_matches_v1_2_status_ref_and_field_type_contract(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        defs = schema["$defs"]

        self.assertEqual(
            set(defs["status"]["enum"]),
            {
                "available", "missing", "explicit_empty", "conflict",
                "quality_unknown", "malformed",
            },
        )
        source_ref = defs["sourceRef"]
        self.assertEqual("object", source_ref["type"])
        self.assertEqual(
            set(source_ref["required"]), {"source_id", "revision", "locator"}
        )
        self.assertFalse(source_ref["additionalProperties"])
        self.assertEqual(
            set(source_ref["properties"]),
            {"source_id", "revision", "locator", "line"},
        )
        expected_refs = {
            "market_state": "#/$defs/marketStateValue",
            "profit_effect": "#/$defs/profitEffectValue",
            "emotion": "#/$defs/emotionValue",
            "sh_index_pct": "#/$defs/shIndexPctValue",
            "limit_up_count": "#/$defs/countValue",
            "limit_down_count": "#/$defs/countValue",
        }
        for field, expected in expected_refs.items():
            with self.subTest(field=field):
                self.assertEqual(
                    expected,
                    schema["properties"]["market"]["properties"][field]["$ref"],
                )
        self.assertEqual(
            "#/$defs/postClosePositionsValue",
            schema["properties"]["account"]["properties"]["post_close_positions"]["$ref"],
        )
        position = defs["position"]
        self.assertEqual(set(position["required"]), {"name", "qty", "cost"})
        self.assertFalse(position["additionalProperties"])
        self.assertEqual(
    set(defs["marketState"]["enum"]), {"冰点", "低迷", "主升", "强势", "高潮", "退潮"}
)

    def test_projection_maps_all_seven_values_to_existing_portal_fields(self):
        adapted = review_reading.adapt_frontmatter({"date": "2026-09-03", "review_reading": _projection()})

        self.assertEqual(adapted["市场状态"], "低迷")
        self.assertEqual(adapted["赚钱效应"], "差")
        self.assertEqual(adapted["情绪值"], 24.5)
        self.assertEqual(adapted["上证涨幅"], -0.75)
        self.assertEqual(adapted["涨停家数"], 42)
        self.assertEqual(adapted["跌停家数"], 9)
        self.assertEqual(adapted["盘后持仓"], "秘密股份 1200@7.1")
        self.assertEqual(adapted["_review_reading_v1"]["schema"], "review_reading.v1")

    def test_projection_is_explicit_opt_in_and_legacy_frontmatter_is_unchanged(self):
        legacy = {"市场状态": "旧值", "情绪值": "18.5", "盘后持仓": "空仓"}

        self.assertEqual(review_reading.adapt_frontmatter(legacy), legacy)

    def test_each_absent_projection_field_is_missing_without_legacy_fallback(self):
        legacy_values = {
            "市场状态": "不应回退",
            "赚钱效应": "不应回退",
            "情绪值": 0,
            "上证涨幅": 0,
            "涨停家数": 0,
            "跌停家数": 0,
            "盘后持仓": "秘密旧持仓 999@1.23",
        }
        target_keys = dict(zip(FIELD_PATHS, legacy_values))

        for missing_path in FIELD_PATHS:
            with self.subTest(field=missing_path):
                adapted = review_reading.adapt_frontmatter({
                    **legacy_values,
                    "review_reading": _projection(omit=(missing_path,)),
                })
                key = target_keys[missing_path]
                self.assertNotEqual(adapted[key], legacy_values[key])
                if key != "盘后持仓":
                    self.assertEqual(adapted[key], "--")
                else:
                    self.assertEqual(adapted[key], review_reading.POSITION_UNKNOWN)
                self.assertEqual(
                    adapted["_review_reading_v1"][missing_path.split(".")[0]][missing_path.split(".")[1]]["status"],
                    "missing",
                )
                gap = next(
                    gap for gap in adapted["_review_reading_source_gaps"]
                    if gap["field"] == missing_path
                )
                self.assertEqual(gap["status"], "quality_unknown")
                self.assertEqual(gap["reason"], "source_gap")
                self.assertEqual(gap["source_refs"], [])

    def test_explicit_empty_position_and_conflict_do_not_become_empty_account(self):
        projection = _projection()
        projection["account"]["post_close_positions"] = _entry([], "explicit_empty")
        empty = review_reading.adapt_frontmatter({"review_reading": projection})
        self.assertEqual(empty["盘后持仓"], "空仓")
        self.assertEqual(convert_review.public_position_summary(empty["盘后持仓"]), "空仓")
        self.assertEqual(
            convert_daily_note.public_position_summary(empty["盘后持仓"]),
            "持仓状态以空仓或低暴露方式呈现。",
        )

        projection["account"]["post_close_positions"] = _entry("秘密股份 1200@7.10", "conflict")
        conflict = review_reading.adapt_frontmatter({"review_reading": projection})
        self.assertEqual(conflict["盘后持仓"], review_reading.POSITION_UNKNOWN)
        self.assertEqual(convert_review.public_position_summary(conflict["盘后持仓"]), "待核验")
        self.assertEqual(
            convert_daily_note.public_position_summary(conflict["盘后持仓"]),
            "持仓状态待核实。",
        )

    def test_empty_or_unknown_positions_never_expose_private_details(self):
        projection = _projection()
        projection["account"]["post_close_positions"] = _entry(
            [{"name": "秘密股份", "qty": 1200, "cost": 7.10}],
            status="available",
        )
        adapted = review_reading.adapt_frontmatter({"review_reading": projection})
        self.assertEqual(convert_review.public_position_summary(adapted["盘后持仓"]), "持仓")
        self.assertEqual(
            convert_daily_note.public_position_summary(adapted["盘后持仓"]),
            "持仓状态以公开摘要呈现，不展开标的、数量和成本。",
        )
        self.assertNotIn("秘密股份", convert_daily_note.public_position_summary(adapted["盘后持仓"]))
        self.assertNotIn("1200", convert_daily_note.public_position_summary(adapted["盘后持仓"]))
        self.assertNotIn("7.10", convert_daily_note.public_position_summary(adapted["盘后持仓"]))

    def test_unknown_projection_schema_is_rejected(self):
        with self.assertRaises(review_reading.UnsupportedReviewReading) as ctx:
            review_reading.adapt_frontmatter({"review_reading": {"schema": "review_reading.v9"}})
        self.assertIn("unsupported_review_reading_schema:review_reading.v9", str(ctx.exception))

    def test_malformed_position_item_becomes_malformed_with_source_gap(self):
        projection = _projection()
        projection["account"]["post_close_positions"] = _entry(
            [{"name": "秘密股份", "shares": 1200}], "available"
        )
        adapted = review_reading.adapt_frontmatter({"review_reading": projection})
        self.assertEqual(adapted["盘后持仓"], review_reading.POSITION_UNKNOWN)
        field = adapted["_review_reading_v1"]["account"]["post_close_positions"]
        self.assertEqual("malformed", field["status"])
        self.assertIsNone(field["value"])
        gap = next(
            gap for gap in adapted["_review_reading_source_gaps"]
            if gap["field"] == "account.post_close_positions"
        )
        self.assertEqual(gap["status"], "quality_unknown")
        self.assertEqual(gap["reason"], "value_invalid")
        self.assertEqual(gap["source_refs"], [EXTERNAL_REF])

    def test_string_counts_and_uncited_available_values_are_not_guessed(self):
        projection = _projection()
        projection["market"]["limit_up_count"] = _entry("42")
        projection["market"]["emotion"] = _entry(24.5)
        projection["market"]["emotion"]["source_refs"] = []
        adapted = review_reading.adapt_frontmatter({"review_reading": projection})
        self.assertEqual(adapted["涨停家数"], "--")
        self.assertEqual(adapted["情绪值"], "--")
        gaps = {item["field"]: item for item in adapted["_review_reading_source_gaps"]}
        self.assertEqual(gaps["market.limit_up_count"]["status"], "quality_unknown")
        self.assertEqual(gaps["market.emotion"]["reason"], "source_refs_missing")

    def test_available_measurement_cannot_be_backed_only_by_review_note_self_reference(self):
        projection = _projection()
        self_ref = {
            "source_id": projection["source_id"],
            "revision": projection["source_revision"],
            "locator": "frontmatter:情绪值",
        }
        projection["market"]["emotion"] = _entry(24.5, source_refs=[self_ref])

        adapted = review_reading.adapt_frontmatter({"review_reading": projection})

        field = adapted["_review_reading_v1"]["market"]["emotion"]
        self.assertEqual("quality_unknown", field["status"])
        self.assertIsNone(field["value"])
        self.assertEqual("--", adapted["情绪值"])

    def test_market_state_may_use_review_note_self_reference(self):
        projection = _projection()
        self_ref = {
            "source_id": projection["source_id"],
            "revision": projection["source_revision"],
            "locator": "frontmatter:市场状态",
        }
        projection["market"]["market_state"] = _entry("强势", source_refs=[self_ref])

        adapted = review_reading.adapt_frontmatter({"review_reading": projection})

        self.assertEqual("available", adapted["_review_reading_v1"]["market"]["market_state"]["status"])
        self.assertEqual("强势", adapted["市场状态"])

    def test_string_or_incomplete_source_ref_degrades_available_value_to_quality_unknown(self):
        for refs in ([], ["source://daily-close"], [{"source_id": "source-only"}]):
            with self.subTest(refs=refs):
                projection = _projection()
                projection["market"]["sh_index_pct"] = _entry(-0.39, source_refs=refs)
                adapted = review_reading.adapt_frontmatter({"review_reading": projection})
                field = adapted["_review_reading_v1"]["market"]["sh_index_pct"]
                self.assertEqual("quality_unknown", field["status"])
                self.assertIsNone(field["value"])
                self.assertEqual("--", adapted["上证涨幅"])

    def test_unknown_status_is_quality_unknown_and_never_renders_its_numeric_value(self):
        projection = _projection()
        projection["market"]["sh_index_pct"] = {
            "value": -0.39,
            "status": "future_status",
            "source_refs": [dict(EXTERNAL_REF)],
        }
        projection["market"]["emotion"] = {
            "value": 42,
            "status": "future_status",
            "source_refs": [dict(EXTERNAL_REF)],
        }

        try:
            adapted = review_reading.adapt_frontmatter({"review_reading": projection})
        except review_reading.UnsupportedReviewReading as exc:
            self.fail(f"unknown status must degrade instead of rejecting: {exc}")

        self.assertEqual("--", adapted["上证涨幅"])
        self.assertEqual("--", adapted["情绪值"])
        for name in ("sh_index_pct", "emotion"):
            field = adapted["_review_reading_v1"]["market"][name]
            self.assertEqual("quality_unknown", field["status"])
            self.assertIsNone(field["value"])

    def test_percent_strings_are_immediately_normalized_to_numbers(self):
        projection = _projection()
        projection["market"]["sh_index_pct"] = _entry("-1.22%")
        projection["market"]["emotion"] = _entry("42.5%")

        adapted = review_reading.adapt_frontmatter({"review_reading": projection})

        self.assertEqual(-1.22, adapted["上证涨幅"])
        self.assertEqual(42.5, adapted["情绪值"])
        self.assertEqual(-1.22, adapted["_review_reading_v1"]["market"]["sh_index_pct"]["value"])
        self.assertEqual(42.5, adapted["_review_reading_v1"]["market"]["emotion"]["value"])

    def test_source_refs_accept_workspace_objects_and_preserve_them_in_machine_state(self):
        projection = _projection()
        ref = {
            "source_id": "review:2026-09-03",
            "revision": "a" * 64,
            "locator": "frontmatter:市场状态",
            "line": 3,
        }
        projection["market"]["market_state"]["source_refs"] = [ref]
        adapted = review_reading.adapt_frontmatter({"review_reading": projection})
        self.assertEqual(
            adapted["_review_reading_v1"]["market"]["market_state"]["source_refs"],
            [ref],
        )

    def test_malformed_source_refs_degrade_without_exposing_available_value(self):
        invalid_refs = (
            [3],
            [{"revision": "a" * 64}],
            [{"source_id": "../secret"}],
            [{"source_id": "review:2026-09-03", "revision": "bad"}],
            [{
                "source_id": "review:2026-09-03",
                "revision": "a" * 64,
                "locator": "frontmatter:市场状态",
                "unexpected": True,
            }],
        )
        for refs in invalid_refs:
            with self.subTest(refs=refs):
                projection = _projection()
                projection["market"]["market_state"]["source_refs"] = refs
                adapted = review_reading.adapt_frontmatter({"review_reading": projection})
                field = adapted["_review_reading_v1"]["market"]["market_state"]
                self.assertEqual("quality_unknown", field["status"])
                self.assertIsNone(field["value"])
                self.assertEqual("--", adapted["市场状态"])

    def test_human_unconfirmed_blocks_next_day_actions_even_when_final_stage_is_done(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            note = root / "2026_9_3_Thursday_ReviewNote.md"
            note.write_text(
                _new_note().replace(
                    "stage_final: done",
                    "stage_final: done\nhuman_unconfirmed: D2 待确认",
                ),
                encoding="utf-8",
            )

            def unconfirmed_plan(payload):
                payload["sections"]["next_step"] = (
                    "**总基调**：等待条件确认。\n\n"
                    "### 明日观察与处理\n\n1. 触发即买。"
                )

            sidecar_path, _, _ = _write_sidecar(note, mutate=unconfirmed_plan)
            daily = convert_daily_note.build_daily_note(
                note, reading_sidecar_path=sidecar_path
            )
            page = convert_daily_note.render_daily_note_page(daily)

        self.assertEqual(["次日观察与处理尚未确认。"], daily.watch_items)
        self.assertIn("未确认", page)
        self.assertNotIn("触发即买", page)

    def test_public_review_status_marks_human_unconfirmed_as_not_final(self):
        status, text = convert_review.public_review_status({
            "stage_red_team": "done",
            "stage_final": "done",
            "human_unconfirmed": "D2 待确认",
        })

        self.assertEqual("amber", status)
        self.assertIn("未确认", text)
        self.assertNotIn("终稿", text)

    def test_v2_projection_does_not_require_raw_machine_appendix(self):
        with tempfile.TemporaryDirectory() as temporary:
            note = Path(temporary) / '2026_9_11_Friday_ReviewNote.md'
            note.write_text('---\ndate: 2026-09-11\nnote_schema: yimu.review.v2\nstage_final: pending\n---\n正文。\n')
            sidecar, _, _ = _write_sidecar(note)
            with patch.object(convert_review, 'REVIEW_NOTES', Path(temporary)):
                _, output = convert_review.convert_md_to_html(note, reading_sidecar_path=sidecar)
            self.assertIn('当时可见时点未核实', output.read_text())
            with self.assertRaises(convert_review.UnsupportedNoteSchema):
                convert_review.convert_md_to_html(note)

    def test_independent_sidecar_drives_both_converters_without_publishing_refs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            note = root / "2026_9_11_Friday_ReviewNote.md"
            note.write_bytes(SOURCE_NOTE_PATH.read_bytes())

            def add_machine_ref(payload):
                payload["market"]["market_state"]["source_refs"] = [{
                    "source_id": "private-sidecar-ref",
                    "revision": "b" * 64,
                    "locator": "review/market",
                }]

            sidecar_path, _, revision = _write_sidecar(note, mutate=add_machine_ref)
            reading_text, reading_fm, bundle_backed = convert_review.read_review_input(
                note, reading_sidecar_path=sidecar_path
            )
            with patch.object(convert_review, "REVIEW_NOTES", root):
                _, review_path = convert_review.convert_md_to_html(
                    note, reading_sidecar_path=sidecar_path
                )
                review_html = review_path.read_text(encoding="utf-8")
            daily = convert_daily_note.build_daily_note(
                note, reading_sidecar_path=sidecar_path
            )
            daily_html = convert_daily_note.render_daily_note_page(daily)

        self.assertFalse(bundle_backed)
        self.assertEqual(reading_fm["_review_reading_v1"]["source_revision"], revision)
        self.assertEqual(reading_fm["_review_reading_v1"]["source_id"], "review-2026-09-11")
        self.assertEqual(
            set(reading_fm["_review_reading_v1"]["sections"]),
            {"today_happened", "judgment_and_actions", "looking_back", "next_step"},
        )
        self.assertEqual(
            reading_fm["_review_reading_v1"]["market"]["market_state"]["source_refs"],
            [{"source_id": "private-sidecar-ref", "revision": "b" * 64, "locator": "review/market"}],
        )
        self.assertIn("## 1. 今天发生了什么", reading_text)
        self.assertIn("## 4. 下一步", reading_text)
        self.assertIn("市场缩量分化", review_html)
        self.assertEqual(daily.summary, "市场缩量分化，保持观察。")
        self.assertEqual(daily.market_status, "主升")
        self.assertEqual(daily.cognition_title, "")
        self.assertNotIn('class="note-cognition-card"', daily_html)
        for private_value in (
            "private-sidecar-ref", revision, "b" * 64, "market-close", "hermes-close"
        ):
            self.assertNotIn(private_value, review_html)
            self.assertNotIn(private_value, daily_html)
        self.assertIn("空仓", review_html)
        self.assertIn("空仓", daily_html)

    def test_sidecar_rejects_wrong_source_revision_date_path_and_artifact_shape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            note = root / "2026_9_11_Friday_ReviewNote.md"

            cases = (
                (
                    "wrong_revision",
                    "2026-09-11",
                    lambda payload: payload.update({"source_revision": "f" * 64}),
                    "review_reading_source_revision_mismatch",
                ),
                (
                    "wrong_date_path",
                    "2026-09-12",
                    None,
                    "review_reading_sidecar_path_mismatch",
                ),
                (
                    "producer_artifact_not_sidecar",
                    "2026-09-11",
                    lambda payload: payload.update({
                        "date": "2026-09-11",
                        "body": {"format": "markdown", "markdown": "not persisted"},
                        "content_status": "complete",
                    }),
                    "invalid_review_reading_sidecar_shape",
                ),
            )
            for label, sidecar_date, mutate, expected_error in cases:
                with self.subTest(case=label):
                    note.write_bytes(SOURCE_NOTE_PATH.read_bytes())
                    sidecar_path, _, _ = _write_sidecar(
                        note, source_date=sidecar_date, mutate=mutate
                    )
                    with self.assertRaises(review_reading.UnsupportedReviewReading) as ctx:
                        convert_review.read_review_input(
                            note, reading_sidecar_path=sidecar_path
                        )
                    self.assertIn(expected_error, str(ctx.exception))

    def test_unsealed_new_review_and_daily_note_keep_four_sections_and_old_anchors(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            note = root / "2026_9_3_Thursday_ReviewNote.md"
            note.write_text(_new_note(), encoding="utf-8")
            with patch.object(convert_review, "REVIEW_NOTES", root):
                _, review_path = convert_review.convert_md_to_html(note)
                review_html = review_path.read_text(encoding="utf-8")
            daily = convert_daily_note.build_daily_note(note)
            reading_text, reading_fm, _ = convert_review.read_review_input(note)
            reading_sections = convert_review.extract_review_reading_sections(reading_text, reading_fm)

        self.assertIn("新格式结论", review_html)
        self.assertIn("弈沐先观察，等待事实确认", review_html)
        self.assertIn("42涨停 / 9跌停", review_html)
        self.assertIn("情绪 24.5", review_html)
        self.assertIn("新格式结论", daily.summary)
        self.assertEqual(daily.market_status, "低迷")
        self.assertEqual(daily.cognition_title, "新格式先等确认")
        self.assertEqual(daily.cognition_evidence, "复盘证据支持这个判断。")
        self.assertEqual(daily.watch_items, ["观察承接是否延续。"])
        self.assertEqual(
            list(reading_sections.keys()),
            ["1. 今天发生了什么", "2. 我的判断和动作", "3. 回头看", "4. 下一步"],
        )
        self.assertIn("### 一句话结论", reading_sections["1. 今天发生了什么"])
        self.assertIn("### 今日认知", reading_sections["3. 回头看"])
        self.assertIn("**总基调**", reading_sections["4. 下一步"])
        self.assertIn("### 明日观察", reading_sections["4. 下一步"])
        self.assertNotIn("秘密股份", str(daily.market_facts))
        self.assertNotIn("1200", str(daily.market_facts))
        self.assertNotIn("7.10", str(daily.market_facts))
        self.assertNotIn("秘密股份", review_html)
        self.assertNotIn("1200", review_html)
        self.assertNotIn("7.10", review_html)
        self.assertNotIn("PRIVATE_MACHINE_LEDGER", review_html)
        self.assertNotIn("source://daily-close", review_html)
        for heading in (
            "1. 今天发生了什么",
            "2. 我的判断和动作",
            "3. 回头看",
            "4. 下一步",
        ):
            self.assertIn(heading, review_html)

    def test_legacy_reviewnote_default_output_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            note = root / "2026_9_2_Wednesday_ReviewNote.md"
            note.write_text(_legacy_note(cognition=False), encoding="utf-8")
            daily = convert_daily_note.build_daily_note(note)
            page = convert_daily_note.render_daily_note_page(daily)
            with patch.object(convert_review, "REVIEW_NOTES", root):
                _, review_path = convert_review.convert_md_to_html(note)
                review_html = review_path.read_text(encoding="utf-8")

        self.assertEqual(daily.summary, "旧格式结论。")
        self.assertEqual(daily.cognition_title, "先把当天经验压成可复用原则")
        self.assertIn('class="note-cognition-card"', page)
        self.assertIn("旧格式结论", review_html)
        self.assertNotIn("review-reading-1", review_html)

    def test_sealed_review_sidecar_is_bound_to_resolved_review_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            note = root / "2026_9_3_Thursday_ReviewNote.md"
            note.write_text(
                _new_note().replace(
                    "上证指数: 3500",
                    "stage_final: done\nhuman_unconfirmed:\ndaily_bundle_ref: private-generation\n上证指数: 3500",
                ),
                encoding="utf-8",
            )
            sealed = root / "sealed_review.md"
            sealed.write_text(
                "---\ndate: 2026-09-03\nstage_final: done\n---\n"
                "SEALED_MACHINE_SNAPSHOT\n",
                encoding="utf-8",
            )
            payload = deepcopy(json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))
            revision = hashlib.sha256(sealed.read_bytes()).hexdigest()
            payload["source_revision"] = revision
            payload["market"]["market_state"]["value"] = "主升"
            payload["account"]["post_close_positions"]["value"] = []
            sidecar = (
                root
                / "Market_Watch"
                / "artifacts"
                / "review-reading"
                / "2026"
                / "2026-09-03"
                / f"{revision}.review_reading.v1.json"
            )
            sidecar.parent.mkdir(parents=True)
            sidecar.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            with patch("daily_bundle_input.resolve_bundle_reading", return_value={
                "reading_text": note.read_text(encoding="utf-8"),
                "machine_text": sealed.read_text(encoding="utf-8"),
                "review_path": sealed,
            }):
                try:
                    _body, facts, bundle_backed = convert_review.read_review_input(
                        note, reading_sidecar_path=sidecar
                    )
                except review_reading.UnsupportedReviewReading as exc:
                    self.fail(f"sealed sidecar must bind review_path: {exc}")

        self.assertTrue(bundle_backed)
        self.assertEqual(revision, facts["_review_reading_v1"]["source_revision"])
        self.assertEqual("主升", facts["市场状态"])

    def test_sealed_review_uses_projection_from_validated_machine_text(self):
        reading = _new_note().split("\n---\n", 1)[1]
        reading = reading.split("## 折叠：机器附录", 1)[0]
        note_text = """---
date: 2026-09-03
weekday: 周四
note_schema: yimu.review.v2
stage_final: done
daily_bundle_ref: private-generation
---
""" + reading
        machine_text = """---
date: 2026-09-03
weekday: 周四
stage_final: done
review_reading: """ + _serialized_projection() + """
---
PRIVATE_SEALED_LEDGER raw-secret
"""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            note = root / "2026_9_3_Thursday_ReviewNote.md"
            note.write_text(note_text, encoding="utf-8")
            with patch("daily_bundle_input.resolve_bundle_reading", return_value={
                "reading_text": note_text,
                "machine_text": machine_text,
            }), patch.object(convert_review, "REVIEW_NOTES", root):
                _, review_path = convert_review.convert_md_to_html(note)
                review_html = review_path.read_text(encoding="utf-8")
                daily = convert_daily_note.build_daily_note(note)

        self.assertIn("新格式结论", review_html)
        self.assertEqual(daily.market_status, "低迷")
        self.assertEqual(daily.cognition_title, "新格式先等确认")
        self.assertEqual(daily.watch_items, ["观察承接是否延续。"])
        self.assertNotIn("PRIVATE_SEALED_LEDGER", review_html)
        self.assertNotIn("raw-secret", review_html)
        self.assertNotIn("秘密股份", str(daily))
        self.assertNotIn("1200", str(daily))
        self.assertNotIn("7.10", str(daily))

    def test_new_review_with_no_new_cognition_does_not_invent_a_principle(self):
        with tempfile.TemporaryDirectory() as temporary:
            note = Path(temporary) / "2026_9_3_Thursday_ReviewNote.md"
            note.write_text(_new_note(cognition=False), encoding="utf-8")
            daily = convert_daily_note.build_daily_note(note)

        self.assertEqual(daily.cognition_title, "")
        self.assertEqual(daily.cognition_evidence, "")
        self.assertEqual(daily.cognition_action, "")
        self.assertNotIn(
            'class="note-cognition-card"',
            convert_daily_note.render_daily_note_page(daily),
        )

    def test_sealed_new_review_with_empty_cognition_stays_empty(self):
        reading = _new_note(cognition=False).split("\n---\n", 1)[1]
        reading = reading.split("## 折叠：机器附录", 1)[0]
        note_text = """---
date: 2026-09-03
weekday: 周四
note_schema: yimu.review.v2
stage_final: done
daily_bundle_ref: private-generation
---
""" + reading
        machine_text = """---
date: 2026-09-03
weekday: 周四
stage_final: done
review_reading: """ + _serialized_projection() + """
---
PRIVATE_SEALED_LEDGER raw-secret
"""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            note = root / "2026_9_3_Thursday_ReviewNote.md"
            note.write_text(note_text, encoding="utf-8")
            with patch("daily_bundle_input.resolve_bundle_reading", return_value={
                "reading_text": note_text,
                "machine_text": machine_text,
            }), patch.object(convert_review, "REVIEW_NOTES", root):
                _, review_path = convert_review.convert_md_to_html(note)
                review_html = review_path.read_text(encoding="utf-8")
                daily = convert_daily_note.build_daily_note(note)

        self.assertEqual(daily.cognition_title, "")
        self.assertEqual(daily.cognition_evidence, "")
        self.assertEqual(daily.cognition_action, "")
        self.assertNotIn('class="note-cognition-card"', convert_daily_note.render_daily_note_page(daily))
        self.assertIn("（无新增认知）", review_html)
        self.assertNotIn("PRIVATE_SEALED_LEDGER", review_html)


class VersionedSidecarPathTests(unittest.TestCase):
    """Portal must accept the contract §6 versioned file name."""

    def test_versioned_and_legacy_names_are_accepted(self):
        import hashlib
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            note = pathlib.Path(tmp) / "n.md"
            note.write_text("hello", encoding="utf-8")
            revision = hashlib.sha256(b"hello").hexdigest()
            base = pathlib.Path(tmp) / "Market_Watch/artifacts/review-reading/2026/2026-09-23"
            base.mkdir(parents=True)
            for name in (
                f"{revision}.review_reading.v1.json",
                f"{revision}.1.0.0.ev1.review_reading.v1.json",
                f"{revision}.2.3.1.ev9.review_reading.v1.json",
            ):
                target = base / name
                target.write_text(json.dumps({"schema": "review_reading.v1"}), encoding="utf-8")
                with self.subTest(name=name):
                    try:
                        review_reading.read_sidecar(target, source_path=note,
                                                    source_date="2026-09-23")
                    except Exception as exc:  # noqa: BLE001
                        # 只关心路径契约：任何非 path_mismatch 的后续校验失败
                        # （如此处 payload 形状不完整）都说明命名已被接受。
                        self.assertNotIn("path_mismatch", str(exc), name)

    def test_foreign_source_name_is_rejected(self):
        import hashlib
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            note = pathlib.Path(tmp) / "n.md"
            note.write_text("hello", encoding="utf-8")
            base = pathlib.Path(tmp) / "Market_Watch/artifacts/review-reading/2026/2026-09-23"
            base.mkdir(parents=True)
            foreign = base / f"{'b' * 64}.1.0.0.ev1.review_reading.v1.json"
            foreign.write_text("{}", encoding="utf-8")
            with self.assertRaises(Exception) as ctx:
                review_reading.read_sidecar(foreign, source_path=note, source_date="2026-09-23")
            self.assertIn("path_mismatch", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
