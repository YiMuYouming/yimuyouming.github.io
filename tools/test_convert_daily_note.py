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


if __name__ == "__main__":
    unittest.main()
