"""test_build_daily_page.py — W8 S3：每个交易日一张公开页

四项指标来自封存原件（Market_Watch 的 `review_index_fields`），不解析公开稿；
当天有已发布的「每日/」写作就附上，没有就只出事实区（铁律 4：有内容才渲染）。
"""

import json
import tempfile
import unittest
from pathlib import Path

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "build_daily_page", Path(__file__).resolve().parent / "build_daily_page.py"
)
build_daily_page_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_daily_page_module)
INDEX_FIELDS = build_daily_page_module.INDEX_FIELDS
build_daily_page = build_daily_page_module.build_daily_page
main = build_daily_page_module.main
build_parser = build_daily_page_module.build_parser

REPO = Path(__file__).resolve().parents[1]


def _index(**overrides):
    fields = {
        "情绪值": 62,
        "上证涨幅": "+0.34%",
        "涨停家数": 41,
        "最高板": 7,
        "赚钱效应": "一般",
        "整体晋级率": 21.05,
    }
    fields.update(overrides)
    return fields


class IndexFieldsTest(unittest.TestCase):
    def test_only_four_headline_metrics_are_shown(self):
        """每日公开页只出四项，其余字段不进公开页。"""
        self.assertEqual(
            [key for key, _label in INDEX_FIELDS],
            ["情绪值", "上证涨幅", "涨停家数", "最高板"],
        )

    def test_missing_metric_is_dash_not_zero(self):
        page = build_daily_page({}, day="2026-10-08")
        # 缺值一律破折号：不能补 0，也不能让"0%"这种形状出现在指标格里
        self.assertIn("—", page)
        self.assertNotIn("<b>0</b>", page)

    def test_unknown_extra_fields_are_not_leaked(self):
        page = build_daily_page({"内部备注": "不该出现"}, day="2026-10-08")
        self.assertNotIn("内部备注", page)


class RenderTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _render(self, index=None, writing=None):
        return build_daily_page(
            index or _index(),
            day="2026-10-08",
            writing=writing or [],
            out_dir=self.root / "daily",
        )

    def test_page_carries_the_date_and_the_metrics(self):
        page = self._render()
        self.assertIn("2026-10-08", page)
        self.assertIn("62", page)
        self.assertIn("+0.34%", page)
        self.assertIn("41", page)
        self.assertIn("7", page)

    def test_no_writing_means_only_the_fact_section(self):
        page = self._render()
        self.assertIn("每日公开页", page)
        self.assertNotIn("<article>", page)
        self.assertNotIn("即将上线", page)
        self.assertNotIn("敬请期待", page)

    def test_published_writing_attaches_verbatim(self):
        page = self._render(writing=[{
            "path": "每日/2026-10-08.md", "kind": "daily", "date": "2026-10-08",
            "title": "10-08 手记", "series": "", "status": "published",
            "published_at": "2026-10-08", "week": "", "sha256": "0" * 64,
            "body": "# 2026-10-08\n\n今天写了一段。",
        }])
        self.assertIn("今天写了一段。", page)
        self.assertIn("10-08 手记", page)

    def test_render_is_deterministic(self):
        self.assertEqual(self._render(), self._render())


class CliTest(unittest.TestCase):
    def test_dry_run_prints_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = tmp + "/index.json"
            Path(payload).write_text(json.dumps(_index(), ensure_ascii=False), encoding="utf-8")
            code = main(["build", "--day", "2026-10-08", "--index", payload,
                         "--out", tmp + "/daily", "--dry-run"])
            self.assertEqual(code, 0)
            self.assertEqual(list(Path(tmp).glob("daily/*.html")), [])

    def test_build_writes_one_page_per_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = tmp + "/index.json"
            Path(payload).write_text(json.dumps(_index(), ensure_ascii=False), encoding="utf-8")
            out = Path(tmp) / "daily"
            self.assertEqual(main(["build", "--day", "2026-10-08", "--index", payload,
                                   "--out", str(out)]), 0)
            self.assertTrue((out / "2026-10-08.html").is_file())

    def test_check_detects_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = tmp + "/index.json"
            Path(payload).write_text(json.dumps(_index(), ensure_ascii=False), encoding="utf-8")
            out = Path(tmp) / "daily"
            main(["build", "--day", "2026-10-08", "--index", payload, "--out", str(out)])
            self.assertEqual(0, main(["build", "--day", "2026-10-08", "--index", payload,
                                      "--out", str(out), "--check"]))
            payload2 = tmp + "/index2.json"
            Path(payload2).write_text(json.dumps(_index(情绪值=77), ensure_ascii=False), encoding="utf-8")
            self.assertEqual(1, main(["build", "--day", "2026-10-08", "--index", payload2,
                                      "--out", str(out), "--check"]))

    def test_bad_day_format_is_refused(self):
        self.assertEqual(1, main(["build", "--day", "20261008", "--index", "/dev/null",
                                  "--out", "/tmp/x"]))


if __name__ == "__main__":
    unittest.main()
