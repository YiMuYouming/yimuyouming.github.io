"""test_redline_scope.py — W8 S5：红线只管机器生成的事实部分

开工单 W8 第二节第 6 点：业绩区、每日公开页的指标、周报事实区、研究报告照现有
规则检查，零命中才推送；**写作原文发布，不过红线**（铁律 1 的例外）。

所以扫描器必须认得出"哪一段是写作原文"——那一段整体豁免，事实部分照查。
"""

import importlib.util
import unittest
from pathlib import Path

_tool = Path(__file__).resolve().parent
sys_path = list(__import__("sys").path)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _tool / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


portal_check = _load("portal_check")

# 写作原文的标记：生成时由 build_daily_page / build_weekly_page 包上。
# 常量从生成器那一侧读，测试不自己造一个。
WRITING_CLASS = "writing-body"


def _scan_page(html: str):
    """走生产的同一条路：先去标签再扫，CSS 里的 rgba(255,255,255) 不会误报。"""
    text, _positions = portal_check._strip_tags_for_redline(html)
    return portal_check.check_redlines_static(text)


class WritingSpanTest(unittest.TestCase):
    def test_static_checker_ignores_words_inside_the_writing_span(self):
        page = (
            "<div class=\"fact\">情绪 62</div>"
            f'<div class="{WRITING_CLASS}" data-public-writing="verbatim">' 
            "这里提到门禁与执行卡——写作原文，不脱敏。</div>"
        )
        hits = _scan_page(page)
        self.assertEqual([], hits)

    def test_same_word_outside_the_span_still_blocks(self):
        page = "<div class=\"fact\">今日门禁关闭</div>"
        hits = _scan_page(page)
        self.assertTrue(any("门禁" in hit for hit in hits), hits)

    def test_hit_in_fact_section_is_reported_even_when_writing_is_present(self):
        page = (
            f'<div class="{WRITING_CLASS}" data-public-writing="verbatim">' 
            "门禁</div><div class=\"fact\">门禁</div>"
        )
        hits = _scan_page(page)
        self.assertTrue(hits, "事实区的命中必须报出来")

    def test_verbatim_body_is_not_rewritten_by_the_gate(self):
        body = "<p>原话一段：情绪 62，涨停 41 家。</p>"
        page = f'<div data-public-writing="verbatim">{body}</div>'
        self.assertEqual([], _scan_page(page))


class GeneratorMarkingTest(unittest.TestCase):
    def test_daily_page_wraps_writing_in_the_verbatim_marker(self):
        daily = _load("build_daily_page")
        page = daily.build_daily_page(
            {"情绪值": 62}, day="2026-10-08",
            writing=[{
                "path": "每日/2026-10-08.md", "kind": "daily", "date": "2026-10-08",
                "title": "10-08 手记", "status": "published", "published_at": "2026-10-08",
                "body": "<p>门禁与执行卡出现在写作里是允许的。</p>",
            }],
        )
        self.assertIn('data-public-writing="verbatim"', page)
        self.assertEqual([], _scan_page(page))

    def test_weekly_page_wraps_narrative_in_the_verbatim_marker(self):
        weekly = _load("build_weekly_page")
        page = weekly.render(
            [{"date": "2026-09-28", "index": {"情绪值": 55}}],
            {"summary": {"last_date": "2026-09-30"}, "meta": {}},
            writing=[{
                "path": "周记/W40.md", "kind": "weekly", "week": "W40",
                "status": "published", "title": "第 40 周",
                "published_at": "2026-10-01", "body": "<p>红方与回执。</p>",
            }],
            week="2026-W40",
        )
        self.assertIn('data-public-writing="verbatim"', page)
        self.assertEqual([], _scan_page(page))


if __name__ == "__main__":
    unittest.main()


class NestedDivTest(unittest.TestCase):
    def test_writing_body_with_nested_divs_stays_exempt_throughout(self):
        body = (
            '<div class="writing-body" data-public-writing="verbatim">'
            '<p>里层提一句执行卡。</p><div class="quote">回执</div>'
            '<p>再提一句门禁。</p></div><div class="fact">情绪 62</div>'
        )
        self.assertEqual([], _scan_page(body))

    def test_content_after_the_writing_div_is_scanned_again(self):
        body = (
            '<div class="writing-body" data-public-writing="verbatim">'
            '执行卡</div><div class="fact">门禁</div>'
        )
        hits = _scan_page(body)
        self.assertTrue(any("门禁" in hit for hit in hits), hits)
