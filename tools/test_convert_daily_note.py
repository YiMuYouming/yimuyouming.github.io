import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_daily_note


SAMPLE_REVIEW_NOTE = """---
date: 2026-06-26
weekday: 周五
市场状态: 冰点
赚钱效应: 差
情绪值: 14.7
上证涨幅: -2.26
涨停家数: 60
跌停家数: 30
盘后持仓: 海光信息 300股 成本价 12.34；中信证券 200股
---

## 一、当日复盘

### 一句话结论

冰点日更重要的是确认系统有没有帮人少犯错，而不是解释每一笔波动。

### 大盘全景

| 节点 | 上涨/下跌 | 结论 |
| --- | --- | --- |
| 收盘 | 768/4456 | 市场处在冰点状态 |

### 持仓与交易

| 时间 | 操作 | 备注 |
| --- | --- | --- |
| 10:04 | TICKET-123 买入海光信息300股 | 成本价 12.34 |

## 二、心得与教训

### 今日认知

**1. 冰点日先看系统门禁，再看观点**

今天指数和情绪同时下压，主观上想找反弹解释，但系统门禁把仓位和新开仓节奏压住了。

### 规则教训

- **交易前先停顿**：不要在下跌扩散时用单票逻辑替代市场状态。

## 三、次日预案

**总基调**：先观察承接，不急于恢复进攻。

### 明日观察

1. 观察指数是否止跌。
2. 明日买入海光信息 500股，突破 13.20 加仓。
3. 看主线是否从恐慌里走出合力。
"""


class ConvertDailyNoteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.daily_notes = self.root / "daily-notes"
        self.review_note = self.root / "2026_6_26_Friday_ReviewNote.md"
        self.review_note.write_text(SAMPLE_REVIEW_NOTE, encoding="utf-8")
        (self.root / "index.html").write_text(
            """<!doctype html><html><head><title>Portal</title></head><body>
<section class="section" id="reviews">
  <div class="review-stat"><span>日报归档</span><strong>65</strong><em>篇</em></div>
</section>
<section class="section workspace" id="workspace">
  <div class="workspace-grid">
    <a class="workspace-card" id="workspace-latest-review" href="review-notes/2026-06-26.html"><strong>最新复盘</strong><span>当天交易归因与次日预案</span></a>
  </div>
</section>
</body></html>""",
            encoding="utf-8",
        )
        self.original_portal = convert_daily_note.PORTAL
        self.original_daily_notes = convert_daily_note.DAILY_NOTES
        convert_daily_note.PORTAL = self.root
        convert_daily_note.DAILY_NOTES = self.daily_notes

    def tearDown(self):
        convert_daily_note.PORTAL = self.original_portal
        convert_daily_note.DAILY_NOTES = self.original_daily_notes
        self.tmp.cleanup()

    def test_generates_public_daily_note_page_with_six_reading_sections(self):
        note = convert_daily_note.convert_review_to_daily_note(
            self.review_note,
            user_feeling="今天真实感受是想解释下跌，但系统提醒先接受冰点和门禁。",
        )

        html_path = self.daily_notes / "2026-06-26.html"
        html = html_path.read_text(encoding="utf-8")

        self.assertEqual(note["date"], "2026-06-26")
        self.assertIn("冰点日先看系统门禁", html)
        self.assertIn("今日一句话", html)
        self.assertIn("今日市场状态", html)
        self.assertIn("今日一个认知", html)
        self.assertIn("系统今天做了什么", html)
        self.assertIn("明日只看什么", html)
        self.assertIn("边界声明", html)
        self.assertIn("个人交易系统复盘与认知记录，不构成投资建议。", html)

    def test_daily_note_uses_reading_card_design_classes(self):
        convert_daily_note.convert_review_to_daily_note(self.review_note)

        html = (self.daily_notes / "2026-06-26.html").read_text(encoding="utf-8")

        for class_name in [
            "daily-note-shell",
            "note-hero",
            "note-thesis",
            "note-market-aside",
            "note-cognition-card",
            "note-system-voice",
            "note-watch-list",
        ]:
            self.assertIn(class_name, html)

    def test_daily_note_extracts_numbered_bold_colon_cognition(self):
        review_note = self.root / "2026_6_29_Monday_ReviewNote.md"
        review_note.write_text(
            SAMPLE_REVIEW_NOTE.replace(
                "date: 2026-06-26",
                "date: 2026-06-29",
            )
            .replace(
                "### 今日认知\n\n**1. 冰点日先看系统门禁，再看观点**\n\n今天指数和情绪同时下压，主观上想找反弹解释，但系统门禁把仓位和新开仓节奏压住了。",
                "### 今日认知\n\n1. **不追错过的目标票**：南大、雅克早盘冲高，但目标在池子里不等于可以买，必须等缩量回踩或平台承接。",
            )
            .replace(
                "1. 观察指数是否止跌。",
                "1. **持仓第一优先级**：若跌破60m MA10 120.82并拉不回，则先保护利润。",
            )
            .replace(
                "3. 看主线是否从恐慌里走出合力。",
                "3. **半导体/电子是第一观察板块**：候选补入澜起科技、中微公司、聚和材料；不追开盘加速。",
            ),
            encoding="utf-8",
        )

        convert_daily_note.convert_review_to_daily_note(review_note)

        html = (self.daily_notes / "2026-06-29.html").read_text(encoding="utf-8")
        self.assertIn("不追错过的目标票", html)
        self.assertIn("目标在池子里不等于可以买", html)
        self.assertNotIn("先把当天经验压成可复用原则", html)
        self.assertNotIn("南大", html)
        self.assertNotIn("雅克", html)
        self.assertNotIn("澜起科技", html)
        self.assertNotIn("中微公司", html)
        self.assertNotIn("聚和材料", html)
        self.assertNotIn("120.82", html)

    def test_daily_note_skips_portal_guidance_and_extracts_bracket_cognition(self):
        review_note = self.root / "2026_6_30_Tuesday_ReviewNote.md"
        review_note.write_text(
            SAMPLE_REVIEW_NOTE.replace("date: 2026-06-26", "date: 2026-06-30")
            .replace(
                "冰点日更重要的是确认系统有没有帮人少犯错，而不是解释每一笔波动。",
                "> **Portal 今日一句话来源**：一句话讲清当日市场状态和系统判断；不写 ticket、股数、成本、精确买卖指令。\n\n市场从竞价低迷修复为科技主升，系统顺势降低非主线暴露。",
            )
            .replace(
                "### 今日认知\n\n**1. 冰点日先看系统门禁，再看观点**\n\n今天指数和情绪同时下压，主观上想找反弹解释，但系统门禁把仓位和新开仓节奏压住了。",
                "### 今日认知\n\n1. [认知] 主线强势股的买点不是越强越追，而是缩量回踩或强横守住关键位时建仓。\n2. [教训] 二笔不是缩量回踩，而是追趋势加速的小仓试探。",
            ),
            encoding="utf-8",
        )

        convert_daily_note.convert_review_to_daily_note(review_note)

        html = (self.daily_notes / "2026-06-30.html").read_text(encoding="utf-8")
        self.assertIn("市场从竞价低迷修复为科技主升", html)
        self.assertIn("主线强势股的买点不是越强越追", html)
        self.assertNotIn("Portal 今日一句话来源", html)
        self.assertNotIn("先把当天经验压成可复用原则", html)
        self.assertNotIn("不写 ticket", html)

    def test_daily_note_filters_sensitive_execution_details(self):
        convert_daily_note.convert_review_to_daily_note(self.review_note)

        html = (self.daily_notes / "2026-06-26.html").read_text(encoding="utf-8")

        self.assertNotIn("TICKET-123", html)
        self.assertNotIn("300股", html)
        self.assertNotIn("500股", html)
        self.assertNotIn("成本价", html)
        self.assertNotIn("13.20", html)
        self.assertNotIn("明日买入", html)
        self.assertNotIn("药明康德", html)
        self.assertNotIn("中信证券", html)
        self.assertNotIn("海光信息", html)
        self.assertIn("-2.26%", html)
        self.assertIn("持仓状态以公开摘要呈现", html)

    def test_daily_note_redacts_cost_lines_from_total_tone_fallback(self):
        review_note = self.root / "2026_7_1_Wednesday_ReviewNote.md"
        review_note.write_text(
            SAMPLE_REVIEW_NOTE.replace("date: 2026-06-26", "date: 2026-07-01")
            .replace("weekday: 周五", "weekday: 周三")
            .replace(
                "**总基调**：先观察承接，不急于恢复进攻。",
                "**总基调**：太极为主线强分歧回封后的核心持仓，聚和材料按计划外仓处理，先看能否收回 134.40 成本线并获得江丰/金宏无负反馈确认，不能在成本下摊平。",
            )
            .replace(
                "### 明日观察\n\n1. 观察指数是否止跌。\n2. 明日买入海光信息 500股，突破 13.20 加仓。\n3. 看主线是否从恐慌里走出合力。",
                "",
            ),
            encoding="utf-8",
        )

        convert_daily_note.convert_review_to_daily_note(review_note)

        html = (self.daily_notes / "2026-07-01.html").read_text(encoding="utf-8")
        self.assertNotIn("134.40", html)
        self.assertNotIn("成本线", html)
        self.assertNotIn("成本下", html)
        self.assertNotIn("聚和材料", html)
        self.assertNotIn("聚和", html)
        self.assertNotIn("标的/标的", html)
        self.assertIn("标的按计划外仓处理", html)

    def test_daily_note_collapses_multiple_position_names(self):
        review_note = self.root / "2026_7_2_Thursday_ReviewNote.md"
        review_note.write_text(
            SAMPLE_REVIEW_NOTE.replace("date: 2026-06-26", "date: 2026-07-02")
            .replace("weekday: 周五", "weekday: 周四")
            .replace(
                "**总基调**：先观察承接，不急于恢复进攻。",
                "**总基调**：先降风险、再验证修复；太极/海兰信/聚和全部重新走触发/失效，不因昨日身份自动延续。",
            )
            .replace(
                "### 明日观察\n\n1. 观察指数是否止跌。\n2. 明日买入海光信息 500股，突破 13.20 加仓。\n3. 看主线是否从恐慌里走出合力。",
                "",
            ),
            encoding="utf-8",
        )

        convert_daily_note.convert_review_to_daily_note(review_note)

        html = (self.daily_notes / "2026-07-02.html").read_text(encoding="utf-8")
        self.assertNotIn("太极", html)
        self.assertNotIn("海兰信", html)
        self.assertNotIn("聚和", html)
        self.assertNotIn("标的/标的", html)
        self.assertIn("持仓标的全部重新走触发/失效", html)

    def test_updates_daily_notes_archive_and_home_without_review_count_drift(self):
        convert_daily_note.convert_review_to_daily_note(self.review_note)
        convert_daily_note.convert_review_to_daily_note(self.review_note)

        archive = (self.daily_notes / "index.html").read_text(encoding="utf-8")
        home = (self.root / "index.html").read_text(encoding="utf-8")

        self.assertIn("每日市场手记", archive)
        self.assertIn("2026-06-26.html", archive)
        self.assertEqual(archive.count('href="2026-06-26.html"'), 1)
        self.assertIn('id="daily-notes"', home)
        self.assertIn("daily-notes/2026-06-26.html?from=daily-notes", home)
        self.assertIn("daily-notes/index.html", home)
        self.assertIn("<strong>65</strong><em>篇</em>", home)

    def test_home_secondary_daily_note_card_keeps_summary_and_design_class(self):
        convert_daily_note.convert_review_to_daily_note(self.review_note)
        review_note = self.root / "2026_6_29_Monday_ReviewNote.md"
        review_note.write_text(
            SAMPLE_REVIEW_NOTE.replace("date: 2026-06-26", "date: 2026-06-29")
            .replace(
                "冰点日更重要的是确认系统有没有帮人少犯错，而不是解释每一笔波动。",
                "市场进入需要降速观察的一天里，先确认系统约束，再处理主观判断。",
            )
            .replace(
                "冰点日先看系统门禁，再看观点",
                "不追错过的目标票",
            ),
            encoding="utf-8",
        )

        convert_daily_note.convert_review_to_daily_note(review_note)

        home = (self.root / "index.html").read_text(encoding="utf-8")
        self.assertIn('class="daily-note-mini daily-note-secondary"', home)
        self.assertIn("冰点日更重要的是确认系统有没有帮人少犯错", home)
        self.assertIn("daily-note-mini-tag", home)


if __name__ == "__main__":
    unittest.main()
