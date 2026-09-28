"""Privacy red-line gate: blocked sentences are caught, the public draft passes.

The cases mirror what the 2026-09-28 gate actually had to stop (G1–G4 of
PLAN §6.1) plus one positive case built from the day's public draft, so the
allowlist stays exactly as wide as it needs to be.
"""

import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import portal_check


NAMES = ["楚天龙", "润泽科技"]
CODES = ["003040", "300442"]

BLOCKED_CASES = [
    # G1 个股名称与代码
    ("个股名称", "<p>楚天龙 003040 清仓</p>"),
    ("个股代码", "<p>今日卖出 300442</p>"),
    # G1/G2 金额与股数
    ("千分位金额", "<p>浮亏 -38,170 元</p>"),
    ("股数", "<p>减仓 7000 股</p>"),
    # G3 机器话
    ("规则编号", "<p>按 WIN-ICE-W1-001 关闭</p>"),
    ("lesson 编号", "<p>见 lesson_16 诱多判定</p>"),
    ("rules 路径", "<p>见 rules/双冰场景.md</p>"),
    ("章节符号", "<p>§一 节假日规则</p>"),
    ("红方编号", "<p>R4 已追踪</p>"),
    ("红方", "<p>红方提出质疑</p>"),
    ("回执", "<p>回执编号见附录</p>"),
    ("sha256", "<p>sha256: abc</p>"),
    ("阅读投影", "<p>阅读投影；当时可见时点未核实</p>"),
    ("可见时点", "<p>当时可见时点未核实</p>"),
    ("执行卡", "<p>执行卡未生成</p>"),
    ("门禁", "<p>交易门禁未放行</p>"),
    # G4 对话体
    ("对话体与你", "<p>与你说的一致</p>"),
    ("对话体你说", "<p>你说明天是出金日</p>"),
    ("对话体原话", "<p>弈沐原话：低开概率高</p>"),
    # G2 脱敏残渣
    ("脱敏残渣若干笔", "<p>分若干笔减仓</p>"),
    ("脱敏残渣上限", "<p>触发内部集中度上限</p>"),
    ("脱敏残渣关键位", "<p>关键确认位 日线</p>"),
    ("脱敏残渣风险动作", "<p>风险处理动作已执行</p>"),
    ("脱敏残渣可卖", "<p>可卖状态待确认</p>"),
]

PASS_CASES = [
    # 今日公开稿：仓位百分比在允许清单内
    (
        "<p>把风险敞口从 46.66% 降到 10.41%</p>",
        "账户层面仓位百分比",
    ),
    (
        "<p>情绪 16.5 冰点，指数放量下跌，37 个行业只有 6 个净流入、"
        "33 只涨停里 26 只首板。</p>",
        "公开稿正文",
    ),
    (
        "<p>问题不在胜率，在单笔尾部。</p>",
        "公开稿一句认知",
    ),
]


class RedLineTests(unittest.TestCase):
    def test_blocked_sentences_are_caught(self):
        for label, html in BLOCKED_CASES:
            with self.subTest(label):
                text = portal_check._strip_tags_for_redline(html)[0]
                hits = portal_check.check_redlines(text, NAMES, CODES)
                self.assertTrue(hits, f"{label} 未被红线命中: {html}")

    def test_public_draft_passes(self):
        for html, label in PASS_CASES:
            with self.subTest(label):
                text = portal_check._strip_tags_for_redline(html)[0]
                hits = portal_check.check_redlines(text, NAMES, CODES)
                self.assertEqual([], hits, f"{label} 误报: {hits}")

    def test_strip_tags_removes_script_style_and_comments(self):
        html = (
            "<html><head><style>.a{color:red}</style></head><body>"
            "<script>var x = '红方';</script><!-- sha256 -->"
            "<p>可见正文</p></body></html>"
        )
        text = portal_check._strip_tags_for_redline(html)[0]
        self.assertIn("可见正文", text)
        self.assertNotIn("红方", text)
        self.assertNotIn("sha256", text)
        self.assertNotIn("color", text)

    def test_allowlist_only_covers_bare_percentages(self):
        # 46.66% 放行，但 46,660 或 46.66 股 不放行
        self.assertEqual(
            [],
            portal_check.check_redlines("仓位 46.66% 降到 10.41%", [], []),
        )
        self.assertTrue(
            portal_check.check_redlines("浮亏 46,660", [], []),
            "千分位金额不应被百分比允许清单放行",
        )

    def test_trade_window_filters_by_trade_date(self):
        with patch.object(portal_check, "load_traded_symbols", return_value=(["万科A"], ["000002"])):
            text = portal_check._strip_tags_for_redline("<p>万科A 000002</p>")[0]
            hits = portal_check.check_redlines(text, ["万科A"], ["000002"])
        self.assertTrue(hits, "窗口内成交个股应命中")
        # 旧代码不在名单内 → 不命中
        self.assertEqual(
            [],
            portal_check.check_redlines("平安银行 000001", ["万科A"], ["000002"]),
        )

    def test_trade_source_failure_fails_closed(self):
        class _API:
            def __init__(self, *a, **k):
                pass

            def fetch(self, path):
                raise OSError("bridge down")

        with patch("sync_pnl_data.BridgeAPI", _API):
            with self.assertRaises(RuntimeError) as ctx:
                portal_check.load_traded_symbols(source="local")
        self.assertIn("redline_trade_source_unavailable", str(ctx.exception))

    def test_position_symbols_come_from_frontmatter(self):
        with __import__("tempfile").TemporaryDirectory() as tmp:
            note = Path(tmp) / "note.md"
            note.write_text(
                '---\ndate: 2026-09-28\n盘后持仓: "润泽科技 1000@66.22"\n---\n',
                encoding="utf-8",
            )
            names, codes = portal_check.load_position_symbols(note)
        self.assertIn("润泽科技", names)


if __name__ == "__main__":
    unittest.main()


class DeferredHistoryTests(unittest.TestCase):
    """周/月复盘卡由 sync_weekly_review 产出，不在本次同步链内。"""

    INDEX_HTML = (
        '<a href="weekly-2026-09-14_09-18.html" class="wk-card">'
        '<div class="wt">门禁外动作 · 观察底座</div></a>'
        '<a href="2026-09-28.html" class="day-card">'
        '<div class="mm"><span class="tag tag-a">持仓</span></div></a>'
    )

    def test_period_card_hits_are_deferred_not_blocking(self):
        text, positions = portal_check._strip_tags_for_redline(self.INDEX_HTML)
        hits = portal_check._scan_redline_hits(text, [], [])
        self.assertTrue(hits, "周卡文本应命中红线")
        spans = portal_check._deferred_redline_spans(self.INDEX_HTML, "review-notes/index.html")
        self.assertEqual(1, len(spans))
        deferred, blocking = [], []
        for start, end, description in hits:
            raw_start = positions[start]
            raw_end = positions[end - 1] + 1
            (deferred if any(a <= raw_start and raw_end <= b for a, b in spans) else blocking).append(description)
        self.assertTrue(deferred)
        self.assertEqual([], blocking, "当日卡与持仓标签不得被判成 deferred")

    def test_daily_page_hits_are_not_deferred(self):
        text, _ = portal_check._strip_tags_for_redline(
            "<p>交易门禁未放行</p>"
        )
        hits = portal_check._scan_redline_hits(text, [], [])
        self.assertTrue(hits)
        spans = portal_check._deferred_redline_spans(
            "<html><body><p>交易门禁未放行</p></body></html>", "daily-notes/2026-09-28.html"
        )
        self.assertEqual([], spans)
