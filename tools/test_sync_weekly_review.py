import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sync_weekly_review


class WeeklyPublishTest(unittest.TestCase):
    """W8 S7b：只写归档索引，不动首页（首页交给 build_home.py 整页渲染）。"""

    def _site(self, portal: Path):
        reviews = portal / "review-notes"
        reviews.mkdir()
        page = reviews / "weekly-2026-09-21_09-24.html"
        page.write_text(
            '<meta name="weekly-summary" content="周初活跃 · 后半周转弱 · 收益待复核">'
            '<h1>W39 周复盘</h1>'
            '<span>周度收益</span><strong>-1.80%</strong>'
            '<span>交易日</span><strong>4天</strong>'
            '<span>周末仓位</span><strong>约47%</strong>',
            encoding="utf-8",
        )
        home = portal / "index.html"
        home.write_text(
            '<div class="archive-item"><span>周报归档</span><strong>0</strong><em>篇</em></div>'
            '<div class="review-stat"><span>周报归档</span><strong>0</strong><em>篇</em></div>'
            '<a class="workspace-card" id="workspace-weekly-review" '
            'href="review-notes/weekly-2026-09-14_09-18.html">周度复盘</a>'
            '<div class="recent-review-grid">'
            '<a id="recent-review-0924" href="review-notes/2026-09-24.html?from=recent-review-0924" '
            'class="recent-review-card">日复盘</a></div>',
            encoding="utf-8",
        )
        (reviews / "index.html").write_text(
            '<span><strong>0</strong> 份周度总结</span>'
            '<div class="weekly-grid">\n</div>\n\n<!-- ===== 月 -->',
            encoding="utf-8",
        )
        return page, home

    def test_updates_archive_only_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            portal = Path(tmp)
            page, home = self._site(portal)
            reviews = portal / "review-notes"
            home_before = home.read_bytes()
            with patch.object(sync_weekly_review, "PORTAL", portal), \
                 patch.object(sync_weekly_review, "REVIEW_NOTES", reviews):
                sync_weekly_review.sync_weekly(page)
                first_archive = (reviews / "index.html").read_text(encoding="utf-8")
                sync_weekly_review.sync_weekly(page)
                second_archive = (reviews / "index.html").read_text(encoding="utf-8")

            self.assertEqual(first_archive, second_archive, "重复发布必须幂等")
            self.assertIn('<strong>1</strong> 份周度总结', first_archive)
            self.assertIn('第39周 · 4天', first_archive)
            self.assertIn('周初活跃 · 后半周转弱 · 收益待复核', first_archive)
            self.assertIn('href="weekly-2026-09-21_09-24.html"', first_archive)
            # S7b 的硬约束：首页一个字节都不许动
            self.assertEqual(home_before, home.read_bytes(), "sync_weekly 不许再改 index.html")

    def test_wrong_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            portal = Path(tmp)
            self._site(portal)
            stray = portal / "weekly-2026-09-21_09-24.html"
            stray.write_text("<h1>W39</h1>", encoding="utf-8")
            with patch.object(sync_weekly_review, "PORTAL", portal), \
                 patch.object(sync_weekly_review, "REVIEW_NOTES", portal / "review-notes"):
                with self.assertRaises(ValueError):
                    sync_weekly_review.sync_weekly(stray)


if __name__ == "__main__":
    unittest.main()
