#!/usr/bin/env python3
"""Regression checks for the portal PnL KPI contract."""

from pathlib import Path
import re
import unittest


PORTAL = Path(__file__).resolve().parent.parent
# W8 S7a 起首页不再内联业绩引擎，改为 <script src="static/pnl-engine.js">。
# 这组用例守的是**引擎那份唯一实现**（审计回复 1 第一节：业绩只算一处），
# 所以直接读引擎文件，不再从首页 HTML 里抠出来。
ENGINE_JS = PORTAL / "static" / "pnl-engine.js"
INDEX_HTML = PORTAL / "index.html"


class PortalPnlKpiTests(unittest.TestCase):
    def setUp(self):
        # 模板给的是 DOM id，引擎给的是动态标签文案——两个来源分别读。
        self.html = INDEX_HTML.read_text(encoding="utf-8")
        self.engine = ENGINE_JS.read_text(encoding="utf-8")

    def test_secondary_kpis_have_live_dashboard_dynamic_labels(self):
        for text in [
            "id=\"pnl_pnl_label\"",
            "id=\"pnl_pos_label\"",
            "id=\"pnl_today_alpha_label\"",
            "账户收益",
            "期末仓位",
            "周期累计",
            "超额",
            "回撤",
        ]:
            with self.subTest(text=text):
                self.assertIn(text, self.html)

    def test_kpis_follow_selected_period_and_average_position(self):
        update_kpis = re.search(
            r"function updateKPIs\(\) \{(?P<body>.*?)\n  function setKPI",
            self.engine,
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
