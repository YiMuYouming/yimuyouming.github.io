import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_review
import promotion_metrics_shadow


FIXTURE = Path(__file__).resolve().parents[2] / "shared" / "research" / "workflow-v2-2026-09-24" / "implementation-evidence" / "P4-consumer-fixture.json"


class PromotionMetricsShadowTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "promotion.json"

    def render(self):
        self.path.write_text(json.dumps(self.payload, ensure_ascii=False), encoding="utf-8")
        return promotion_metrics_shadow.render(self.path, "2026-06-25")

    def test_partial_is_labeled_without_public_numeric_or_private_fields(self):
        self.payload["secret_path"] = "/private/account/123456"
        html = self.render()
        self.assertIn("来源待补齐", html)
        self.assertIn("影子数据", html)
        self.assertNotIn("50%", html)
        self.assertNotIn("/private/", html)
        self.assertNotIn("synthetic_fixture", html)

    def test_ready_shows_only_three_tier_comparisons(self):
        self.payload["status"] = "ready"
        self.payload["secret_path"] = "/private/account/123456"
        html = self.render()
        self.assertIn("50%（1/2）", html)
        self.assertIn("100%（1/1）", html)
        self.assertIn("不可用", html)
        self.assertNotIn("overall_candidates", html)
        self.assertNotIn("/private/", html)

    def test_wrong_schema_date_or_authority_fails_closed(self):
        for key, value in (("schema_version", "unexpected"), ("trade_date", "2026-06-24"), ("authority", {"mode": "active", "active": True})):
            with self.subTest(key=key):
                original = self.payload[key]
                self.payload[key] = value
                with self.assertRaises(ValueError):
                    self.render()
                self.payload[key] = original

    def test_converter_accepts_explicit_shadow_input(self):
        self.path.write_text(json.dumps(self.payload, ensure_ascii=False), encoding="utf-8")
        note = Path(self.temp.name) / "2026_6_25_ReviewNote.md"
        note.write_text("---\ndate: 2026-06-25\nweekday: 周四\n---\n## 一、当日复盘\n### 一句话结论\n观察。\n", encoding="utf-8")
        with patch.object(convert_review, "REVIEW_NOTES", Path(self.temp.name)):
            _, output = convert_review.convert_md_to_html(note, promotion_metrics_shadow_path=self.path)
        html = output.read_text(encoding="utf-8")
        self.assertIn("逐股晋级率对照", html)
        self.assertIn("来源待补齐", html)


if __name__ == "__main__":
    unittest.main()
