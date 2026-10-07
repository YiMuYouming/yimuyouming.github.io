"""指标 JSON 自带日期，门户必须拿它跟页面日期比对（审计回复 37 · 第三节）。

**为什么现有的 ``data_date_mismatch`` 是同义反复**：
``sync_portal.py:374`` 调出页时传的是 ``--data-date target_day``，
而 ``build_daily_page`` 校验的是 ``data_date != day`` ——
两个值来自同一个变量，**永远相等**。于是
「拿 9-30 的指标出 10-08 的页」这种情况**照常出页**。

2ee0e7a 原本要防的正是这个。MW 侧已在 v6 路径输出
``date = review_facts.trading_date``（``7fdd120``），但**门户一次都没读它**。
本测试钉住第二道防线：**指标自己报它是谁的日期**，门户拿它跟页��日期比。

判据：
1. ``index`` 里有 ``date`` 且与 ``day`` 不一致 → 拒绝（``index_date_mismatch``）；
2. 一致 → 放行；
3. **没有** ``date`` → 维持现状，**不新增阻断**
   （v5 路径的指标JSON 不带日期，堵死它等于把 v5 全部页面打死）；
4. ``date`` 格式非法 → 当作没有（不新增阻断），但要在页面上留痕；
5. ``sample=True`` 与``day<PHASE2_START`` 的既有豁免不受影响。
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

PORTAL_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PORTAL_ROOT / "tools" / "build_daily_page.py"


def _module():
    spec = importlib.util.spec_from_file_location("iso_build_daily_page", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["iso_build_daily_page"] = module
    spec.loader.exec_module(module)
    return module


class IndexDateGuardTest(unittest.TestCase):
    """``index["date"]`` 与 ``day`` 不一致 → 拒绝出页。"""

    @classmethod
    def setUpClass(cls):
        if not MODULE_PATH.is_file():
            raise unittest.SkipTest(f"找不到 build_daily_page.py: {MODULE_PATH}")
        cls.mod = _module()

    def _build(self, index: dict, day: str = "2026-10-08", **kw):
        return self.mod.build_daily_page(index, day=day, **kw)

    def test_index_date_mismatch_is_rejected(self):
        """9-30 的指标不许出10-08 的页。"""
        with self.assertRaises(ValueError) as ctx:
            self._build({"date": "2026-09-30", "涨停家数": 52}, day="2026-10-08",
                        data_date="2026-10-08")
        self.assertIn("index_date_mismatch", str(ctx.exception))

    def test_index_date_equal_is_allowed(self):
        """日期一致 → 正常出页。"""
        html = self._build({"date": "2026-10-08", "涨停家数": 52}, day="2026-10-08",
                           data_date="2026-10-08")
        self.assertIn("2026-10-08", html)

    def test_index_without_date_still_publishes(self):
        """**没有** date → 维持现状，不新增阻断（v5 路径的指标 JSON 不带日期）。"""
        html = self._build({"涨停家数": 52}, day="2026-10-08", data_date="2026-10-08")
        self.assertIn("2026-10-08", html)

    def test_index_date_invalid_format_does_not_block(self):
        """date 格式非法 → 不当作不一致，也不新增阻断（沿用现状）。"""
        html = self._build({"date": "不是日期", "涨停家数": 52}, day="2026-10-08",
                           data_date="2026-10-08")
        self.assertIn("2026-10-08", html)

    def test_mismatch_is_rejected_even_when_data_date_matches_day(self):
        """核心回归：``data_date`` 与 ``day`` 相等（现有校验通过）也必须被拒。

        这条是整件事的意义所在 —— 同义反复的校验就是从这条缝里漏出去的。
        """
        with self.assertRaises(ValueError) as ctx:
            self._build({"date": "2026-09-30"}, day="2026-10-08", data_date="2026-10-08")
        self.assertIn("index_date_mismatch", str(ctx.exception))

    def test_sample_page_exempt_from_index_date_check(self):
        """``sample=True`` 仍豁免（示例页用预演数据，不该被真实指标日期拦住）。"""
        html = self._build({"date": "2026-09-30"}, day="2026-10-08", sample=True)
        self.assertIn("2026-10-08", html)


if __name__ == "__main__":
    unittest.main()