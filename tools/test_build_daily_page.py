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
        page = build_daily_page({}, day="2026-10-08", data_date="2026-10-08")
        # 缺值一律破折号：不能补 0，也不能让"0%"这种形状出现在指标格里
        self.assertIn("—", page)
        self.assertNotIn("<b>0</b>", page)

    def test_unknown_extra_fields_are_not_leaked(self):
        page = build_daily_page({"内部备注": "不该出现"}, day="2026-10-08", data_date="2026-10-08")
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
            data_date="2026-10-08",
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
            code = main(["build", "--day", "2026-10-08", "--index", payload, "--data-date", "2026-10-08",
                         "--out", tmp + "/daily", "--dry-run"])
            self.assertEqual(code, 0)
            self.assertEqual(list(Path(tmp).glob("daily/*.html")), [])

    def test_build_writes_one_page_per_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = tmp + "/index.json"
            Path(payload).write_text(json.dumps(_index(), ensure_ascii=False), encoding="utf-8")
            out = Path(tmp) / "daily"
            self.assertEqual(main(["build", "--day", "2026-10-08", "--index", payload, "--data-date", "2026-10-08",
                                   "--out", str(out)]), 0)
            self.assertTrue((out / "2026-10-08.html").is_file())

    def test_check_detects_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = tmp + "/index.json"
            Path(payload).write_text(json.dumps(_index(), ensure_ascii=False), encoding="utf-8")
            out = Path(tmp) / "daily"
            main(["build", "--day", "2026-10-08", "--index", payload, "--data-date", "2026-10-08", "--out", str(out)])
            self.assertEqual(0, main(["build", "--day", "2026-10-08", "--index", payload, "--data-date", "2026-10-08",
                                      "--out", str(out), "--check"]))
            payload2 = tmp + "/index2.json"
            Path(payload2).write_text(json.dumps(_index(情绪值=77), ensure_ascii=False), encoding="utf-8")
            self.assertEqual(1, main(["build", "--day", "2026-10-08", "--index", payload2, "--data-date", "2026-10-08",
                                      "--out", str(out), "--check"]))

    def test_bad_day_format_is_refused(self):
        self.assertEqual(1, main(["build", "--day", "20261008", "--index", "/dev/null", "--data-date", "2026-10-08",
                                  "--out", "/tmp/x"]))


if __name__ == "__main__":
    unittest.main()


class DataDateGuardTests(unittest.TestCase):
    """审计回复 3 第三节第 1 条：页面日期和指标日期不一致就不出页。

    根因在源头：`review_index_fields()` 只回 MARKET_INDEX_FIELDS 里的键，
    而 `date` 不在其中，所以指标 JSON 本身不自带日期——页面写哪天和
    指标是哪天的可以悄悄对不上。门户这一层必须显式收口。
    """

    def test_mismatched_data_date_is_refused(self):
        with self.assertRaises(ValueError) as ctx:
            build_daily_page(_index(), day="2026-10-08", data_date="2026-09-30")
        self.assertIn("data_date_mismatch", str(ctx.exception))

    def test_matching_data_date_renders(self):
        page = build_daily_page(_index(), day="2026-10-08", data_date="2026-10-08")
        self.assertIn("2026-10-08", page)

    def test_missing_data_date_is_refused_unless_sample(self):
        with self.assertRaises(ValueError) as ctx:
            build_daily_page(_index(), day="2026-10-08")
        self.assertIn("data_date_required", str(ctx.exception))

    def test_sample_mode_marks_the_page_and_keeps_going(self):
        """预演数据照样出页，但页面上必须带「示例」徽标，不能让人误读成真数据。"""
        page = build_daily_page(
            _index(), day="2026-10-08", data_date="2026-09-30", sample=True
        )
        self.assertIn("示例", page)
        self.assertIn("预演数据", page)
        self.assertIn("2026-09-30", page)   # 数据日期如实标出来

    def test_no_sample_badge_when_dates_agree(self):
        page = build_daily_page(_index(), day="2026-10-08", data_date="2026-10-08")
        self.assertNotIn("data-sample", page)


