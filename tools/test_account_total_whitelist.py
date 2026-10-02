"""周报事实区：账户层面总额的白名单只开给带标记的元素（审计回复 8 第二节第 8 条）。

账户总额（当前资产、累计入金）本来就是公开口径——现网首页一直在公开，
弈沐看过的预览里也有。真正要拦的是正文里的个股金额和股数。

所以白名单不给"页面上的一切金额"，只给一个**固定标记**：
``data-public="account-total"``。带这个标记的元素跳过，其余任何地方的千分位
金额照拦不误。
"""

import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "portal_check", REPO / "tools" / "portal_check.py"
)
portal_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(portal_check)


class AccountTotalWhitelistTests(unittest.TestCase):
    def _hits(self, html: str) -> list[tuple[str, ...]]:
        text, _positions = portal_check._strip_tags_for_redline(html)
        return portal_check._scan_redline_hits(text, set(), set())

    def test_marked_account_total_is_allowed_through(self):
        """带 data-public="account-total" 的元素，金额不拦。"""
        html = (
            '<div class="kpis">'
            '<div class="kpi"><span class="lbl">当前资产</span>'
            '<b data-public="account-total">623,807.97</b></div>'
            '<div class="kpi"><span class="lbl">累计入金</span>'
            '<b data-public="account-total">711,059.23</b></div>'
            "</div>"
        )
        self.assertEqual([], self._hits(html))

    def test_the_same_number_in_body_text_is_still_blocked(self):
        """同样的数字出现在正文里，照拦不误——白名单只开给那个标记。"""
        html = (
            '<div class="kpis">'
            '<b data-public="account-total">623,807.97</b></div>'
            "<p>9 月 30 日收盘时账户总额是 623,807.97 元。</p>"
        )
        hits = self._hits(html)
        self.assertTrue(hits, "正文里的千分位金额必须被拦下")
        self.assertTrue(any("千分位金额" in str(hit) for hit in hits))

    def test_unmarked_kpi_amount_is_still_blocked(self):
        """没有标记的 KPI 金额一样拦——不给「看起来像 KPI 就放过」。"""
        hits = self._hits('<div class="kpi"><b>623,807.97</b></div>')
        self.assertTrue(hits)

    def test_marker_is_only_emitted_by_the_fact_area_generators(self):
        """防走私：标记只允许出现在事实区的生成器里，不许内容路径随手加。"""
        allowed = {
            # 生成器与扫描器本身当然要提到这个标记——它们是定义方，不是消费方。
            "tools/portal_check.py",
            "tools/build_weekly_page.py",
            "tools/build_home.py",
            "templates/home.html",
            "tools/test_portal_check_redline.py",
            "tools/test_redline_scope.py",
            "tools/test_account_total_whitelist.py",
        }
        offenders = []
        for path in sorted(REPO.rglob("*")):
            if not path.is_file() or path.suffix not in {".py", ".html"}:
                continue
            rel = path.relative_to(REPO).as_posix()
            if rel.startswith(("output/", "v1/", "review-notes/", "daily-notes/", "out/")):
                continue
            if rel in allowed:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            if "account-total" in text:
                offenders.append(rel)
        self.assertEqual([], offenders, "account-total 标记出现在不该出现的地方")


class WeeklyKpiMarkerTests(unittest.TestCase):
    def test_weekly_kpi_marks_only_the_account_totals(self):
        spec = importlib.util.spec_from_file_location(
            "build_weekly_page", REPO / "tools" / "build_weekly_page.py"
        )
        weekly = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(weekly)
        days = [{"date": "2026-09-30", "index": {"情绪值": 47.6}}]
        pnl = {"summary": {"pnl_pct": -1.79, "last_date": "2026-09-30"},
               "meta": {"total_asset": 623807.97, "total_deposit": 711059.225}}
        html = weekly.fact_section(days, pnl)
        self.assertEqual(2, html.count('data-public="account-total"'))
        self.assertIn('data-public="account-total">623,807.97<', html)
        # 金额本身照旧是两位小数，不因为带标记就放松
        self.assertIn("711,059.23", html)


if __name__ == "__main__":
    unittest.main()