#!/usr/bin/env python3
"""Regression checks for the portal PnL KPI contract."""

from pathlib import Path
import re
import unittest


PORTAL = Path(__file__).resolve().parent.parent
INDEX_HTML = PORTAL / "index.html"


class PortalPnlKpiTests(unittest.TestCase):
    def setUp(self):
        self.html = INDEX_HTML.read_text(encoding="utf-8")

    def test_secondary_kpis_have_live_dashboard_dynamic_labels(self):
        for text in [
            "id=\"pnl_pnl_label\"",
            "id=\"pnl_pos_label\"",
            "id=\"pnl_today_alpha_label\"",
            "今日收益",
            "今日仓位",
            "今日 TWR",
            "今日相对指数",
            "今日回撤",
        ]:
            with self.subTest(text=text):
                self.assertIn(text, self.html)

    def test_kpis_follow_selected_period_and_average_position(self):
        update_kpis = re.search(
            r"function updateKPIs\(\) \{(?P<body>.*?)\n  function setKPI",
            self.html,
            flags=re.S,
        )
        self.assertIsNotNone(update_kpis)
        body = update_kpis.group("body")
        self.assertIn("periodText + '收益'", body)
        self.assertIn("periodText + ' TWR'", body)
        self.assertIn("periodText + ' 相对指数'", body)
        self.assertIn("periodText + ' 回撤'", body)
        self.assertIn("periodText + '平均仓位'", body)
        self.assertIn("validPos.length + ' 个采样'", body)


if __name__ == "__main__":
    unittest.main()
