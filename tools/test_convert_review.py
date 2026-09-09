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
<div class="kpi green"><span>周度收益</span><strong class="gain">+3.08%</strong></div>
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

    def test_extract_close_ratio_reads_expanded_close_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_review_notes = convert_review.REVIEW_NOTES
            convert_review.REVIEW_NOTES = Path(tmp)
            try:
                (Path(tmp) / "2026-08-13.html").write_text(
                    """<table><tr><td>收盘</td>
<td>上证-0.50%</td>
<td>情绪21.2%；规范校验涨跌1192/4021；涨停59/跌停4</td>
<td>医药逆势收涨</td>
<td>持仓相对表现</td>
<td>来源记录</td>
<td>数据缺口</td></tr></table>""",
                    encoding="utf-8",
                )

                ratio = convert_review.extract_close_ratio("2026-08-13")
            finally:
                convert_review.REVIEW_NOTES = original_review_notes

        self.assertEqual(
            ratio,
            '<b class="upnum">1192</b>/<b class="dnnum">4021</b>',
        )

    def test_extract_period_metric_accepts_classed_strong(self):
        html = '<span>周度收益</span><strong class="gain">+3.08%</strong>'

        self.assertEqual(
            convert_review.extract_period_metric(html, ["周度收益", "收益"]),
            "+3.08%",
        )

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

    def test_convert_md_to_html_accepts_operation_guide_section_alias(self):
        markdown = """---
date: 2026-08-04
weekday: 周二
情绪值: 67
上证指数: 3822.28
上证涨幅: 0.33
涨停家数: 138
跌停家数: 0
盘后持仓: 空仓
---

## 第〇部分：当日操作指引

### 操作指南

公开操作边界。
"""

        with tempfile.TemporaryDirectory() as tmp:
            original_review_notes = convert_review.REVIEW_NOTES
            convert_review.REVIEW_NOTES = Path(tmp)
            try:
                source = Path(tmp) / "2026_8_4_Tuesday_ReviewNote.md"
                source.write_text(markdown, encoding="utf-8")
                _, output_path = convert_review.convert_md_to_html(source)
                html = output_path.read_text(encoding="utf-8")
            finally:
                convert_review.REVIEW_NOTES = original_review_notes

        self.assertIn("第〇部分 · 当日操作指引", html)
        self.assertIn("公开操作边界", html)

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
        self.assertIn('<div class="emotion-conclusion">', table2)
        self.assertNotIn('<div class="emotion-kpi "><div class="klabel">结论</div>', table2)
        self.assertNotIn('<span class="rlabel">竞价验证结论</span>', table2)
        self.assertIn("&lt;30%(W1追涨)/&lt;40%(W2冰点)", table2)
        self.assertNotIn("<th>指标</th>", table2)

    def test_parse_s1_renders_observation_dimension_as_metric_column(self):
        markdown = """### 表2：情绪高标

| 观察维度 | 竞价 | 收盘 |
| --- | --- | --- |
| 最高板/晋级 | 最高5板 | 最高5板 |
| 涨跌停与炸板 | 涨停8/跌停1 | 涨停63/跌停10 |
"""

        html = convert_review.parse_s1(markdown)
        table2 = html.split("📈 表2：情绪高标", 1)[1]

        self.assertIn('<div class="stage-title">竞价</div>', table2)
        self.assertIn('<span class="rlabel">最高板/晋级</span>', table2)
        self.assertIn('<span class="rval">最高5板</span>', table2)
        self.assertNotIn('<div class="stage-title">观察维度</div>', table2)
        self.assertNotIn('<span class="rlabel">—</span>', table2)

    def test_parse_s1_uses_frontmatter_for_missing_emotion_summary_rows(self):
        markdown = """### 表2：情绪高标

| 观察维度 | 竞价 | 收盘 |
| --- | --- | --- |
| 最高板/晋级 | 最高5板 | 最高5板 |
| 涨跌停与炸板 | 涨停8/跌停1 | 涨停63/跌停10 |
"""
        frontmatter = {
            "赚钱效应": "差",
            "昨日涨停收益": "0.06",
            "昨日连板收益": "-0.42",
            "封板率": "⚠️需复核（数据源脏）",
            "炸板率": "⚠️需复核（数据源脏）",
            "一进二晋级率": "13.51",
            "三进四晋级率": "11.11",
        }

        html = convert_review.parse_s1(markdown, frontmatter)
        table2 = html.split("📈 表2：情绪高标", 1)[1]

        for value in ("差", "0.06", "-0.42", "⚠️需复核", "13.51", "11.11"):
            self.assertIn(value, table2)

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

    def test_parse_s2_renders_plain_numbered_sentence_cognitions_as_cards(self):
        markdown = """### 今日认知

1. 市场强不等于持仓强。今日情绪与涨停数量明显修复，但持仓仍弱于同链锚点；板块繁荣只能用于风险判断，不能替持仓结构辩护。
2. 没有盘中盯盘会话时，复盘只能基于五节点事实、收盘数据与结构化回执；以“无盘中盘感记录”明确留缺，不用收盘结果伪造当时判断。
"""

        html = convert_review.parse_s2(markdown)

        self.assertEqual(html.count('class="lesson-card cognition"'), 2)
        self.assertIn("市场强不等于持仓强", html)
        self.assertIn("板块繁荣只能用于风险判断", html)
        self.assertIn("没有盘中盯盘会话时，复盘只能基于五节点事实", html)
        self.assertIn("明确留缺", html)
        self.assertNotIn("<ol class=\"tight-list\">", html)

    def test_redacts_account_total_close_prices_and_unmarked_unlock_quantities(self):
        raw = (
            "持仓：深信服 -3.23% 收 121.50，利通电子 +0.96% 收 119.36；"
            "账户：总资产 693178.47、仓位25.98%。"
            "利通电子1000股（新300解锁8/12），收盘回红，新300已解锁。"
        )

        text = convert_review.sanitize_public_review_text(raw)

        for secret in ("121.50", "119.36", "693178.47", "1000股", "新300", "8/12"):
            self.assertNotIn(secret, text)
        self.assertIn("价格已脱敏", text)
        self.assertIn("总资产已脱敏", text)
        self.assertIn("新增批次可卖状态已记录", text)

    def test_public_review_text_redacts_compact_holding_close_prices(self):
        text = convert_review.sanitize_public_review_text(
            "收盘：深信服收123.13(-0.76%)、通宇收36.30(-0.11%)，均跑输市场；"
            "利通收142.84(+3.88%)，已清仓。"
        )

        for secret in ("123.13", "36.30", "142.84"):
            self.assertNotIn(secret, text)
        self.assertIn("收 价格已脱敏", text)

    def test_public_review_text_redacts_chinese_execution_counts(self):
        text = convert_review.sanitize_public_review_text(
            "但今天又有五笔买入，也完成三笔卖出：复盘要同时检查减掉什么、又增加什么。"
        )

        self.assertEqual(
            text,
            "但今天又有新增风险暴露，也完成风险处理动作：复盘要同时检查减掉什么、又增加什么。",
        )

    def test_translates_executable_ticket_and_trade_watch_labels(self):
        text = convert_review.sanitize_public_review_text(
            "不创建 executable ticket；两只持仓均进入 trade_watch。"
        )

        self.assertNotIn("executable", text)
        self.assertNotIn("trade_watch", text)
        self.assertIn("内部执行记录", text)
        self.assertIn("持仓复核", text)

    def test_public_review_text_redacts_win_execution_rule_ids(self):
        text = convert_review.sanitize_public_review_text(
            "冰点规则 WIN-ICE-W1-001 已关闭。"
        )

        self.assertNotIn("WIN-ICE-W1-001", text)
        self.assertIn("冰点规则", text)

    def test_public_review_text_redacts_execution_receipt_counts_and_authorization_details(self):
        text = convert_review.sanitize_public_review_text(
            "无成交（票据 0）；预案动作未执行，未获弈沐指令。"
        )

        for secret in ("票据 0", "来源记录 0", "未获弈沐指令"):
            self.assertNotIn(secret, text)
        self.assertIn("成交细节已隐藏", text)
        self.assertIn("执行原因未公开", text)

    def test_public_review_text_redacts_comparator_risk_levels(self):
        text = convert_review.sanitize_public_review_text(
            "通宇持续 <32.5（降低风险建议）；中安科（<3.36 降风险）。"
        )

        for secret in ("32.5", "3.36"):
            self.assertNotIn(secret, text)
        self.assertIn("关键位", text)

    def test_public_review_text_redacts_holding_concentration_percentages(self):
        text = convert_review.sanitize_public_review_text(
            "总仓位以收盘约 43.74% 为只减不增基准；紫光单票 27.3% >25% 违规；"
            "持有（超限 27.3%>25%）。"
        )

        for secret in ("43.74%", "27.3%", "25%"):
            self.assertNotIn(secret, text)
        self.assertIn("账户比例已脱敏", text)

    def test_public_review_text_redacts_compact_position_caps_and_account_rule_ids(self):
        text = convert_review.sanitize_public_review_text(
            "不新增；现仓48.04%，先处理超限。ACCT-RISK-001：仍持仓时30%上限；"
            "次日先处理弱势与48.04%总仓风险；连亏持仓上限为30%，"
            "生产端仍显示0%，昨日计划亦按0%表述；仓位超30%参考上限。"
        )

        for secret in ("48.04%", "30%", "ACCT-RISK-001"):
            self.assertNotIn(secret, text)
        self.assertIn("账户比例已脱敏", text)
        self.assertIn("内部集中度上限", text)

    def test_public_review_text_redacts_internal_source_debug_labels(self):
        text = convert_review.sanitize_public_review_text(
            "AI context 风险；连板明细源空（limit_up_detail returned=0）。"
        )

        self.assertNotIn("AI context", text)
        self.assertNotIn("limit_up_detail", text)
        self.assertNotIn("returned=0", text)
        self.assertIn("系统判断", text)
        self.assertIn("连板明细数据缺失", text)

    def test_public_review_text_redacts_compact_execution_state_labels(self):
        text = convert_review.sanitize_public_review_text(
            "保留 PLAN_W1_CLOSED、WINDOW_CLOSED、POSITION_ADD_BLOCKED。"
        )

        for secret in ("PLAN_W1_CLOSED", "WINDOW_CLOSED", "POSITION_ADD_BLOCKED"):
            self.assertNotIn(secret, text)
        self.assertIn("执行条件已隐藏", text)

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

    def test_convert_md_to_html_anonymizes_current_holding_names_and_codes(self):
        markdown = """---
date: 2026-09-04
weekday: 周五
情绪值: 44.5
上证指数: 3930.12
上证涨幅: -0.30
涨停家数: 39
跌停家数: 9
盘后持仓: "甲辰科技8000股、乙巳股份4100股；仓位48.04%"
---

## 一、当日复盘

### 持仓与交易

| 标的 | 代码 | 仓位 | 原因 |
|------|------|------|------|
| 甲辰科技 | 600001 | 8000股 | 持仓风险处理 |
| 乙巳股份 | 000002 | 4100股 | 持仓风险处理 |

### 一句话结论

甲辰科技与乙巳股份仅作持仓风险处理；乙巳继续弱于锚组时优先复核。
"""

        with tempfile.TemporaryDirectory() as tmp:
            original_review_notes = convert_review.REVIEW_NOTES
            convert_review.REVIEW_NOTES = Path(tmp)
            try:
                source = Path(tmp) / "2026_9_4_Friday_ReviewNote.md"
                source.write_text(markdown, encoding="utf-8")

                _, output_path = convert_review.convert_md_to_html(source)
                html = output_path.read_text(encoding="utf-8")

                for secret in ("甲辰科技", "乙巳股份", "乙巳继续", "600001", "000002"):
                    self.assertNotIn(secret, html)
                self.assertIn("持仓标的一", html)
                self.assertIn("持仓标的二", html)
                self.assertIn("代码已脱敏", html)
            finally:
                convert_review.REVIEW_NOTES = original_review_notes

    def test_public_review_text_redacts_internal_entrypoints_and_receipt_labels(self):
        text = convert_review.sanitize_public_review_text(
            "最终交易入口仍只认下一交易日 /api/ai/context.decision_gate.allowed；"
            "机器回执见 canonical red receipt（schema=market_watch.red_team.v2）；"
            "状态为 round_3_submitted，授权机械finalizer收口。"
        )

        for secret in (
            "/api/",
            "实时执行条件.allowed",
            "red receipt",
            "market_watch.red_team.v2",
            "round_3_submitted",
            "finalizer",
        ):
            self.assertNotIn(secret.lower(), text.lower())

    def test_public_review_text_redacts_runtime_field_aliases_and_candidate_ids(self):
        text = convert_review.sanitize_public_review_text(
            "8088盘前只读事实；系统 available_add_pct=0；"
            "execution_card 盘中是否有授权窗口；source_gaps=[quotes_stale]；"
            "review_source_packet；SIG-20260805-4746ae91e411；"
            "d0_input_source_date=2026-08-05。"
        )

        for secret in (
            "8088",
            "available_add_pct=0",
            "execution_card",
            "source_gaps",
            "review_source_packet",
            "SIG-20260805-4746ae91e411",
            "d0_input_source_date",
        ):
            self.assertNotIn(secret.lower(), text.lower())
        self.assertIn("盘前数据入口已隐藏", text)
        self.assertIn("新增仓位条件已脱敏", text)
        self.assertIn("规则条件记录", text)
        self.assertIn("数据缺口", text)
        self.assertIn("候选记录", text)

    def test_public_review_text_redacts_spaced_execution_prices_quantities_and_exposure(self):
        text = convert_review.sanitize_public_review_text(
            "自选池：网宿 +1.70%(14.98，弈沐两笔加仓后 T 出 2000，持仓 8000)。"
            "突破 14.99 后回踩未破；仓位/连亏：当前约39.18%，下一交易日前重新读取执行条件。"
        )

        for secret in ("14.98", "2000", "8000", "14.99", "39.18%"):
            self.assertNotIn(secret, text)
        self.assertIn("+1.70%", text)
        self.assertIn("价格已脱敏", text)
        self.assertIn("部分仓位", text)
        self.assertIn("账户比例已脱敏", text)

    def test_public_review_text_redacts_quantities_after_hidden_execution_price(self):
        text = convert_review.sanitize_public_review_text(
            "自选池：网宿 +3.19% 走强（弈沐 盘中@成交价已隐藏 +2000、"
            "盘中@成交价已隐藏 +2000 两笔加仓，合计部分仓位）。"
        )

        self.assertNotIn("+2000", text)
        self.assertIn("@成交价已隐藏 部分仓位", text)

    def test_public_review_text_redacts_position_prices_in_market_node_notes(self):
        text = convert_review.sanitize_public_review_text(
            "自选池：持仓网宿+6.58%（高点14.99回落）；长鑫+0.02%（55.00翻红，振幅53.02-56.16）；"
            "盘中新开仓中超控股+1.41%（5.76，部分仓位）。"
        )

        for secret in ("14.99", "55.00", "53.02", "56.16", "5.76"):
            self.assertNotIn(secret, text)
        self.assertIn("+6.58%", text)
        self.assertIn("+0.02%", text)

    def test_public_review_text_redacts_position_prices_without_pool_label(self):
        text = convert_review.sanitize_public_review_text(
            "早盘网宿+0.07%守住14.99结构线；"
            "午盘网宿-1.74%跌破14.99结构线（现价14.72）；"
            "尾盘三持仓全线跑输，网宿-1.87%（14.70）全天未收复14.99结构线；"
            "利欧加仓后走弱（午盘 -3.88%、5.45）。"
        )

        for secret in ("14.99", "14.72", "14.70", "5.45"):
            self.assertNotIn(secret, text)
        self.assertIn("+0.07%", text)
        self.assertIn("-1.74%", text)
        self.assertIn("价格已脱敏", text)

    def test_public_review_text_redacts_account_reconciliation_quantities(self):
        text = convert_review.sanitize_public_review_text(
            "Q5 持仓复核：position_lots + trade_records SSH 回读；"
            "长鑫关键位/利欧15000（10000+5000锁8/7）；网宿全清归零。"
        )

        for secret in ("position_lots", "trade_records", "15000", "10000", "5000", "8/7"):
            self.assertNotIn(secret.lower(), text.lower())
        self.assertIn("内部账户记录", text)
        self.assertIn("仓位数量已脱敏", text)

    def test_public_review_text_redacts_position_ratio_after_rule_record(self):
        text = convert_review.sanitize_public_review_text(
            "仓位：规则条件记录盘后约39.18%；当前无新增仓位授权。"
        )

        self.assertNotIn("39.18%", text)
        self.assertIn("账户比例已脱敏", text)

    def test_public_review_text_redacts_position_price_before_recovery_action(self):
        text = convert_review.sanitize_public_review_text(
            "三持仓仍弱：网宿14.70未收复关键位；盘中网宿14.70未收复关键位。"
        )

        self.assertNotIn("14.70", text)

    def test_public_review_text_redacts_lock_dates_without_t1_label(self):
        text = convert_review.sanitize_public_review_text(
            "持仓：可卖状态 部分仓位锁8/7。"
        )

        self.assertNotIn("8/7", text)

    def test_public_review_tables_redact_anchor_risk_thresholds(self):
        html = convert_review.html_table(
            ["主标的", "锚点用途"],
            [{"主标的": "网宿科技", "锚点用途": "验证14.99附近结构与算力同链承接"}],
        )

        self.assertNotIn("14.99", html)
        self.assertIn("关键位", html)

    def test_public_review_text_preserves_observation_counts(self):
        text = convert_review.sanitize_public_review_text("只观察3只；观察22.48继续验证。")

        self.assertIn("只观察3只", text)
        self.assertNotIn("22.48", text)

    def test_public_review_tables_redact_generic_position_fact_cells(self):
        html = convert_review.html_table(
            ["标的", "当前事实", "观察问题", "今日结论"],
            [
                {
                    "标的": "长鑫科技",
                    "当前事实": "部分仓位，成本已脱敏，收盘55.00，浮盈+1.29%",
                    "观察问题": "板块锚点能否继续承接，MA5约53.96",
                    "今日结论": "续持风险复核，不因锚点强势机械加仓",
                }
            ],
        )

        for secret in ("55.00", "53.96"):
            self.assertNotIn(secret, html)
        self.assertIn("已脱敏", html)

    def test_public_review_tables_redact_dated_holding_headers_and_evidence(self):
        html = convert_review.html_table(
            ["标的", "数量", "8/5理论可卖", "成本", "8/4收盘", "证据"],
            [{
                "标的": "长鑫科技",
                "数量": "1900",
                "8/5理论可卖": "1900",
                "成本": "54.30",
                "8/4收盘": "55.00",
                "证据": "55.00 > MA5 53.96，浮盈+1.29%",
            }],
        )

        for secret in ("1900", "54.30", "55.00", "53.96"):
            self.assertNotIn(secret, html)
        self.assertIn("+1.29%", html)

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
            convert_review.sanitize_public_review_cell("盘前数量", "800"),
            "已脱敏",
        )
        self.assertEqual(
            convert_review.sanitize_public_review_cell("收盘数量", "800"),
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

    def test_public_review_text_collapses_duplicate_hidden_detail_labels(self):
        text = convert_review.sanitize_public_review_text(
            "盘中记录（票据交易记录，FIFO关闭交易流水已隐藏）"
        )

        self.assertEqual(text.count("成交细节已隐藏"), 1)

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

    def test_public_review_text_redacts_w32_prose_price_and_amount_aliases(self):
        text = convert_review.sanitize_public_review_text(
            "清仓后卖在5.24，止损 -5050；长鑫清仓，收盘 52.48（+1.00%）。"
        )

        for secret in ("5.24", "5050", "52.48"):
            self.assertNotIn(secret, text)
        self.assertIn("价格已脱敏", text)
        self.assertIn("金额已脱敏", text)

    def test_public_review_text_redacts_compact_post_trade_price_and_position_change(self):
        text = convert_review.sanitize_public_review_text(
            "某持仓37.03是脉冲后成交，原浮亏仓从约22.6%加至约28.1%。"
        )

        for secret in ("37.03", "22.6%", "28.1%"):
            self.assertNotIn(secret, text)
        self.assertIn("价格已脱敏", text)
        self.assertIn("账户比例已脱敏", text)

    def test_public_review_text_redacts_spaced_execution_price_before_pnl(self):
        text = convert_review.sanitize_public_review_text(
            "尾盘持仓：利通电子 -5.21%续弱（今日加仓 122.20 浮亏扩大至约 -2.95 元/股）。"
        )

        self.assertNotIn("122.20", text)
        self.assertNotIn("-2.95", text)
        self.assertIn("成交价已隐藏", text)
        self.assertIn("金额已脱敏", text)

    def test_public_review_table_redacts_signed_pnl_without_currency_suffix(self):
        html = convert_review.html_table(
            ["标的", "成本", "现价", "浮盈率", "仓位", "评价"],
            [{
                "标的": "利通电子",
                "成本": "125.06",
                "现价": "118.22",
                "浮盈率": "-5.47%",
                "仓位": "17.04%",
                "评价": "今日 +745；今日 -6,507；收盘",
            }],
        )

        for secret in ("125.06", "118.22", "+745", "-6,507"):
            self.assertNotIn(secret, html)
        self.assertIn("金额已脱敏", html)

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

    def test_public_review_text_redacts_compact_quantity_and_internal_risk_shorthand(self):
        text = convert_review.sanitize_public_review_text(
            "长鑫盘中开仓1000@52.83；歌尔6000可卖，金山仅400可卖，"
            "长鑫次日解锁后再按lot回读。仓位单日+14.76pcts，"
            "两笔逆规则成交进入24h风控复核。"
        )

        for secret in ("1000", "6000", "400可卖", "次日解锁", "lot", "14.76pcts", "24h"):
            self.assertNotIn(secret.lower(), text.lower())
        self.assertIn("部分仓位@成交价已隐藏", text)
        self.assertIn("可卖状态已记录", text)
        self.assertIn("次日可卖状态复核", text)
        self.assertIn("账户比例已脱敏", text)
        self.assertIn("次日风控复核", text)

    def test_public_review_text_redacts_compact_holding_ratio_and_locked_quantity(self):
        text = convert_review.sanitize_public_review_text(
            "成交回读后持仓率50.61%；剩余仓位2000锁定，可卖量0。"
        )

        self.assertNotIn("50.61%", text)
        self.assertNotIn("2000", text)
        self.assertIn("账户比例已脱敏", text)
        self.assertIn("仓位数量已脱敏", text)

    def test_public_review_text_redacts_execution_shorthand_from_daily_review(self):
        text = convert_review.sanitize_public_review_text(
            "命中旧lot trade:150，总仓1000→700，保留400股可卖旧仓+300股T+1锁定至7/24；"
            "经济上形成反T（买102.27→卖97.41，价差-4.86元/股、税费前-1458元）；"
            "其中300股7/24解锁，7/24解锁只改变可卖数量。"
        )

        for secret in (
            "trade:150",
            "1000",
            "700",
            "7/24",
            "102.27",
            "97.41",
            "-4.86",
            "-1458",
        ):
            self.assertNotIn(secret, text)
        self.assertIn("交易流水已隐藏", text)
        self.assertIn("总仓数量已脱敏", text)
        self.assertIn("可卖状态已记录", text)
        self.assertIn("买入价已脱敏→卖出价已脱敏", text)

    def test_public_review_text_redacts_t1_position_availability(self):
        text = convert_review.sanitize_public_review_text(
            "部分仓位T+1锁定至7月22日；全部T+1锁定至7月22日。"
        )

        self.assertNotIn("锁定至7月22日", text)
        self.assertNotIn("部分仓位T+1", text)
        self.assertNotIn("全部T+1", text)
        self.assertEqual(text.count("可卖状态已记录"), 2)

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
            "本轮为observation-only，4只no_touch，process-defect检查项；"
            "process defect；human_resolution；ledger_sha256；d2_sha256；trade_review"
        )

        for secret in (
            "blocked_degraded",
            "observation_only",
            "process_defect",
            "observe",
            "no_touch",
            "exclude",
            "process-defect",
            "process defect",
            "human_resolution",
            "ledger_sha256",
            "d2_sha256",
            "trade_review",
        ):
            self.assertNotIn(secret, text.lower())
        self.assertIn("数据降级，仅观察", text)
        self.assertIn("流程缺口已记录", text)
        self.assertIn("观察 / 不参与 / 排除", text)
        self.assertIn("人工裁决", text)
        self.assertIn("内部校验字段", text)
        self.assertIn("交易复核", text)

    def test_public_review_text_redacts_internal_stage_markers(self):
        text = convert_review.sanitize_public_review_text(
            "终稿结论（stage_final=done）；stage_C=degraded_done。"
        )

        self.assertNotIn("stage_final", text)
        self.assertNotIn("stage_C", text)
        self.assertIn("终稿结论（终稿）", text)
        self.assertIn("流程状态已确认", text)

    def test_public_review_text_redacts_boolean_gate_and_freshness_fields(self):
        text = convert_review.sanitize_public_review_text(
            "add_allowed=false；freshness=`delayed`；问财delayed。"
        )

        self.assertNotIn("add_allowed", text.lower())
        self.assertNotIn("freshness", text.lower())
        self.assertNotIn("delayed", text.lower())
        self.assertIn("新增仓位条件已脱敏", text)
        self.assertIn("行情时效已记录", text)
        self.assertIn("问财数据状态已记录", text)

    def test_public_review_text_redacts_plural_ticket_field(self):
        text = convert_review.sanitize_public_review_text("tickets=0。")

        self.assertNotIn("tickets", text.lower())
        self.assertNotIn("内部执行记录s", text)
        self.assertIn("交易记录数量已隐藏", text)

    def test_public_review_text_redacts_runtime_handoff_labels_and_iso_timestamps(self):
        text = convert_review.sanitize_public_review_text(
            "状态为 ready_with_warnings，昨日 blocked，PLAN_NOT_CURRENT 不再阻断；"
            "机器预案层/人工裁决层/D3 已收口。"
            "原记录为 degraded acceptance，candidate_id=abc，候选 backfill 见 "
            "yimu_resolution_handoff.md；post_trade_reconciliation 已完成。"
            "lot_reconciliation_ok=true；valuation_complete=true；"
            "scheduled_review_fill；rotation_decisions；round_3_resolved；"
            "yangmi_red_team_round3。"
            "内部执行记录_id: TICKET-20260814-002792-0001。"
            "已于 2026-08-14T18:10:00+08:00 完成成交事实核对。"
        )

        for secret in (
            "ready_with_warnings",
            "blocked",
            "PLAN_NOT_CURRENT",
            "机器预案层",
            "人工裁决层",
            "degraded acceptance",
            "candidate_id",
            "backfill",
            "yimu_resolution_handoff.md",
            "post_trade_reconciliation",
            "lot_reconciliation_ok",
            "valuation_complete",
            "scheduled_review_fill",
            "rotation_decisions",
            "round_3_resolved",
            "yangmi_red_team_round3",
            "内部执行记录_id",
            "TICKET-20260814-002792-0001",
            "2026-08-14T18:10:00+08:00",
            "2026-08-14T盘中+盘中",
        ):
            self.assertNotIn(secret.lower(), text.lower())
        self.assertNotRegex(text, r"(?<![A-Za-z0-9_])D3(?![A-Za-z0-9_])")
        self.assertIn("日期已记录", text)
        self.assertEqual(
            convert_review.sanitize_public_review_cell(
                "性质", "post_trade_reconciliation"
            ),
            "成交事实核对",
        )

    def test_public_review_text_preserves_gap_without_placeholder_wording(self):
        text = convert_review.sanitize_public_review_text(
            "连板风险值缺源占位；大市值赚钱比例缺源脚本占位；"
            "前置版本的占位内容已由正式审阅覆盖。"
        )

        self.assertNotIn("占位", text)
        self.assertEqual(text.count("数据缺口估算"), 2)
        self.assertIn("前置版本的临时内容", text)

    def test_public_review_cells_redact_action_prices_and_monetary_pnl(self):
        self.assertEqual(
            convert_review.sanitize_public_review_cell("现价", "207.36(清仓)"),
            "已脱敏",
        )
        self.assertEqual(
            convert_review.sanitize_public_review_cell("现价", "54.99"),
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

    def test_public_review_tables_redact_close_price_for_position_rows(self):
        html = convert_review.html_table(
            ["标的", "窗口", "收盘价"],
            [
                {"标的": "长鑫科技", "窗口": "持仓", "收盘价": "54.99"},
                {"标的": "中岩大地", "窗口": "观察", "收盘价": "21.16"},
            ],
        )

        self.assertNotIn("54.99", html)
        self.assertIn("21.16", html)

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

    def test_public_review_text_redacts_spaced_trade_id_ranges(self):
        text = convert_review.sanitize_public_review_text(
            "成交事实已补录为 trade_id 241–242；交易流水不得进入公开页。"
        )

        self.assertNotIn("trade_id", text.lower())
        self.assertNotIn("241", text)
        self.assertNotIn("242", text)
        self.assertIn("交易流水已隐藏", text)

    def test_public_review_text_redacts_unqualified_execution_counts(self):
        text = convert_review.sanitize_public_review_text(
            "今日十一笔成交已回读；六笔已完成账本补录；三笔已成交事实；八笔成交事实。"
        )

        for secret in ("十一笔", "六笔", "三笔", "八笔"):
            self.assertNotIn(secret, text)
        self.assertIn("若干笔", text)

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

    def test_public_review_text_redacts_table_pnl_without_currency_suffix(self):
        text = convert_review.sanitize_public_review_text(
            "| 当日盈亏 | **+22,534（+3.36%）** | -3% 熔断 |"
        )

        self.assertNotIn("22,534", text)
        self.assertIn("金额已脱敏", text)
        self.assertIn("+3.36%", text)

    def test_public_review_text_redacts_multiplication_style_position_quantities(self):
        text = convert_review.sanitize_public_review_text(
            "盘中 @成交价已隐藏×1000、盘中 @成交价已隐藏×800，均为事后补录。"
        )

        self.assertNotIn("1000", text)
        self.assertNotIn("800", text)
        self.assertEqual(text.count("部分仓位"), 2)

    def test_public_review_text_redacts_execution_cost_comparisons(self):
        text = convert_review.sanitize_public_review_text(
            "浮盈垫 36.874 > 加仓前成本 **36.32**、站回昨日预案硬卡 **36.82**；"
            "今日 MA20 = 37.11，37.56 在其上。"
            "必须记录：站回 **36.82** 则继续减；"
            "成本口径 36.55 = 4900股加权成本，36.32 = 加仓前 3100股加权成本，"
            "此前误填 36.32。"
        )

        for secret in ("36.874", "36.55", "36.32", "36.82", "37.11", "37.56"):
            self.assertNotIn(secret, text)
        self.assertIn("浮盈垫已核对", text)
        self.assertIn("关键位", text)

    def test_public_review_text_redacts_inline_execution_terms_and_exposure_thresholds(self):
        text = convert_review.sanitize_public_review_text(
            "明日按T+1与算力扩散验证处理；最终门禁关闭；依据来自执行卡。"
            "盯盘笔记盘中，票据交易记录，FIFO关闭交易流水已隐藏，绑定账户批次。"
            "总仓位上限：维持当前20.57%附近；**仓位**：维持当前20.57%附近；"
            "不因跌超10%机械补仓。Q5 持仓复核：长鑫+1.89%/成交299.9亿；网宿-1.50%/13.82。"
        )

        for secret in (
            "T+1", "门禁", "执行卡", "票据交易记录", "FIFO", "账户批次",
            "交易流水", "20.57%", "跌超10%", "13.82",
        ):
            self.assertNotIn(secret.lower(), text.lower())
        self.assertIn("可卖状态", text)
        self.assertIn("执行条件", text)
        self.assertIn("账户比例已脱敏", text)
        self.assertIn("跌幅达到风险阈值", text)

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

    def test_public_review_text_redacts_execution_adjacent_prices_and_rule_codes(self):
        text = convert_review.sanitize_public_review_text(
            "新增中微公司，午盘390.97；日内低点370.08早于盘中买入；"
            "买入后最低383.62，收盘+2.90%，最大浮亏-3.81%。"
            "该笔直接违反CLIMAX_STOP，属gate=false自主交易；另有decision_gate=false。"
        )

        for secret in (
            "390.97", "370.08", "383.62", "CLIMAX_STOP", "gate=false", "实时门禁=false",
        ):
            self.assertNotIn(secret.lower(), text.lower())
        self.assertIn("+2.90%", text)
        self.assertIn("-3.81%", text)
        self.assertIn("风险约束", text)

    def test_public_review_text_redacts_post_action_and_pressure_prices(self):
        text = convert_review.sanitize_public_review_text(
            "金山加仓后255.08；歌尔仍守MA5(23.15>23.05)；"
            "长鑫53.99-55.03有短压。"
        )

        for secret in ("255.08", "23.15", "23.05", "53.99", "55.03"):
            self.assertNotIn(secret, text)
        self.assertIn("加仓后价格已脱敏", text)
        self.assertIn("关键位附近", text)
        self.assertIn("关键区间", text)

    def test_public_review_text_redacts_plan_ranges_and_account_exposure(self):
        text = convert_review.sanitize_public_review_text(
            "错过长鑫后，中微主逻辑用405—407/388—392验证。"
            "同为200股，长鑫38元≈0.76万(约1%账户) vs "
            "中微398.81元≈7.98万(约11.3%账户)，不可控敞口占11.3%仓位。"
        )

        for secret in (
            "405", "407", "388", "392", "200股", "38元", "0.76万",
            "1%账户", "398.81元", "7.98万", "11.3%账户", "11.3%仓位",
        ):
            self.assertNotIn(secret, text)
        self.assertIn("关键区间", text)
        self.assertIn("账户比例已脱敏", text)

    def test_public_review_text_redacts_position_first_exposure_and_t1_guidance(self):
        text = convert_review.sanitize_public_review_text(
            "**仓位**：维持约34.48%；次日以账户事实为准。\n"
            "- T+1：次日重新回读歌尔、金山可卖数量。"
        )

        for secret in ("34.48%", "T+1", "歌尔", "金山", "可卖数量"):
            self.assertNotIn(secret, text)
        self.assertIn("账户比例已脱敏", text)
        self.assertIn("可卖状态以账户事实为准", text)

    def test_public_review_cell_redacts_post_sanitized_sellable_header(self):
        self.assertEqual(
            convert_review.sanitize_public_review_cell("可卖状态已记录", "是（6000）"),
            "按账户事实复核",
        )

    def test_public_review_text_redacts_red_team_risk_price_forms(self):
        text = convert_review.sanitize_public_review_text(
            "中微尾盘393.46，浮亏收窄；若明日回调，可能再次测试388—392风险区"
            "甚至370低点。歌尔K线低点22.08 < 22.20，收盘22.87重新站上22.48；"
            "中微低点370.08未记录，买入后最低跌至370。"
        )

        for secret in ("393.46", "388", "392", "370低点", "22.08", "22.20", "22.48", "370.08", "跌至370"):
            self.assertNotIn(secret, text)
        self.assertIn("收盘22.87", text)
        self.assertIn("关键区间", text)
        self.assertIn("关键位", text)

    def test_public_review_text_redacts_ranges_before_single_price_rules(self):
        text = convert_review.sanitize_public_review_text(
            "中微看405—407/388—392与设备材料锚；歌尔连续击穿22.20；"
            "中科不应等待98.50被动触发。"
        )

        for secret in ("405", "407", "388", "392", "22.20", "98.50"):
            self.assertNotIn(secret, text)
        self.assertIn("关键区间", text)
        self.assertIn("关键位", text)

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

    def test_public_review_text_redacts_spaced_artifact_hash_audit_language(self):
        text = convert_review.sanitize_public_review_text(
            "回执审计：artifact hash 与回执自哈希均匹配。"
        )

        for secret in ("回执审计", "artifact hash", "回执自哈希"):
            self.assertNotIn(secret.lower(), text.lower())
        self.assertIn("复核说明", text)
        self.assertIn("复核记录一致", text)

    def test_public_review_text_redacts_w32_internal_aliases(self):
        text = convert_review.sanitize_public_review_text(
            "红方receipt与弈沐resolution已记录；"
            "focus_sectors/rotation_board_scan字段存在语义降级，candidate仍需回链；"
            "本周继续使用SSOT；baseline已发布且execution_plan_valid=true；"
            "最终状态为MARKET_SESSION_CLOSED，行情stale，lots=0；"
            "NeoData查询缺失，保留semiconductor_index_exact_close_unverified和"
            "quotes_stale_preopen、account_position_reconciliation_mismatch_300017。"
        )

        for secret in (
            "receipt",
            "resolution",
            "focus_sectors",
            "rotation_board_scan",
            "candidate",
            "ssot",
            "baseline",
            "execution_plan_valid",
            "market_session_closed",
            "stale",
            "lots=0",
            "neodata",
            "semiconductor_index_exact_close_unverified",
            "quotes_stale_preopen",
            "account_position_reconciliation_mismatch_300017",
        ):
            self.assertNotIn(secret, text.lower())
        self.assertIn("来源记录", text)
        self.assertIn("裁决记录", text)
        self.assertIn("板块扫描字段", text)
        self.assertIn("候选记录", text)

    def test_public_review_text_redacts_plan_price_shorthand(self):
        text = convert_review.sanitize_public_review_text(
            "歌尔看22.48/23.01与两锚，不站回22.48则降险；"
            "中国软件看35.89后确认，盘中节点复核22.48。"
        )

        for secret in ("22.48", "23.01", "35.89"):
            self.assertNotIn(secret, text)
        self.assertIn("看关键位", text)
        self.assertIn("不站回关键位", text)

    def test_public_review_text_preserves_market_stage_metrics(self):
        text = convert_review.sanitize_public_review_text(
            "尾盘情绪44.4%（较午盘50.9%持续回落），"
            "跌停家数从午盘33飙至113，较午盘33→尾盘113→收盘128持续恶化；"
            "当时买入条件不成立，仓位继续收缩。"
        )

        for metric in ("午盘50.9%", "午盘33飙至113", "午盘33→尾盘113→收盘128"):
            self.assertIn(metric, text)
        self.assertNotIn("午盘价格已脱敏", text)
        self.assertNotIn("尾盘价格已脱敏", text)

    def test_public_review_text_preserves_market_count_pairs(self):
        text = convert_review.sanitize_public_review_text(
            "当日成交已记录；早盘涨停41/跌停13，上涨4033/下跌1179；"
            "涨跌比4033/1179（较午盘3227/1944大幅改善）；"
            "涨停扩至58/跌停19；涨停86家（午盘58/19→收盘86/9）。"
        )

        for metric in (
            "涨停41/跌停13",
            "上涨4033/下跌1179",
            "较午盘3227/1944",
            "涨停扩至58/跌停19",
            "午盘58/19→收盘86/9",
        ):
            self.assertIn(metric, text)
        self.assertNotIn("关键位/", text)
        self.assertNotIn("价格已脱敏/", text)

    def test_public_review_text_redacts_action_prefixed_risk_range_as_a_unit(self):
        text = convert_review.sanitize_public_review_text(
            "具体原因未提供；事后结构显示已跌破388-392且锚点同弱。"
        )

        self.assertNotIn("388", text)
        self.assertNotIn("392", text)
        self.assertIn("跌破关键区间", text)
        self.assertNotIn("关键位-", text)

    def test_public_review_text_redacts_postfixed_execution_prices_and_average(self):
        text = convert_review.sanitize_public_review_text(
            "金山247.36买入、245.10加仓；中科93.32全清；"
            "买入均价(247.36+245.10)/2=246.23，距日内低点约4.1%。"
        )

        for secret in ("247.36", "245.10", "93.32", "246.23"):
            self.assertNotIn(secret, text)
        self.assertIn("成交价已隐藏", text)
        self.assertIn("买入均价已脱敏", text)

    def test_public_review_text_redacts_slash_separated_execution_prices(self):
        text = convert_review.sanitize_public_review_text(
            "长鑫今日加仓900股(56.96/55.10)；"
            "红方核查加仓@56.96/55.10；"
            "收盘跌破两笔加仓成本56.96/55.10。"
        )

        for secret in ("900股", "56.96", "55.10"):
            self.assertNotIn(secret, text)
        self.assertIn("成交价已隐藏", text)
        self.assertIn("成本已脱敏", text)

    def test_public_review_text_redacts_named_execution_prices_and_preserves_pct_range(self):
        text = convert_review.sanitize_public_review_text(
            "盘中买长鑫56.96 / 盘中卖歌尔23.23；"
            "半导体较高点回落5-8pct但仍在强势区；"
            "周一（8/3 T+1解锁后）再按账户事实复核。"
        )

        for secret in ("56.96", "23.23", "5-8pct", "8/3"):
            self.assertNotIn(secret, text)
        self.assertEqual(text.count("成交价已隐藏"), 2)
        self.assertIn("若干个百分点", text)
        self.assertIn("次日可卖状态复核", text)

    def test_public_review_text_redacts_internal_data_and_receipt_names(self):
        text = convert_review.sanitize_public_review_text(
            "原因字段 pnl.db reason=null；原稿无 c15_signal_ledger/d2_decision_receipt，"
            "现由 degraded_acceptance.v3 收口。"
        )

        for secret in ("pnl.db", "c15_signal_ledger", "d2_decision_receipt", "degraded_acceptance.v3"):
            self.assertNotIn(secret.lower(), text.lower())
        self.assertIn("内部账户记录", text)
        self.assertIn("候选记录", text)
        self.assertIn("裁决记录", text)
        self.assertIn("降级授权记录", text)

    def test_public_review_text_redacts_named_risk_levels_and_internal_labels(self):
        text = convert_review.sanitize_public_review_text(
            "中微388-392/中科98.50下方，中科98.50/中微388—392风险区失守，98.50修复受阻；"
            "风险复核带MA5 237.46/当日低点236.36；"
            "盘中观察388—392与设备锚，观察22.20/22.48结构；"
            "C1.5→C2→D1→D2仍为fail-closed，F-008与added_at_peak_risk仅作研究；"
            "rotation_state与candidate_codes缺失，金山T+1锁定。"
        )

        for secret in (
            "388", "392", "98.50", "237.46", "236.36", "22.20", "22.48", "C1.5", "C2",
            "D1", "D2", "fail-closed", "F-008", "peak_risk",
            "rotation_state", "candidate_codes", "T+1锁定",
        ):
            self.assertNotIn(secret.lower(), text.lower())
        self.assertIn("关键区间", text)
        self.assertIn("关键位", text)
        self.assertIn("可卖状态已记录", text)

    def test_public_review_cells_redact_numeric_trigger_thresholds(self):
        self.assertEqual(
            convert_review.sanitize_public_review_cell(
                "触发/失效", "突破35.89后缩量守住；失守34.09/33.49失效"
            ),
            "风险条件已记录（具体阈值已脱敏）",
        )
        self.assertEqual(
            convert_review.sanitize_public_review_cell(
                "触发/失效", "守MA5 9.52/MA20 9.36；转弱则失效"
            ),
            "风险条件已记录（具体阈值已脱敏）",
        )
        self.assertNotIn(
            "35.89",
            convert_review.sanitize_public_review_cell(
                "今日检查", "35.89突破与价格/时间回踩"
            ),
        )

    def test_public_review_text_redacts_spaced_single_digit_risk_levels(self):
        text = convert_review.sanitize_public_review_text(
            "中安科尚未收复 3.49、3.58 和 3.62-3.63；"
            "明日以紫光动态 MA20 约 37.31、通宇 32.5、中安科 3.36/3.28 校准。"
        )

        for secret in ("3.49", "3.58", "3.62", "3.63", "37.31", "32.5", "3.36", "3.28"):
            self.assertNotIn(secret, text)
        self.assertIn("关键位", text)

    def test_public_review_text_softens_precise_account_actions(self):
        text = convert_review.sanitize_public_review_text(
            "通宇未收回 32.5，维持清仓建议，禁止补仓；"
            "紫光先降至不高于 25%，若规则要求 20% 继续从严处理。"
        )

        for secret in ("32.5", "清仓建议", "禁止补仓", "25%", "20%"):
            self.assertNotIn(secret, text)
        self.assertIn("降低风险建议", text)
        self.assertIn("不提高风险暴露", text)

    def test_public_review_text_redacts_plan_close_prices_and_confirmation_levels(self):
        text = convert_review.sanitize_public_review_text(
            "为什么：通宇收 30.17，未完成 32.5 修复；"
            "中安科虽收 3.49，但只站上第一确认位。"
        )

        for secret in ("30.17", "32.5", "3.49"):
            self.assertNotIn(secret, text)
        self.assertIn("关键位", text)

    def test_public_review_text_redacts_one_word_price_evidence_and_account_caps(self):
        text = convert_review.sanitize_public_review_text(
            "8/28 为 3.62-3.63 一字板，9/1 早盘冲高 3.58 后回落；"
            "按实时价减至 ≤25%，持有/先降至不高于25%。"
        )

        for secret in ("3.62", "3.63", "3.58", "25%", "关键位%"):
            self.assertNotIn(secret, text)
        self.assertIn("关键区间", text)
        self.assertIn("内部集中度上限", text)

    def test_public_review_text_redacts_internal_runtime_labels(self):
        text = convert_review.sanitize_public_review_text(
            "当前 rule_state 单票上限更严，entry_leg 记为计划外。"
        )

        self.assertNotIn("rule_state", text)
        self.assertNotIn("entry_leg", text)
        self.assertIn("运行规则", text)
        self.assertIn("建仓层级", text)

    def test_public_review_cell_redacts_single_digit_composite_check_levels(self):
        text = convert_review.sanitize_public_review_cell(
            "今日检查", "3.49/3.58/3.62-3.63", position_row=True
        )

        for secret in ("3.49", "3.58", "3.62", "3.63"):
            self.assertNotIn(secret, text)
        self.assertIn("具体阈值已脱敏", text)

    def test_public_review_text_avoids_duplicate_concentration_wording(self):
        text = convert_review.sanitize_public_review_text(
            "至少先降至不高于 25%，不新增。"
        )

        self.assertNotIn("降至降低至", text)
        self.assertIn("降至内部集中度上限", text)


if __name__ == "__main__":
    unittest.main()
