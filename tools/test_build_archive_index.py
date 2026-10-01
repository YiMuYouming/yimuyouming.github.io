"""test_build_archive_index.py — W8 S3：第一阶段归档入口页

归档入口页按周列出（"第一阶段 · 2026-03-23 至 09-30"），不逐页平铺——
234 个页面平铺出来没人会看。首页的手记和复盘列表只显示 10 月以后的。
"""

import importlib.util
import tempfile
import unittest
from datetime import date
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "build_archive_index", Path(__file__).resolve().parent / "build_archive_index.py"
)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

PHASE1_START = date(2026, 3, 23)
PHASE1_END = date(2026, 9, 30)


def _pages(root, dates):
    for day in dates:
        (root / f"{day}.html").write_text("<html></html>", encoding="utf-8")


class WeekGroupingTest(unittest.TestCase):
    def test_iso_week_label(self):
        self.assertEqual(mod.week_label(date(2026, 3, 23)), "2026-W13")
        self.assertEqual(mod.week_label(date(2026, 9, 30)), "2026-W40")

    def test_pages_group_by_week_not_flat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _pages(root, ["2026-03-23", "2026-03-24", "2026-03-25",
                          "2026-04-07", "2026-04-08"])
            groups = mod.group_by_week(sorted(root.glob("*.html")))
            self.assertEqual([g["label"] for g in groups], ["2026-W13", "2026-W15"])
            self.assertEqual(groups[0]["count"], 3)
            self.assertEqual(groups[1]["count"], 2)

    def test_phase1_pages_are_inside_the_frozen_window(self):
        self.assertTrue(mod.in_phase1("2026-03-23"))
        self.assertTrue(mod.in_phase1("2026-09-30"))
        self.assertFalse(mod.in_phase1("2026-10-01"), "10 月起的页面不属第一阶段")
        self.assertFalse(mod.in_phase1("2026-03-22"))


class RenderTest(unittest.TestCase):
    def test_header_states_the_frozen_window(self):
        html = mod.render([])
        self.assertIn("第一阶段", html)
        self.assertIn("2026-03-23", html)
        self.assertIn("2026-09-30", html)

    def test_empty_archive_still_renders_without_placeholder_text(self):
        html = mod.render([])
        self.assertNotIn("即将上线", html)
        self.assertNotIn("敬请期待", html)

    def test_each_week_row_links_its_pages(self):
        groups = [{"label": "2026-W40", "count": 2,
                   "pages": [("2026-09-29", "09-29 复盘", "review-notes/2026-09-29.html"),
                             ("2026-09-30", "09-30 复盘", "review-notes/2026-09-30.html")]}]
        html = mod.render(groups)
        self.assertIn("2026-09-29.html", html)
        self.assertIn("2026-09-30.html", html)
        self.assertIn("2026-W40", html)

    def test_no_page_is_duplicated(self):
        groups = [{"label": "2026-W40", "count": 2,
                   "pages": [("2026-09-29", "a", "review-notes/2026-09-29.html"),
                             ("2026-09-30", "b", "review-notes/2026-09-30.html")]}]
        html = mod.render(groups)
        self.assertEqual(html.count("2026-09-29.html"), 1)


if __name__ == "__main__":
    unittest.main()