class MarkdownRenderTests(unittest.TestCase):
    """审计回复 3 第三节第 2 条：写作正文的 Markdown 没渲染，正文首行标题还重复一次。"""

    def _render(self, md):
        return build_daily_page_module._markdown_to_html(md)

    def test_bold_and_italic_and_inline_code(self):
        out = self._render("先写下**当时的理由**，再看 *事后* 的 `KPI`。")
        self.assertIn("<strong>当时的理由</strong>", out)
        self.assertIn("<em>事后</em>", out)
        self.assertIn("<code>KPI</code>", out)
        self.assertNotIn("**", out)

    def test_escapes_html_in_body(self):
        out = self._render("a < b & c > d")
        self.assertNotIn("<b>", out)
        self.assertIn("&lt;", out)
        self.assertIn("&amp;", out)

    def test_leading_h1_matching_title_is_dropped(self):
        writing = [{
            "title": "9 月 30 日手记",
            "date": "2026-10-08",
            "status": "published",
            "path": "每日/2026-10-08.md",
            "body": "<h1>9 月 30 日手记</h1><p>正文</p>",
        }]
        page = build_daily_page(
            _index(), day="2026-10-08", data_date="2026-10-08", writing=writing
        )
        self.assertEqual(page.count("9 月 30 日手记"), 1)

    def test_non_matching_h1_is_kept(self):
        writing = [{
            "title": "9 月 30 日手记",
            "date": "2026-10-08",
            "status": "published",
            "path": "每日/2026-10-08.md",
            "body": "<h1>另一篇的标题</h1><p>正文</p>",
        }]
        page = build_daily_page(
            _index(), day="2026-10-08", data_date="2026-10-08", writing=writing
        )
        self.assertIn("另一篇的标题", page)


class CliDataDateTests(unittest.TestCase):
    def test_cli_requires_data_date(self):
        args = build_parser().parse_args(["build", "--day", "2026-10-08", "--index", "x.json"])
        self.assertFalse(args.sample)
        self.assertIsNone(getattr(args, "data_date", None))

    def test_cli_accepts_sample_flag(self):
        args = build_parser().parse_args(
            ["build", "--day", "2026-10-08", "--index", "x.json", "--sample"]
        )
        self.assertTrue(args.sample)

    def test_leading_h1_matching_the_page_date_is_dropped(self):
        """正文常以 `# 日期` 起头，而页首已经写过一次这个日期——这才是真正重复的那一对。"""
        import re as _re
        writing = [{
            "title": "10-08 手记",
            "date": "2026-10-08",
            "status": "published",
            "path": "每日/2026-10-08.md",
            "body": "<h1>2026-10-08</h1><p>正文</p>",
        }]
        page = build_daily_page(
            _index(), day="2026-10-08", data_date="2026-10-08", writing=writing
        )
        self.assertEqual(_re.findall(r"<h1>(.*?)</h1>", page), ["2026-10-08"],
                         "正文开头那个重复的 H1 应当被去掉，页首留一个")


class MetricPrecisionTests(unittest.TestCase):
    """情绪值在封存原件里是四位小数（47.6164），直接印在公开页上像没写完。"""

    def test_emotion_is_shown_with_one_decimal(self):
        page = build_daily_page(_index(情绪值=47.6164), day="2026-10-08", data_date="2026-10-08")
        self.assertIn("47.6", page)
        self.assertNotIn("47.6164", page)

    def test_counts_stay_integers(self):
        page = build_daily_page(_index(涨停家数=52, 最高板=7), day="2026-10-08", data_date="2026-10-08")
        self.assertIn(">52<", page)
        self.assertIn(">7<", page)

    def test_string_metrics_are_untouched(self):
        page = build_daily_page(_index(上证涨幅="+0.31%"), day="2026-10-08", data_date="2026-10-08")
        self.assertIn("+0.31%", page)
