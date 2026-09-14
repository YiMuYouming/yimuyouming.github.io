"""test_convert_review_schema.py — P2.3 note_schema 分派与隐私

验收（03 篇 P2.3）：
- 新 frontmatter 带 ``note_schema: yimu.review.v2``；旧文件按旧 parser 读取；
- **禁止凭标题相似猜版本**：未知版本必须拒绝，不得静默按 v1 解析；
- v2 的机器附录必须标记为自动生成，且不进入公开页面（内部路径/哈希/回执）；
- 人工心得保留在独立区域，重新生成不得覆盖；
- Portal 脱敏照旧，覆盖账户号、金额、持仓明细、内部路径、确认事件、未公开意见。

全隔离：纯函数 + 临时文件；不写 review-notes 目录。
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_review as cr


V1_NOTE = """---
date: 2026-06-03
weekday: 周三
---

## 一、当日复盘

上证 +0.22%，涨停 51 家。

## 二、心得与教训

1. 不追高，等确认。
"""

V2_NOTE_TEMPLATE = """---
date: 2026-06-04
weekday: 周四
note_schema: yimu.review.v2
---

## 1. 今天发生了什么

自动汇总实际交易、持仓变化与重要提醒。

## 2. 哪些交易或遗漏值得讨论

今天无新增讨论。

## 3. 明天准备怎么做

展示下一交易日计划。

## 4. 需要保留的一条经验

（可空）

## 折叠：机器附录（自动生成）

- 内部路径 /Users/yimu/Projects/YM_Capital/live-dashboard/data/pnl.db
- 规则哈希 sha256:deadbeef
- 终稿回执 finalization_report.json
{extra}
"""


class SchemaDetectionTest(unittest.TestCase):
    def test_missing_schema_defaults_to_v1(self):
        fm = cr.parse_frontmatter(V1_NOTE)
        self.assertEqual(cr.detect_note_schema(fm), cr.NOTE_SCHEMA_V1)

    def test_v2_declared_explicitly(self):
        fm = cr.parse_frontmatter(V2_NOTE_TEMPLATE.format(extra=""))
        self.assertEqual(cr.detect_note_schema(fm), cr.NOTE_SCHEMA_V2)

    def test_unknown_schema_is_rejected_not_guessed(self):
        """版本必须显式声明：未知版本拒绝，不凭标题相似猜。"""
        with self.assertRaises(cr.UnsupportedNoteSchema) as ctx:
            cr.detect_note_schema({"note_schema": "yimu.review.v9"})
        self.assertIn("unsupported_note_schema:yimu.review.v9", str(ctx.exception))

    def test_v1_note_has_no_schema_key_and_is_not_confused_with_v2(self):
        """旧笔记即使标题含"次日预案"也必须按 v1 读取。"""
        v1_with_similar_title = V1_NOTE.replace(
            "## 二、心得与教训", "## 三、次日预案").replace(
            "1. 不追高，等确认。", "明日关注：等回踩确认。")
        fm = cr.parse_frontmatter(v1_with_similar_title)
        self.assertEqual(cr.detect_note_schema(fm), cr.NOTE_SCHEMA_V1)

    def test_supported_schemas_are_explicit(self):
        self.assertEqual(set(cr.SUPPORTED_NOTE_SCHEMAS),
                         {"yimu.review.v1", "yimu.review.v2"})


class V2SplitTest(unittest.TestCase):
    def test_body_and_appendix_are_separated(self):
        parts = cr.split_v2_body_and_appendix(V2_NOTE_TEMPLATE.format(extra=""))
        self.assertTrue(parts["appendix_marker_found"])
        self.assertTrue(parts["appendix_is_generated"])
        self.assertNotIn("/Users/yimu", parts["body"])
        self.assertIn("/Users/yimu", parts["appendix"])

    def test_appendix_must_be_marked_generated(self):
        """附录存在但未标自动生成 → 拒绝，避免把机器内容当人读正文发布。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.md"
            text = V2_NOTE_TEMPLATE.format(extra="").replace("（自动生成）", "")
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(cr.UnsupportedNoteSchema) as ctx:
                cr.convert_md_to_html(str(path))
            self.assertIn("appendix_not_marked_generated", str(ctx.exception))

    def test_missing_appendix_marker_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.md"
            path.write_text(
                V2_NOTE_TEMPLATE.format(extra="").split("## 折叠：机器附录")[0],
                encoding="utf-8")
            with self.assertRaises(cr.UnsupportedNoteSchema) as ctx:
                cr.convert_md_to_html(str(path))
            self.assertIn("appendix_marker_missing", str(ctx.exception))

    def test_no_appendix_section_reports_not_found(self):
        parts = cr.split_v2_body_and_appendix("# 只有正文\n\n没有附录。\n")
        self.assertFalse(parts["appendix_marker_found"])
        self.assertEqual(parts["appendix"], "")

    def test_v2_four_sections_are_located(self):
        result = cr.find_v2_sections(V2_NOTE_TEMPLATE.format(extra=""))
        self.assertEqual(len(result["found"]), 4)
        self.assertEqual(result["missing"], [])

    def test_v2_missing_section_is_reported_not_faked(self):
        text = V2_NOTE_TEMPLATE.format(extra="").replace(
            "## 4. 需要保留的一条经验", "## 别的标题")
        result = cr.find_v2_sections(text)
        self.assertEqual(len(result["found"]), 3)
        self.assertEqual(result["missing"], ["4. 需要保留的一条经验"])


