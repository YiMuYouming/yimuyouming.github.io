import unittest
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_review


class ConvertReviewTest(unittest.TestCase):
    def test_update_review_notes_index_refreshes_footer_day_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_review_notes = convert_review.REVIEW_NOTES
            convert_review.REVIEW_NOTES = Path(tmp)
            try:
                idx = convert_review.REVIEW_NOTES / "index.html"
                idx.write_text(
                    """<html><body>
<span class="sub">全部记录 · 1篇</span>
<span><strong>1</strong> 个交易日</span>
<!-- 2026年6月 -->
<div class="month-group">
  <div class="month-label"><span class="cnt">1篇 · 进行中</span></div>
  <div class="day-list">
    <a href="2026-06-02.html" class="day-card"><div class="dt">2</div></a>
  </div>
</div>
<div class="footer">弈沐资本 · 交易复盘系统 · 1个交易日 · 3/23 至今</div>
</body></html>""",
                    encoding="utf-8",
                )

                convert_review.update_review_notes_index(
                    "2026-06-03",
                    {
                        "weekday": "周三",
                        "上证涨幅": "+0.22",
                        "涨停家数": "51",
                        "情绪值": "32.4",
                        "赚钱效应": "差",
                        "盘后持仓": "光迅科技 100@200",
                    },
                )

                html = idx.read_text(encoding="utf-8")
                self.assertIn("全部记录 · 2篇", html)
                self.assertIn("<strong>2</strong> 个交易日", html)
                self.assertIn("2个交易日 · 3/23 至今", html)
            finally:
                convert_review.REVIEW_NOTES = original_review_notes

    def test_update_main_index_rebuilds_recent_reviews_as_mixed_timeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_portal = convert_review.PORTAL
            original_review_notes = convert_review.REVIEW_NOTES
            tmp_path = Path(tmp)
            review_notes = tmp_path / "review-notes"
            review_notes.mkdir()
            convert_review.PORTAL = tmp_path
            convert_review.REVIEW_NOTES = review_notes
            try:
                (review_notes / "weekly-2026-06-22_06-26.html").write_text(
                    """<html><head><title>W26 周复盘</title></head><body>
<h1>W26 周复盘（2026-06-22 至 2026-06-26）</h1>
<div class="kpi green"><span>周度收益</span><strong>+3.08%</strong></div>
<div class="kpi"><span>交易日</span><strong>5天</strong></div>
<div class="kpi red"><span>风控事件</span><strong>DAY_STOP</strong></div>
</body></html>""",
                    encoding="utf-8",
                )
                (review_notes / "2026-06-26.html").write_text(
                    """<html><body><table><tr><td>收盘</td><td></td><td></td><td></td><td></td><td>768/4456</td></tr></table></body></html>""",
                    encoding="utf-8",
                )
                existing_cards = "\n".join(
                    f'''<a id="recent-review-06{day:02d}" href="review-notes/2026-06-{day:02d}.html?from=recent-review-06{day:02d}" class="recent-review-card">
            <div class="recent-review-top"><span class="recent-date">6月{day}日</span><span class="review-kind">日复盘</span><span class="review-read">阅读 →</span></div>
            <div class="recent-review-title">旧日复盘 {day}</div>
            <div class="review-metric-row"></div>
    </a>'''
                    for day in [25, 24, 23, 22, 18, 17]
                )
                existing_period_card = '''<a id="recent-review-weekly-20260622-20260626" href="review-notes/weekly-2026-06-22_06-26.html?from=recent-review-weekly-20260622-20260626" class="recent-review-card period-review-card weekly-review-card">
            <div class="recent-review-top"><span class="recent-date">6/22–6/26</span><span class="review-kind review-kind-weekly">周复盘</span><span class="review-read">阅读 →</span></div>
            <div class="recent-review-title">W26 周复盘：保留人工提炼标题</div>
            <div class="review-metric-row"><span class="metric-up"><em>周收益</em><strong>+3.08%</strong></span><span class="metric-warn"><em>核心风险</em><strong>DAY_STOP</strong></span></div>
    </a>'''
                (tmp_path / "index.html").write_text(
                    f"""<html><body>
<div class="review-stat"><span>最新复盘</span><strong>6月25日</strong><em>日复盘</em></div>
<div class="recent-review-grid">
{existing_period_card}
{existing_cards}
</div>
</body></html>""",
                    encoding="utf-8",
                )

                convert_review.update_main_index(
                    "2026-06-26",
                    {
                        "weekday": "周五",
                        "上证涨幅": "-2.26",
                        "涨停家数": "60",
                        "跌停家数": "30",
                        "情绪值": "14.7",
                        "赚钱效应": "差",
                        "市场状态": "冰点",
                    },
                )

                html = (tmp_path / "index.html").read_text(encoding="utf-8")
                self.assertIn("recent-review-0626", html)
                self.assertIn("recent-review-weekly-20260622-20260626", html)
                self.assertIn("W26 周复盘", html)
                self.assertIn("W26 周复盘：保留人工提炼标题", html)
                self.assertIn("核心风险", html)
                self.assertIn("周复盘", html)
                self.assertIn('<span class="recent-date">6/22–6/26</span>', html)
                self.assertNotIn("recent-review-0618", html)
                self.assertEqual(html.count('class="recent-review-card'), 6)
                self.assertLess(html.index("recent-review-0626"), html.index("recent-review-weekly-20260622-20260626"))
                self.assertLess(html.index("recent-review-weekly-20260622-20260626"), html.index("recent-review-0625"))
            finally:
                convert_review.PORTAL = original_portal
                convert_review.REVIEW_NOTES = original_review_notes

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

    def test_parse_s4_renders_terminal_verdict_once(self):
        markdown = """### Round 3 — 洋米终审（2026-06-26）

| 维度 | 结论 |
|------|------|
| 数据口径 | 通过 |

**终稿定论**：蓝方可发布，但 STYLE 分数必须标注估算来源。
"""

        html = convert_review.parse_s4(markdown)

        self.assertEqual(html.count("蓝方可发布"), 1)
        self.assertIn('class="verdict"', html)
        self.assertIn("STYLE 分数必须标注估算来源", html)

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

    def test_parse_s1_keeps_ordered_operation_times_in_node_notes(self):
        markdown = """### 节点说明

**午盘**
⭐**今日操作（从票据读取）**：
1. **09:42 药明加仓300股@119.20**——笔2
2. **10:04 海光减仓200股@348.57**——执行预案
"""

        html = convert_review.parse_s1(markdown)

        self.assertIn("09:42 药明加仓300股", html)
        self.assertIn("10:04 海光减仓200股", html)
        self.assertNotIn('class="node-label">1. **09', html)
        self.assertNotIn('class="node-copy">42 药明加仓', html)

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
        self.assertIn('class="lesson-principle"', html)
        self.assertIn('class="lesson-evidence"', html)
        self.assertIn('class="lesson-action"', html)
        self.assertIn("可复用原则", html)
        self.assertIn("当日证据", html)
        self.assertIn("下次动作", html)
        self.assertNotIn("<ol class=\"tight-list\">", html)

    def test_parse_s2_renders_bracketed_category_inline_body_as_cognition_cards(self):
        markdown = """### 今日认知

1. **[流程纪律] 未盯盘日只补事实，不补编盘中授权。** 今日的最大约束不是行情强弱，而是过程缺失。
2. **[账户纪律] 批次对账冲突优先于一切行情判断。** 基础数量不可信时，所有主动交易动作都应降级为观察/核对。
"""

        html = convert_review.parse_s2(markdown)

        self.assertEqual(html.count('class="lesson-card cognition"'), 2)
        self.assertIn("流程纪律", html)
        self.assertIn("未盯盘日只补事实", html)
        self.assertIn("今日的最大约束不是行情强弱", html)
        self.assertIn("账户纪律", html)
        self.assertIn("批次对账冲突优先于一切行情判断", html)
        self.assertIn("基础数量不可信时", html)
        self.assertIn("先补事实层和缺口清单", html)
        self.assertIn("先核对账户事实", html)
        self.assertNotIn("<ol class=\"tight-list\">", html)

    def test_parse_s2_renders_plain_bracketed_dash_items_as_lesson_cards(self):
        markdown = """### 今日认知

1. [认知] 技术买点与系统授权必须分层 — 形态可以解释主观逻辑，但不能覆盖账户级门禁。
2. [教训] 盘中强势不等于收盘确认 — 后续仓必须预算尾盘回落。
3. [教训] 风险锚触发必须落到主标的 — 动作或拒绝理由必须二选一记录。
4. [流程缺陷] 红方采纳项必须进入次日检查 — 文字采纳要形成可回读约束。

---

### 规则教训
"""

        html = convert_review.parse_s2(markdown)

        self.assertEqual(html.count('class="lesson-card cognition"'), 1)
        self.assertEqual(html.count('class="lesson-card warning"'), 3)
        self.assertIn("技术买点与系统授权必须分层", html)
        self.assertIn("后续仓必须预算尾盘回落", html)
        self.assertIn("红方采纳项必须进入次日检查", html)
        self.assertIn(
            '<div class="lesson-evidence"><div class="para">文字采纳要形成可回读约束。</div></div>',
            html,
        )
        self.assertNotIn("<ol class=\"tight-list\">", html)

    def test_parse_s2_renders_today_cognition_numbered_bold_as_cards(self):
        markdown = """最多 5 条。

### 今日认知

**1. 涨停次日高开放量分歧 = 分批锁利，不赌方向**

雅克昨日涨停，今日高开后放量回落，正确做法是分批减仓而不是一次性清仓。

**2. 新方向建仓必须先看板块再定个股**

建仓理由是单票缩量突破，但没有先确认板块强度、资金流向和中军表现。

### 规则教训

- **W1开仓偏离预案**：今日情绪低迷，新开仓偏离了前日预案。
"""

        html = convert_review.parse_s2(markdown)

        self.assertEqual(html.count('class="lesson-card cognition"'), 2)
        self.assertIn("涨停次日高开放量分歧", html)
        self.assertIn("新方向建仓必须先看板块", html)
        self.assertIn("触发高开放量", html)
        self.assertIn("开仓前先确认板块强度", html)
        self.assertIn("规则教训", html)
        self.assertNotIn("<ol class=\"tight-list\">", html.split("规则教训", 1)[0])

    def test_convert_md_to_html_redacts_public_execution_details(self):
        markdown = """---
date: 2026-07-14
weekday: 周二
情绪值: 74.2
上证指数: 3967.13
上证涨幅: 1.36
涨停家数: 83
跌停家数: 22
盘后持仓: "瑞芯微800股@219.02"
---

## 一、当日复盘

### 节点说明

**午盘**
- 弈沐操作[TICKET-20260714-603893-0001]：10:39加仓200股@210.75。

### 持仓与交易

| 标的 | 仓位 | 盈亏 | 原因 |
|------|------|------|------|
| 瑞芯微 | 600股→800股 | 当日实现-2955元 | 成本219.02，违规加仓 |

### 一句话结论

> **Portal 今日一句话来源**：一句话讲清当日市场状态和系统判断；不写 ticket、股数、成本、精确买卖指令。

公开结论保留。
"""

        with tempfile.TemporaryDirectory() as tmp:
            original_review_notes = convert_review.REVIEW_NOTES
            convert_review.REVIEW_NOTES = Path(tmp)
            try:
                source = Path(tmp) / "2026_7_14_Tuesday_ReviewNote.md"
                source.write_text(markdown, encoding="utf-8")

                _, output_path = convert_review.convert_md_to_html(source)
                html = output_path.read_text(encoding="utf-8")

                for secret in (
                    "瑞芯微800股@219.02",
                    "TICKET-20260714-603893-0001",
                    "10:39加仓200股@210.75",
                    "600股→800股",
                    "-2955元",
                    "成本219.02",
                ):
                    self.assertNotIn(secret, html)
                self.assertIn("持仓状态已记录", html)
                self.assertIn("上证 3967.13 +1.36%", html)
                self.assertIn("83涨停 / 22跌停", html)
                self.assertNotIn("Portal 今日一句话来源", html)
                self.assertNotIn("不写 ticket", html)
                self.assertIn("公开结论保留", html)
            finally:
                convert_review.REVIEW_NOTES = original_review_notes

    def test_public_review_cells_redact_bare_position_quantities(self):
        self.assertEqual(
            convert_review.sanitize_public_review_cell("数量", "800"),
            "已脱敏",
        )
        self.assertEqual(
            convert_review.sanitize_public_review_cell("现持仓", "4000"),
            "已脱敏",
        )
        self.assertEqual(
            convert_review.sanitize_public_review_cell("T+1可卖数量", "4000"),
            "已脱敏",
        )
        self.assertEqual(
            convert_review.sanitize_public_review_cell("时间", "2026-07-20 10:46:01"),
            "盘中",
        )
        self.assertEqual(
            convert_review.sanitize_public_review_cell("价格", "24.78"),
            "已脱敏",
        )

    def test_public_review_text_redacts_action_amounts_and_risk_prices(self):
        text = convert_review.sanitize_public_review_text(
            "任一条件成立先减400；跌破22.91或不站稳MA5=215.49再减仓2000；无execution ticket"
        )
        self.assertNotIn("减400", text)
        self.assertNotIn("22.91", text)
        self.assertNotIn("215.49", text)
        self.assertNotIn("减仓2000", text)
        self.assertNotIn("ticket", text.lower())
        self.assertIn("先减部分仓位", text)
        self.assertIn("跌破关键位", text)
        self.assertIn("内部执行记录", text)

        self.assertEqual(
            convert_review.sanitize_public_review_cell(
                "触发条件", "锚点继续走弱则先减400"
            ),
            "风险条件已记录（具体阈值已脱敏）",
        )

    def test_public_review_text_redacts_prose_execution_prices(self):
        text = convert_review.sanitize_public_review_text(
            "瑞芯微盘中以207.36清仓最后部分仓位；神火股份按23.88卖出；"
            "收盘208.05，距离清仓价207.36仅差0.33%。"
        )

        self.assertNotIn("207.36", text)
        self.assertNotIn("23.88", text)
        self.assertIn("收盘208.05", text)
        self.assertIn("以成交价已隐藏清仓", text)
        self.assertIn("按成交价已隐藏卖出", text)
        self.assertIn("清仓价已脱敏", text)

    def test_public_review_text_redacts_time_at_price_without_corrupting_time(self):
        text = convert_review.sanitize_public_review_text(
            "瑞芯微早盘两笔降险（10:15@198.71/10:29@199.38）"
        )

        self.assertNotIn("10:15", text)
        self.assertNotIn("10:29", text)
        self.assertNotIn("198.71", text)
        self.assertNotIn("199.38", text)
        self.assertNotIn("10:部分仓位", text)
        self.assertEqual(text.count("盘中@成交价已隐藏"), 2)

    def test_public_review_text_redacts_position_arithmetic(self):
        text = convert_review.sanitize_public_review_text(
            "盘中加仓，原4000股+2000=6000；清仓最后400股，累计800股全清。"
        )

        for secret in ("4000", "2000", "6000", "400", "800"):
            self.assertNotIn(secret, text)
        self.assertIn("仓位数量已脱敏", text)
        self.assertIn("累计仓位已脱敏", text)

    def test_public_review_text_redacts_t1_position_availability(self):
        text = convert_review.sanitize_public_review_text(
            "部分仓位T+1锁定至7月22日；全部T+1锁定至7月22日。"
        )

        self.assertNotIn("锁定至7月22日", text)
        self.assertNotIn("部分仓位T+1", text)
        self.assertNotIn("全部T+1", text)
        self.assertEqual(text.count("T+1状态已记录"), 2)

    def test_public_review_text_redacts_bare_risk_prices(self):
        text = convert_review.sanitize_public_review_text(
            "破211.93降险；站稳210.16后继续观察。"
        )

        self.assertNotIn("211.93", text)
        self.assertNotIn("210.16", text)
        self.assertIn("破关键位降险", text)
        self.assertIn("站稳关键位", text)

    def test_public_review_text_translates_internal_audit_terms(self):
        text = convert_review.sanitize_public_review_text(
            "blocked_degraded；observation_only；process_defect=true；"
            "observe / no_touch / exclude；红方process_defect补漏；"
            "本轮为observation-only，4只no_touch，process-defect检查项"
        )

        for secret in (
            "blocked_degraded",
            "observation_only",
            "process_defect",
            "observe",
            "no_touch",
            "exclude",
            "process-defect",
        ):
            self.assertNotIn(secret, text.lower())
        self.assertIn("数据降级，仅观察", text)
        self.assertIn("流程缺口已记录", text)
        self.assertIn("观察 / 不参与 / 排除", text)

    def test_public_review_cells_redact_action_prices_and_monetary_pnl(self):
        self.assertEqual(
            convert_review.sanitize_public_review_cell("现价", "207.36(清仓)"),
            "已脱敏",
        )
        self.assertEqual(
            convert_review.sanitize_public_review_cell("盈亏", "-4374"),
            "金额已脱敏",
        )
        self.assertEqual(
            convert_review.sanitize_public_review_cell("盈亏", "+0.02%"),
            "+0.02%",
        )

    def test_public_review_text_redacts_local_audit_paths_and_hashes(self):
        text = convert_review.sanitize_public_review_text(
            "/Users/yimu/Documents/YM_Capital/Market_Watch/artifacts/d1_draft_receipt.json "
            "receipt_sha256=af6a406713a2a2a3eea03c6e99a33bbe1598c4e22fb4fdc886d1007cc1e927d7"
        )
        self.assertNotIn("/Users/", text)
        self.assertNotIn("d1_draft_receipt.json", text)
        self.assertNotIn("af6a406713a2", text)
        self.assertIn("路径已隐藏", text)
        self.assertIn("回执哈希=哈希已隐藏", text)

    def test_public_review_text_redacts_trade_audit_identifiers_and_gate_times(self):
        text = convert_review.sanitize_public_review_text(
            "trade_id=143；10:43:50已成交；10:06 gate=true，10:43精确gate快照缺失；"
            "decision_gate.allowed=false；gatestatus待补；"
            "候选CAN-20260720-000933；无盘前ticket，仅作已成交reconciliation"
        )
        for secret in (
            "trade_id=143",
            "10:43:50",
            "盘中:50",
            "10:06",
            "10:43",
            "gate=true",
            "decision_gate.allowed=false",
            "allowed=false",
            "gatestatus",
            "can-20260720-000933",
            "ticket",
            "reconciliation",
        ):
            self.assertNotIn(secret, text.lower())
        self.assertIn("交易流水已隐藏", text)
        self.assertIn("内部执行校验已脱敏", text)

    def test_public_review_text_redacts_comma_pnl_and_average_costs(self):
        text = convert_review.sanitize_public_review_text(
            "中科曙光均成本≈100.29，浮盈+3,087/+4.40%；"
            "第二笔均价≈100.29；紫光清仓锁盈+13,160元，已实现+13,160。"
        )

        for secret in ("100.29", "3,087", "13,160", "+13,金额已脱敏"):
            self.assertNotIn(secret, text)
        self.assertIn("均成本≈已脱敏", text)
        self.assertIn("均价≈已脱敏", text)
        self.assertIn("浮盈金额已脱敏/+4.40%", text)
        self.assertIn("锁盈金额已脱敏", text)
        self.assertIn("已实现金额已脱敏", text)

    def test_public_review_text_redacts_bare_gate_state_and_plan_prices(self):
        text = convert_review.sanitize_public_review_text(
            "08:19起已回退为`allowed=false`；歌尔考验22.91、守22.91，"
            "未站22.48且两锚同弱时提请降险；中国软件35.89后完成回踩，"
            "仍受35.89前高约束，失守34.09/33.49失效，上方23.09。"
        )

        for secret in ("allowed=false", "22.91", "22.48", "35.89", "34.09", "33.49", "23.09"):
            self.assertNotIn(secret, text)
        self.assertIn("内部执行校验已脱敏", text)
        self.assertIn("考验关键位", text)
        self.assertIn("关键位突破后完成回踩", text)

    def test_public_review_text_redacts_execution_time_pairs_and_internal_fields(self):
        text = convert_review.sanitize_public_review_text(
            "两笔买入（09:46 + 09:57）都与执行卡冲突；"
            "human_required=DATA_REVIEW_REQUIRED；added_candidate_ids=[]；"
            "changed_candidate_ids=[]；changes=[]；ledger与d2_receipt一致；"
            "source_gap保留；radarsignal待补；decision_gate未通过；POS-SIZE-008未适用；"
            "W1_EMOTION与W1_PROMOTION保留。"
        )

        for secret in (
            "09:46", "09:57", "human_required", "DATA_REVIEW_REQUIRED",
            "added_candidate_ids", "ledger", "d2_receipt", "source_gap", "radarsignal",
            "changed_candidate_ids", "changes=[]", "decision_gate", "POS-SIZE-008",
            "W1_EMOTION", "W1_PROMOTION",
        ):
            self.assertNotIn(secret.lower(), text.lower())
        self.assertIn("盘中", text)
        self.assertIn("需人工复核", text)
        self.assertIn("候选变更已记录", text)
        self.assertIn("数据缺口", text)
        self.assertEqual(text.count("盘中"), 2)

    def test_public_review_text_redacts_bare_receipt_fields_and_hashes(self):
        text = convert_review.sanitize_public_review_text(
            "`receipt_sha256`与canonical不一致，`added_candidate_ids`位于"
            "`candidate_disposition`；用`scripts.selection_closure.artifact_sha256`重算，"
            "哈希a665f21bb24c92dafd877e78372e312fc91c1399bd0013f635c1805cbd768b7f。"
        )

        for secret in (
            "receipt_sha256", "canonical", "added_candidate_ids", "candidate_disposition",
            "scripts.selection_closure.artifact_sha256", "a665f21bb24c92d",
        ):
            self.assertNotIn(secret.lower(), text.lower())
        self.assertIn("哈希已隐藏", text)

    def test_public_review_text_redacts_plan_price_shorthand(self):
        text = convert_review.sanitize_public_review_text(
            "歌尔看22.48/23.01与两锚，不站回22.48则降险；"
            "中国软件看35.89后确认，盘中节点复核22.48。"
        )

        for secret in ("22.48", "23.01", "35.89"):
            self.assertNotIn(secret, text)
        self.assertIn("看关键位", text)
        self.assertIn("不站回关键位", text)

    def test_public_review_cells_redact_numeric_trigger_thresholds(self):
        self.assertEqual(
            convert_review.sanitize_public_review_cell(
                "触发/失效", "突破35.89后缩量守住；失守34.09/33.49失效"
            ),
            "风险条件已记录（具体阈值已脱敏）",
        )
        self.assertNotIn(
            "35.89",
            convert_review.sanitize_public_review_cell(
                "今日检查", "35.89突破与价格/时间回踩"
            ),
        )


if __name__ == "__main__":
    unittest.main()
