"""test_build_weekly_page.py — W8 S4：周报公开页骨架

事实区（hero、KPI、每日脉络、市场表）从数据取：PnL 接口 + review_index_fields，
**不解析周报 Markdown 的表格**（铁律 1）。叙述区看 `公开写作/` 里有没有
`kind: weekly`、`week` 对得上的已发布文件，没有就只出事实区。
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "build_weekly_page", Path(__file__).resolve().parent / "build_weekly_page.py"
)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

DAYS = [
    {"date": "2026-09-28", "index": {"情绪值": 55, "上证涨幅": "+0.31%", "涨停家数": 40, "最高板": 6}},
    {"date": "2026-09-29", "index": {"情绪值": 62, "上证涨幅": "-0.12%", "涨停家数": 45, "最高板": 7}},
    {"date": "2026-09-30", "index": {"情绪值": 48, "上证涨幅": "+0.34%", "涨停家数": 41, "最高板": 7}},
]

PNL = {"summary": {"last_date": "2026-09-30", "daily_count": 119, "pnl_pct": -0.28},
       "meta": {"total_asset": 623807.97, "total_deposit": 711059.23}}


def _writing():
    return [{
        "path": "周记/W40.md", "kind": "weekly", "week": "W40", "status": "published",
        "title": "第 40 周：退潮期的三次误判", "series": "", "published_at": "2026-10-01",
        "sha256": "0" * 64, "body": "<p>这一周写了一段。</p>",
    }]


class WeekMathTest(unittest.TestCase):
    def test_iso_week_label_round_trip(self):
        self.assertEqual(mod.week_label(2026, 40), "2026-W40")
        self.assertEqual(mod.parse_week("2026-W40"), (2026, 40))

    def test_days_of_the_week(self):
        days = mod.days_of_week(2026, 40)
        self.assertEqual([day["date"] for day in days],
                         ["2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01",
                          "2026-10-02", "2026-10-03", "2026-10-04"])

    def test_parse_week_rejects_junk(self):
        for junk in ("W40", "2026W40", "2026-40"):
            with self.assertRaises(ValueError):
                mod.parse_week(junk)


class FactSectionTest(unittest.TestCase):
    def test_facts_come_from_the_data_not_from_markdown(self):
        section = mod.fact_section(DAYS, PNL)
        for day in DAYS:
            self.assertIn(day["date"], section)
            self.assertIn(str(day["index"]["涨停家数"]), section)
        self.assertIn("623,807.97", section)

    def test_day_without_index_is_omitted_not_zeroed(self):
        partial = [DAYS[0], {"date": "2026-09-29", "index": {}}]
        section = mod.fact_section(partial, PNL)
        self.assertIn("2026-09-28", section)
        self.assertNotIn("<b>0</b>", section)

    def test_narrative_comes_from_weekly_writing_only(self):
        html = mod.render(DAYS, PNL, writing=_writing(), week="2026-W40")
        self.assertIn("这一周写了一段。", html)

    def test_writing_from_another_week_is_not_attached(self):
        other = [dict(_writing()[0], week="W39")]
        html = mod.render(DAYS, PNL, writing=other, week="2026-W40")
        self.assertNotIn("这一周写了一段。", html)


class RenderTest(unittest.TestCase):
    def test_render_is_deterministic(self):
        self.assertEqual(mod.render(DAYS, PNL, writing=[], week="2026-W40"),
                         mod.render(DAYS, PNL, writing=[], week="2026-W40"))

    def test_no_narrative_means_fact_section_only(self):
        html = mod.render(DAYS, PNL, writing=[], week="2026-W40")
        self.assertIn("2026-09-28", html)
        self.assertNotIn("这一周写了一段。", html)
        self.assertNotIn("即将上线", html)
        self.assertNotIn("敬请期待", html)

    def test_skeleton_states_that_numbers_are_machine_generated(self):
        html = mod.render(DAYS, PNL, writing=[], week="2026-W40")
        self.assertIn("数据", html)
        self.assertNotIn("占位", html)


class CliTest(unittest.TestCase):
    def _files(self, tmp):
        index = Path(tmp) / "index.json"
        index.write_text(json.dumps(
            {"schema": "weekly_index.v1", "days": DAYS, "pnl": PNL}, ensure_ascii=False),
            encoding="utf-8")
        return index

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = self._files(tmp)
            out = Path(tmp) / "weekly"
            code = mod.main(["build", "--week", "2026-W40", "--index", str(index),
                             "--out", str(out), "--dry-run"])
            self.assertEqual(code, 0)
            self.assertEqual(list(out.glob("*.html")), [])

    def test_build_writes_one_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = self._files(tmp)
            out = Path(tmp) / "weekly"
            self.assertEqual(0, mod.main(["build", "--week", "2026-W40",
                                          "--index", str(index), "--out", str(out)]))
            self.assertTrue((out / "2026-W40.html").is_file())

    def test_bad_week_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = self._files(tmp)
            self.assertEqual(1, mod.main(["build", "--week", "40", "--index", str(index),
                                          "--out", tmp]))


if __name__ == "__main__":
    unittest.main()
