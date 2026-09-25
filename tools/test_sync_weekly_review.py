import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import convert_review
import sync_weekly_review


class WeeklyPublishTest(unittest.TestCase):
    def test_updates_both_indexes_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            portal = Path(tmp)
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
            (portal / "index.html").write_text(
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
            with patch.object(sync_weekly_review, "PORTAL", portal), \
                 patch.object(sync_weekly_review, "REVIEW_NOTES", reviews), \
                 patch.object(convert_review, "REVIEW_NOTES", reviews):
                sync_weekly_review.sync_weekly(page)
                first_home = (portal / "index.html").read_text(encoding="utf-8")
                first_archive = (reviews / "index.html").read_text(encoding="utf-8")
                sync_weekly_review.sync_weekly(page)
                self.assertEqual(first_home, (portal / "index.html").read_text(encoding="utf-8"))
                self.assertEqual(first_archive, (reviews / "index.html").read_text(encoding="utf-8"))

            self.assertIn('href="review-notes/weekly-2026-09-21_09-24.html"', first_home)
            self.assertIn('id="recent-review-weekly-20260921-20260924"', first_home)
            self.assertIn('<em>收益参考</em><strong>-1.80%</strong>', first_home)
            self.assertEqual(first_home.count('周报归档</span><strong>1</strong>'), 2)
            self.assertIn('<strong>1</strong> 份周度总结', first_archive)
            self.assertIn('第39周 · 4天', first_archive)
            self.assertIn('周初活跃 · 后半周转弱 · 收益待复核', first_archive)


if __name__ == "__main__":
    unittest.main()
