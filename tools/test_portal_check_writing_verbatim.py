"""D-12：个股名称/代码的红线豁免只限 writing-body verbatim 区。

2026-10-26 事故：本人长文 `essays/2026-10-25.html`（`writing-body
data-public-writing="verbatim"` 区）里出现「楚天龙」「紫光股份」等个股名，
发布门禁把整篇长文拦住。四类静态模式（机器话/金额股数/对话体/脱敏残渣）
一直走 `_covered` 豁免，只有个股名称、个股代码两个循环漏了这一步。

这里锁两向行为：
  ① verbatim 写作区内 → 个股名/代码放行（不报）；
  ② 同一份文本里放到 verbatim 区之外（首页、每日页、业绩/统计区、嵌套边界外）
     → 照常报（不得整体放宽）；非 verbatim 的 writing-body 也不豁免；
     其它三类模式口径不变。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import portal_check


NAMES = ["楚天龙", "紫光股份"]
CODES = ["003040", "000938"]

VERBATIM_OPEN = '<div class="writing-body" data-public-writing="verbatim">'


def _check(html: str, names=None, codes=None):
    text = portal_check._strip_tags_for_redline(html)[0]
    return portal_check.check_redlines(
        text, NAMES if names is None else names, CODES if codes is None else codes
    )


def _labels(hits):
    return [h.split(":")[0] for h in hits]


class VerbatimWritingExemptionTests(unittest.TestCase):
    """① verbatim 写作区里的个股名/代码必须放行。"""

    def test_stock_name_inside_verbatim_passes(self):
        html = (
            VERBATIM_OPEN
            + "<p>楚天龙那笔，9 月初买进去本想做个短差。</p></div>"
        )
        self.assertEqual([], _check(html), "verbatim 写作区内的个股名不该被拦（D-12）")

    def test_stock_code_inside_verbatim_passes(self):
        html = VERBATIM_OPEN + "<p>003040 那天冲得比我的预期更急。</p></div>"
        self.assertEqual([], _check(html), "verbatim 写作区内的个股代码不该被拦（D-12）")

    def test_both_name_and_code_and_nested_divs_inside_verbatim_pass(self):
        html = (
            VERBATIM_OPEN
            + '<div class="para"><p>紫光股份 000938 第二天卖掉，'
            "赚了一点。</p></div><p>楚天龙 003040 也提过。</p></div>"
        )
        self.assertEqual([], _check(html), "嵌套 div 的 verbatim 写作区仍应整段豁免")

    def test_other_static_patterns_stay_exempt_inside_verbatim(self):
        # 已有的四类豁免口径不变：写作区里出现机器话照样放行。
        html = VERBATIM_OPEN + "<p>按 WIN-ICE-W1-001 关闭，红方也同意。</p></div>"
        self.assertEqual([], _check(html))


class VerbatimExemptionIsNarrowTests(unittest.TestCase):
    """② verbatim 区之外一律照拦，豁免不得外溢。"""

    def test_stock_name_outside_verbatim_still_blocked(self):
        html = VERBATIM_OPEN + "<p>今天只做了减仓。</p></div>" + "<p>楚天龙 清仓</p>"
        hits = _check(html)
        self.assertTrue(hits, "verbatim 区之外的个股名必须照拦")
        self.assertIn("个股名称", _labels(hits))

    def test_stock_code_outside_verbatim_still_blocked(self):
        html = VERBATIM_OPEN + "<p>今天只做了减仓。</p></div>" + "<p>今日卖出 000938</p>"
        hits = _check(html)
        self.assertTrue(hits, "verbatim 区之外的个股代码必须照拦")
        self.assertIn("个股代码", _labels(hits))

    def test_homepage_stats_area_with_name_is_blocked(self):
        # 首页形状：业绩/统计区没有任何 verbatim 标记 → 个股名照拦。
        html = (
            "<section id=\"pnl\"><div class=\"kpi\"><b>TWR</b><span>+1.2%</span></div>"
            "<div class=\"recent\"><p>紫光股份 走强</p></div></section>"
        )
        self.assertIn("个股名称", _labels(_check(html)))

    def test_daily_page_facts_area_with_name_is_blocked(self):
        # 每日公开页形状：指标区 + 说明区，非 verbatim → 个股名/代码照拦。
        html = (
            '<div class="facts"><div class="fact"><span class="lbl">情绪</span>'
            '<b>41.6</b></div></div>'
            '<div class="note">楚天龙 003040 已清仓。</div>'
        )
        labels = _labels(_check(html))
        self.assertIn("个股名称", labels)
        self.assertIn("个股代码", labels)

    def test_name_right_after_verbatim_close_is_blocked(self):
        # 边界：豁免必须正好在写作区 </div> 处结束，不能吞掉紧随其后的正文。
        html = VERBATIM_OPEN + "<p>正文里的普通一句话。</p></div>" + "楚天龙 又来了"
        self.assertIn("个股名称", _labels(_check(html)))

    def test_non_verbatim_writing_body_is_not_exempt(self):
        # 只有 data-public-writing="verbatim" 才是原文豁免；普通 writing-body 不豁免。
        html = '<div class="writing-body"><p>楚天龙 清仓</p></div>'
        self.assertIn("个股名称", _labels(_check(html)))

    def test_code_in_percent_context_outside_verbatim_is_blocked(self):
        # 百分比允许清单仍只服务账户仓位；不得顺手放过 verbatim 区外的代码。
        html = "<p>仓位 46.66% 降到 10.41%，003040 也卖了</p>"
        self.assertIn("个股代码", _labels(_check(html)))

    def test_percent_allowlist_still_applies_to_amount_scan(self):
        # 回归：金额/百分比口径没变，仓位百分比照旧放行。
        self.assertEqual([], _check("<p>把风险敞口从 46.66% 降到 10.41%</p>"))


if __name__ == "__main__":
    unittest.main()
