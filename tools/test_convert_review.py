import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_review


class ConvertReviewTest(unittest.TestCase):
    def test_parse_s0_keeps_tables_with_their_headings(self):
        markdown = """> 来源：昨日预案

### 持仓处理

| 标的 | 操作 |
|------|------|
| 光迅科技 | 持有 |

### 连板板块→操作映射

| 板块 | 触发条件 |
|------|----------|
| 通信设备 | 主力流入 |

### 操作指南

**总基调**：测试基调
"""

        html = convert_review.parse_s0(markdown)

        holding_heading = html.index("持仓处理")
        holding_table = html.index("<th>标的</th>")
        lianban_heading = html.index("连板板块→操作映射")
        lianban_table = html.index("<th>板块</th>")
        guide_heading = html.index("操作指南")

        self.assertLess(holding_heading, holding_table)
        self.assertLess(holding_table, lianban_heading)
        self.assertLess(lianban_heading, lianban_table)
        self.assertLess(lianban_table, guide_heading)

    def test_parse_s4_supports_blockquote_round_marker(self):
        markdown = """> 洋米 Round 1 — 2026-06-10 16:00

### Q0 数据口径校验

| 标的 | 问财主力 | 稳米主力 |
|------|---------|---------|
| 豪恩汽电 | +4526万 | +4526万 |

### Round 1 总结

| 维度 | 评级 |
|------|------|
| 盲区扫描 | 光伏 |

### Round 2 — 稳米回应（2026-06-10）

| # | 洋米质疑 | 稳米回应 |
|---|---------|---------|
| 1 | 光伏盲区 | 已采纳 |

### Round 3 — 洋米终审（2026-06-10 16:45）

**红方对抗闭环完成。**
"""

        html = convert_review.parse_s4(markdown)

        self.assertIn("3轮辩论", html)
        self.assertIn("Q0 数据口径校验", html)
        self.assertIn("<th>问财主力</th>", html)
        self.assertIn("Round 1 总结", html)
        self.assertIn("盲区扫描", html)
        self.assertIn("光伏盲区", html)
        self.assertIn("红方对抗闭环完成", html)

    def test_parse_s1_renders_emotion_table_as_board(self):
        markdown = """### 表2：情绪高标

| 指标 | 竞价 | 早盘 | 午盘 | 尾盘 | 收盘 | 门槛 |
| --- | --- | --- | --- | --- | --- | --- |
| 涨停收益 | — | — | — | 1.98 | 1.98 | >2%(低迷)/>3%(正常) |
| 炸板率 | 63.86 | — | — | 73.17 | —(收盘封板改善) | <30%(W1追涨)/<40%(W2冰点) |
| 封板率 | 36.14 | — | — | 26.83 | —(收盘批量封板后回升) | — |
| 一进二晋级率 | 11.84 | — | — | 8.86 | 8.86 | >15%(低迷)/>18%(主升) |
| 梯队 | 5/4/3 | 5/3/3 | 3/3 | 3(6)-2(11) | 3(4非ST+2ST)-2(8非ST+3ST) | — |
| 最高板/次高板 | 上海贝岭(5板) | 贝岭5板 | 5板断 | 深桑达A/新金路 | 深桑达A(20.81)/新金路(21.31) | — |
| 竞价验证结论 | — | — | — | — | A好+B差 | A好+B差 |
"""

        html = convert_review.parse_s1(markdown)
        table2 = html.split("📈 表2：情绪高标", 1)[1]

        self.assertIn('class="emotion-board"', table2)
        self.assertIn("3(4非ST+2ST)-2(8非ST+3ST)", table2)
        self.assertIn("A好+B差", table2)
        self.assertIn("&lt;30%(W1追涨)/&lt;40%(W2冰点)", table2)
        self.assertNotIn("<th>指标</th>", table2)

    def test_parse_s1_renders_all_node_notes_as_cards(self):
        markdown = """### 节点说明

**竞价**：
- **说明**：低开分歧，创业板偏强。
- **结论**：观察板块承接。
**尾盘**(~14:30)：
- **说明**：电子化学品持续走强。
**收盘**(~15:00)：
- **结论**：分歧日 V 型反转确认。
"""

        html = convert_review.parse_s1(markdown)

        self.assertIn('class="node-timeline"', html)
        self.assertIn("node-note-card", html)
        self.assertIn("竞价", html)
        self.assertIn("尾盘", html)
        self.assertIn("收盘", html)
        self.assertIn("电子化学品持续走强", html)
        self.assertEqual(html.count('class="node-note-card"'), 3)
        self.assertNotIn("<strong>尾盘</strong>(~14:30)：", html)

    def test_parse_s1_renders_node_notes_without_colon_as_cards(self):
        markdown = """### 节点说明

**竞价**
- 说明：低开分歧。
- 结论：观察承接。

**早盘**
- 说明：半导体反包。
- 弈沐操作[TICKET-20260624-688041-0002]：买入海光信息。
- 持仓：雅克走强。

---
"""

        html = convert_review.parse_s1(markdown)

        self.assertIn('class="node-timeline"', html)
        self.assertEqual(html.count('class="node-note-card"'), 2)
        self.assertIn('class="node-label">说明</div>', html)
        self.assertIn('class="node-label">操作</div>', html)
        self.assertIn('class="node-label">持仓</div>', html)
        self.assertNotIn('class="node-copy">--</div>', html)
        self.assertNotIn('<div class="para"><strong>竞价</strong></div>', html)

    def test_parse_s2_renders_lesson_cards(self):
        markdown = """> 最多 8 条。

1. **[认知] 分歧日=趋势买点** — 回踩买才是正确出手方式。

2. **[教训] 出手之前停3秒** — 自选池、窗口、量能三问必须前置。
"""

        html = convert_review.parse_s2(markdown)

        self.assertIn('class="lesson-grid"', html)
        self.assertIn('class="lesson-card cognition"', html)
        self.assertIn('class="lesson-card warning"', html)
        self.assertIn("分歧日=趋势买点", html)
        self.assertIn("自选池、窗口、量能三问", html)
        self.assertNotIn("<ol class=\"tight-list\">", html)


if __name__ == "__main__":
    unittest.main()