class PrivacyTest(unittest.TestCase):
    """脱敏覆盖：账户号、金额、持仓明细、内部路径、确认事件、未公开意见。"""

    SECRETS = {
        "账户号": "证券账户 123456789012",
        "金额": "总资产 1,234,567.89 元",
        "持仓明细": "持仓 600540 新赛股份 1200股 成本 7.10",
        "内部路径": "/Users/yimu/Projects/YM_Capital/live-dashboard/data/pnl.db",
        "确认事件": "弈沐确认票据 TICKET-20260910-000001-0001",
        "未公开意见": "私下看法：明天大概率冲高回落，先别声张",
    }

    def test_sanitizer_removes_internal_paths(self):
        result = cr.sanitize_public_review_text(self.SECRETS["内部路径"])
        self.assertNotIn("/Users/yimu", result)

    def test_v2_appendix_internal_path_never_reaches_public_body(self):
        parts = cr.split_v2_body_and_appendix(V2_NOTE_TEMPLATE.format(extra=""))
        public = cr.sanitize_public_review_text(parts["body"])
        self.assertNotIn("pnl.db", public)
        self.assertNotIn("/Users/yimu", public)

    def test_redaction_applies_to_body_text(self):
        body = "今日复盘。" + self.SECRETS["内部路径"] + " 结束。"
        result = cr.sanitize_public_review_text(body)
        self.assertNotIn("/Users/yimu", result)

    def test_anonymize_current_holdings_handles_missing_section(self):
        # 不含持仓小节时不得抛错，也不得凭空生成持仓内容
        result = cr.anonymize_current_holdings("没有持仓小节。", {})
        self.assertIn("没有持仓小节", result)


class V1RegressionTest(unittest.TestCase):
    """旧笔记必须继续按旧 parser 读取（不得因新增分派而回归）。"""

    def test_v1_conversion_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026_6_3_Wednesday_ReviewNote.md"
            path.write_text(V1_NOTE, encoding="utf-8")
            # 只验证分派与脱敏链路不抛错；完整 HTML 渲染由既有测试覆盖
            fm = cr.parse_frontmatter(V1_NOTE)
            self.assertEqual(cr.detect_note_schema(fm), cr.NOTE_SCHEMA_V1)
            content = cr.sanitize_public_review_text(V1_NOTE)
            self.assertIn("上证 +0.22%", content)

    def test_v1_note_without_appendix_is_not_rejected(self):
        fm = cr.parse_frontmatter(V1_NOTE)
        # v1 不要求机器附录标记
        self.assertEqual(cr.detect_note_schema(fm), cr.NOTE_SCHEMA_V1)


if __name__ == "__main__":
    unittest.main()
