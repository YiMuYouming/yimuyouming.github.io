"""Regression coverage for the opt-in review_reading.v1 Portal adapter."""

import json
import hashlib
import re
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_daily_note
import convert_review
import review_reading


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


def _entry(value, status="available"):
    return {"value": value, "status": status, "source_refs": ["source://daily-close"]}


def _projection(omit=()):
    fixture = deepcopy(json.loads(PROJECTION_FIXTURE_PATH.read_text(encoding="utf-8")))
    projection = {
        "schema": fixture["schema"],
        "market": fixture["market"],
        "account": fixture["account"],
    }
    for dotted in omit:
        group, key = dotted.split(".", 1)
        projection[group].pop(key, None)
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
        self.assertEqual(
            set(envelope["properties"]["status"]["enum"]),
            {"available", "missing", "explicit_empty", "conflict"},
        )
        self.assertEqual(
            envelope["properties"]["source_refs"]["items"]["$ref"],
            "#/$defs/sourceRef",
        )
        source_ref_schemas = schema["$defs"]["sourceRef"]["oneOf"]
        self.assertEqual(len(source_ref_schemas), 2)
        self.assertEqual(source_ref_schemas[0]["type"], "string")
        self.assertEqual(source_ref_schemas[1]["type"], "object")
        self.assertEqual(source_ref_schemas[1]["required"], ["source_id"])
        self.assertEqual(source_ref_schemas[1]["properties"]["source_id"]["$ref"], "#/$defs/sourceId")
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
        for path in FIELD_PATHS:
            group, field = path.split(".", 1)
            self.assertEqual(
                schema["properties"][group]["properties"][field]["$ref"],
                "#/$defs/sourceBoundValue",
            )
            value = fixture[group][field]
            self.assertEqual(set(value), {"value", "status", "source_refs"})
            self.assertIn(value["status"], envelope["properties"]["status"]["enum"])
            self.assertIsInstance(value["source_refs"], list)
            self.assertTrue(value["source_refs"])

    def test_projection_maps_all_seven_values_to_existing_portal_fields(self):
        adapted = review_reading.adapt_frontmatter({"date": "2026-09-03", "review_reading": _projection()})

        self.assertEqual(adapted["市场状态"], "震荡偏弱")
        self.assertEqual(adapted["赚钱效应"], "差")
        self.assertEqual(adapted["情绪值"], 24.5)
        self.assertEqual(adapted["上证涨幅"], -0.75)
        self.assertEqual(adapted["涨停家数"], 42)
        self.assertEqual(adapted["跌停家数"], 9)
        self.assertEqual(adapted["盘后持仓"], "秘密股份 1200@7.10")
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
                self.assertEqual(gap["status"], "unknown")
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
            "秘密股份 1200@7.10", status="available"
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

    def test_unconfirmed_position_shape_becomes_unknown_with_source_gap(self):
        projection = _projection()
        projection["account"]["post_close_positions"] = _entry([{"name": "秘密股份", "shares": 1200}], "available")
        adapted = review_reading.adapt_frontmatter({"review_reading": projection})
        self.assertEqual(adapted["盘后持仓"], review_reading.POSITION_UNKNOWN)
        gap = next(
            gap for gap in adapted["_review_reading_source_gaps"]
            if gap["field"] == "account.post_close_positions"
        )
        self.assertEqual(gap["status"], "unknown")
        self.assertEqual(gap["reason"], "unconfirmed_value_semantics")
        self.assertEqual(gap["source_refs"], ["source://daily-close"])

    def test_string_counts_and_uncited_available_values_are_not_guessed(self):
        projection = _projection()
        projection["market"]["limit_up_count"] = _entry("42")
        projection["market"]["emotion"] = _entry(24.5)
        projection["market"]["emotion"]["source_refs"] = []
        adapted = review_reading.adapt_frontmatter({"review_reading": projection})
        self.assertEqual(adapted["涨停家数"], "--")
        self.assertEqual(adapted["情绪值"], "--")
        gaps = {item["field"]: item for item in adapted["_review_reading_source_gaps"]}
        self.assertEqual(gaps["market.limit_up_count"]["status"], "unknown")
        self.assertEqual(gaps["market.emotion"]["reason"], "source_refs_missing")

    def test_source_refs_accept_workspace_objects_and_preserve_them_in_machine_state(self):
        projection = _projection()
        ref = {
            "source_id": "review:2026-09-03",
            "revision": "a" * 64,
            "section_id": "market",
            "record_id": "record-17",
        }
        projection["market"]["market_state"]["source_refs"] = [ref]
        adapted = review_reading.adapt_frontmatter({"review_reading": projection})
        self.assertEqual(
            adapted["_review_reading_v1"]["market"]["market_state"]["source_refs"],
            [ref],
        )

    def test_source_refs_reject_malformed_values_and_workspace_objects(self):
        projection = _projection()
        invalid_refs = ([3], [{"revision": "a" * 64}], [{"source_id": "../secret"}], [
            {"source_id": "review:2026-09-03", "revision": "bad"}
        ])
        for refs in invalid_refs:
            with self.subTest(refs=refs):
                projection["market"]["market_state"]["source_refs"] = refs
                with self.assertRaises(review_reading.UnsupportedReviewReading) as ctx:
                    review_reading.adapt_frontmatter({"review_reading": projection})
                self.assertIn(
                    "invalid_review_reading_source_refs:market.market_state",
                    str(ctx.exception),
                )

    def test_independent_sidecar_drives_both_converters_without_publishing_refs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            note = root / "2026_9_11_Friday_ReviewNote.md"
            note.write_bytes(SOURCE_NOTE_PATH.read_bytes())

            def add_machine_ref(payload):
                payload["market"]["market_state"]["source_refs"] = [{
                    "source_id": "private-sidecar-ref",
                    "revision": "b" * 64,
                    "section_id": "review/market",
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
            [{"source_id": "private-sidecar-ref", "revision": "b" * 64, "section_id": "review/market"}],
        )
        self.assertIn("## 1. 今天发生了什么", reading_text)
        self.assertIn("## 4. 下一步", reading_text)
        self.assertIn("市场缩量分化", review_html)
        self.assertEqual(daily.summary, "市场缩量分化，保持观察。")
        self.assertEqual(daily.market_status, "震荡偏强")
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
        self.assertEqual(daily.market_status, "震荡偏弱")
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

    def test_sealed_review_uses_projection_from_validated_machine_text(self):
        reading = _new_note().split("\n---\n", 1)[1]
        reading = reading.split("## 折叠：机器附录", 1)[0]
        note_text = """---
date: 2026-09-03
weekday: 周四
note_schema: yimu.review.v2
daily_bundle_ref: private-generation
---
""" + reading
        machine_text = """---
date: 2026-09-03
weekday: 周四
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
        self.assertEqual(daily.market_status, "震荡偏弱")
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
daily_bundle_ref: private-generation
---
""" + reading
        machine_text = """---
date: 2026-09-03
weekday: 周四
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


if __name__ == "__main__":
    unittest.main()
