"""test_build_home.py — W8 S2：整页渲染首页

两条契约：
1. **业绩只算一处**：`build_home.py` 不含任何业绩公式，KPI/曲线/明细由
   `static/pnl-engine.js` 在浏览器里算（审计回复 1 第一节）。这里断言服务端
   没有第二份实现，避免以后有人只改其中一份。
2. **模板与引擎对得上**：模板提供的 DOM id/class/data 属性必须是引擎找的那些，
   否则页面数字永远停在 `—`。
"""

import importlib.util
import json
import re
import unittest
import tempfile
from inspect import signature
from copy import deepcopy
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
TEMPLATE = WORKSPACE / "templates" / "home.html"
ENGINE = WORKSPACE / "static" / "pnl-engine.js"

_spec = importlib.util.spec_from_file_location(
    "build_home", WORKSPACE / "tools" / "build_home.py"
)
build_home = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_home)


def current_pnl_data() -> dict:
    html = (WORKSPACE / "index.html").read_text(encoding="utf-8")
    match = re.search(r"var PNL_DATA = (\{.*?\});\s*</script>", html, flags=re.DOTALL)
    assert match, "现网首页没有 PNL_DATA"
    return json.loads(match.group(1))


class PeriodReviewLinksTest(unittest.TestCase):
    def _render(self, reports):
        self.assertIn('period_reviews', signature(build_home.render_home).parameters)
        return build_home.render_home(
            {'summary': {'last_date': '2026-10-30'}, 'all_sh': {'portfolio': []}},
            period_reviews={'reports': reports},
        )

    def test_two_direct_links_follow_income_heading_before_the_metrics(self):
        page = self._render([
            {'kind': 'monthly', 'id': '2026-10', 'start': '2026-10-08', 'end': '2026-10-30'},
            {'kind': 'weekly', 'id': '2026-W44', 'start': '2026-10-26', 'end': '2026-10-30'},
        ])
        nav = re.search(r'<nav class="period-review-links"[^>]*>(.*?)</nav>', page, re.S)
        self.assertIsNotNone(nav)
        self.assertEqual(len(re.findall(r'<a\b', nav[1])), 2)
        self.assertIn('review-notes/weekly-2026-10-26_10-30.html', nav[1])
        self.assertIn('review-notes/monthly-2026-10-08_10-30.html', nav[1])
        self.assertIn('最新周报 W44', nav[1])
        self.assertIn('10月月报', nav[1])
        self.assertLess(page.index('id="pnl-h"'), nav.start())
        self.assertLess(nav.end(), page.index('<div class="glabel"'))
        self.assertNotIn('摘要', nav[1])

    def test_latest_periods_are_selected_by_date_regardless_of_input_order(self):
        page = self._render([
            {'kind': 'weekly', 'id': '2026-W45', 'start': '2026-11-02', 'end': '2026-11-06'},
            {'kind': 'monthly', 'id': '2026-10', 'start': '2026-10-08', 'end': '2026-10-30'},
            {'kind': 'weekly', 'id': '2026-W44', 'start': '2026-10-26', 'end': '2026-10-30'},
            {'kind': 'monthly', 'id': '2026-11', 'start': '2026-11-02', 'end': '2026-11-30'},
        ])
        nav = re.search(r'<nav class="period-review-links"[^>]*>(.*?)</nav>', page, re.S)[1]
        self.assertIn('weekly-2026-11-02_11-06.html', nav)
        self.assertIn('monthly-2026-11-02_11-30.html', nav)
        self.assertNotIn('weekly-2026-10-26', nav)
        self.assertNotIn('monthly-2026-10-08', nav)

    def test_no_reports_means_no_empty_row(self):
        self.assertNotIn('<nav class="period-review-links"', self._render([]))


class SingleImplementationTest(unittest.TestCase):
    """审计回复 1 第一节：同一个公式只允许一份实现。"""

    def test_build_home_has_no_performance_math(self):
        source = (WORKSPACE / "tools" / "build_home.py").read_text(encoding="utf-8")
        for banned in ("def twr_chain", "def max_drawdown", "def performance_kpis",
                       "toFixed", "round(", "1 + (value"):
            self.assertNotIn(banned, source, f"服务端不应再实现业绩公式：{banned}")

    def test_build_home_has_no_kpi_slots(self):
        source = (WORKSPACE / "tools" / "build_home.py").read_text(encoding="utf-8")
        for slot in ("{{TWR}}", "{{ALPHA}}", "{{MAXDD}}", "{{ASSET}}", "{{DEPOSIT}}"):
            self.assertNotIn(slot, source, f"服务端不应再填 KPI 占位符：{slot}")
        template = TEMPLATE.read_text(encoding="utf-8")
        for slot in ("{{TWR}}", "{{ALPHA}}", "{{MAXDD}}", "{{ASSET}}"):
            self.assertNotIn(slot, template)

    def test_engine_is_the_only_performance_implementation(self):
        engine = ENGINE.read_text(encoding="utf-8")
        self.assertIn("function twrChain", engine)
        self.assertIn("function calcDD", engine)

    def test_only_the_engine_is_loaded_by_the_rendered_page(self):
        """渲染出来的页面只能加载一个业绩实现。

        pnl-chart.js 是更早的一版实现（另一套元素 id、另一套数据键），现网首页
        早就不加载它了。S2 把它从页面里摘掉；S7 弈沐拍板后删文件本身。这里断言
        "页面不加载它"，而不是假装文件已经删了。
        """
        page = build_home.render_home(
            {"summary": {"last_date": "2026-09-30"}, "all_sh": {"portfolio": []}},
            writing_index={}, reports={}, archive_groups={},
        )
        self.assertNotIn("pnl-chart.js", page)
        self.assertEqual(page.count("pnl-engine.js"), 1)


class TemplateEngineContractTest(unittest.TestCase):
    """模板必须提供引擎要找的 DOM 钩子，否则数字停在 —。"""

    def setUp(self):
        self.template = TEMPLATE.read_text(encoding="utf-8")
        self.engine = ENGINE.read_text(encoding="utf-8")

    def test_every_engine_element_id_exists_in_the_template(self):
        # 既要抓 $('id') 也要抓 setKPI('id')：后者不经过 $()，漏了会让 KPI 停在破折号
        ids = sorted(set(re.findall(r"\$\('(pnl_[a-z_]+)'\)", self.engine))
                     | set(re.findall(r"setKPI\('(pnl_[a-z_]+)'", self.engine)))
        self.assertGreater(len(ids), 12, "引擎引用的 id 太少，正则可能失效")
        missing = [name for name in ids if f'id="{name}"' not in self.template]
        self.assertEqual(missing, [], f"模板缺少引擎需要的 id：{missing}")

    def test_engine_button_selectors_match_the_rendered_page(self):
        # 按钮由 build_home.py 按 {{INDEX_BUTTONS}}/{{PERIOD_BUTTONS}} 生成，
        # 所以契约要看渲染结果，不是模板原文。
        page = build_home.render_home(
            {"summary": {"last_date": "2026-09-30"}, "all_sh": {"portfolio": []}},
            writing_index={}, reports={}, archive_groups={},
        )
        for cls in ("pnl-period", "pnl-idx-btn"):
            self.assertIn(f".{cls}", self.engine, f"引擎找 .{cls}")
            self.assertIn(cls, page, f"渲染结果里没有 {cls}")
        self.assertIn('data-p="', page)
        self.assertIn('data-idx="', page)
        # 激活态用 active 类（引擎 add/remove 的就是它）
        self.assertIn("pnl-period active", page)
        self.assertIn("pnl-idx-btn active", page)

    def test_engine_only_reads_pnl_data_and_writing_index(self):
        self.assertIn("PNL_DATA", self.template)
        self.assertIn("static/pnl-engine.js", self.template)

    def test_template_has_no_in_place_regex_slots(self):
        self.assertNotIn("PNL_DATA_START", self.template)
        self.assertNotIn("PNL_DATA_END", self.template)


class RenderTest(unittest.TestCase):
    def _render(self, writing=None, pnl=None):
        return build_home.render_home(
            pnl or current_pnl_data(),
            writing_index=writing or {"schema": "writing_index.v1", "entries": [], "issues": []},
            reports={},
            archive_groups={"weeks": {}},
            version="abc1234",
            as_of="2026-09-30",
        )

    def test_render_is_deterministic(self):
        self.assertEqual(self._render(), self._render())

    def test_no_unfilled_slots(self):
        self.assertNotRegex(self._render(), r"\{\{[A-Z_]+\}\}")

    def test_kpi_placeholders_ship_as_dashes(self):
        html = self._render()
        for name in ("pnl_twr", "pnl_alpha", "pnl_maxdd", "pnl_asset"):
            self.assertIn(f'id="{name}">—<', html)

    def test_pnl_data_is_embedded_verbatim(self):
        html = self._render()
        blob = re.search(r"var PNL_DATA = (\{.*?\});", html, flags=re.DOTALL).group(1)
        payload = json.loads(blob.replace("<\\/", "</"))
        # 守的是「首页内嵌的那份与数据源逐字一致」。日期由 ① 每天刷新，
        # 写死某一天只会让明天再红一次——比这条断言要守的东西更脆。
        source = current_pnl_data()
        self.assertEqual(source, payload)

    def test_no_writing_means_no_placeholder_text(self):
        html = self._render()
        self.assertNotIn("即将上线", html)
        self.assertNotIn("敬请期待", html)
        # 没有已发布写作时，下半区只剩三个小标题，不出列表元素、不出占位文案。
        # 断言用元素标记而不是类名：CSS 里也有 .writing-list 这类选择器。
        self.assertNotIn('<ul class="writing-list">', html)
        self.assertNotIn('<span class="writing-date">', html)

    def test_published_writing_renders(self):
        html = self._render(writing={
            "schema": "writing_index.v1",
            "entries": [{
                "path": "每日/2026-10-08.md", "kind": "daily", "date": "2026-10-08",
                "title": "10-08 手记", "series": "", "status": "published",
                "published_at": "2026-10-08", "week": "", "sha256": "0" * 64,
            }],
            "issues": [],
        })
        self.assertIn("10-08 手记", html)
        self.assertIn('<ul class="writing-list">', html)

    def test_script_payload_cannot_close_the_script_tag(self):
        html = build_home.render_home(
            {"summary": {"last_date": "2026-09-30"}, "all_sh": {"portfolio": []},
             "note": "</script><script>alert(1)</script>"},
            writing_index={}, reports={}, archive_groups={},
        )
        self.assertNotIn("</script><script>alert(1)", html)

    def test_home_daily_preview_shows_three_latest_and_links_to_all(self):
        entries = [
            {"date": f"2026-11-{day:02d}", "title": f"手记 {day}",
             "href": f"daily/2026-11-{day:02d}.html", "series": "观察记录"}
            for day in range(1, 16)
        ]
        original = deepcopy(entries)
        page = build_home.render_writing(
            {"essay": [], "daily": entries, "weekly": []}, None,
        )
        links = re.findall(r'<a[^>]+href="([^"]+)"', page)
        self.assertEqual(links, ["daily/index.html"] + [item["href"] for item in reversed(entries[-3:])])
        for item in entries[-3:]:
            self.assertIn(f'>{item["title"]}<', page)
            self.assertIn(item["date"], page)
        self.assertEqual(page.count('>观察记录<'), 3)
        self.assertEqual(entries, original)

    def test_daily_index_preserves_all_entries_newest_first(self):
        entries = [{"kind": "daily", "date": f"2026-11-{day:02d}",
                    "title": f"手记 {day}", "series": "观察记录"}
                   for day in range(1, 16)]
        original = deepcopy(entries)
        self.assertTrue(callable(getattr(build_home, "render_daily_index", None)),
                        "更多入口需要完整手记页生成器")
        page = build_home.render_daily_index({"entries": entries})
        links = re.findall(r'class="writing-row" href="([^"]+)"', page)
        self.assertEqual(links, [f'2026-11-{day:02d}.html' for day in range(15, 0, -1)])
        for item in entries:
            self.assertIn(f'>{item["title"]}<', page)
            self.assertIn(item["date"], page)
        self.assertEqual(page.count('>观察记录<'), 15)
        self.assertEqual(entries, original)

    def test_home_build_also_generates_and_checks_daily_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pnl = root / "pnl.json"
            pnl.write_text(json.dumps({"summary": {}, "all_sh": {"portfolio": []}}))
            writing = root / "writing.json"
            writing.write_text(json.dumps({"entries": [
                {"kind": "daily", "date": "2026-10-29", "title": "最新手记"}]}))
            args = ["--pnl-from", str(pnl), "--writing-index", str(writing),
                    "--out", str(root / "index.html")]
            self.assertEqual(build_home.main(args), 0)
            archive = root / "daily" / "index.html"
            self.assertTrue(archive.is_file(), "正常首页生成必须同时生成更多页")
            self.assertEqual(build_home.main(args + ["--check"]), 0)
            archive.unlink()
            self.assertEqual(build_home.main(args + ["--check"]), 1,
                             "更多页缺失时不能报告生成物已齐")

    def test_daily_list_without_link_keeps_its_text(self):
        page = build_home.render_writing(
            {"essay": [], "daily": [{"date": "2026-11-01", "title": "待补链接的手记",
                                       "series": "连续观察"}], "weekly": []}, None,
        )
        self.assertIn("待补链接的手记", page)
        self.assertIn("2026-11-01", page)
        self.assertIn("连续观察", page)
        self.assertNotIn('href="None"', page)


if __name__ == "__main__":
    unittest.main()


class HomeDuplicationTests(unittest.TestCase):
    """审计回复 3 第三节第 3 条：首页同一个数重复太多。"""

    def _render(self):
        return build_home.render_home(
            current_pnl_data(),
            writing_index={"schema": "writing_index.v1", "entries": [], "issues": []},
            reports={}, archive_groups={"weeks": {}},
            version="abc1234", as_of="2026-09-30",
        )

    def test_summary_cards_live_inside_the_pnl_drawer(self):
        """曲线下方那组汇总卡与「总体记录」四格重复，收进「损益明细」抽屉。"""
        page = self._render()
        drawer = page[page.index("<details class=\"drawer\">"):page.index("</details>")]
        self.assertIn('id="pnl_summary"', drawer,
                      "pnl_summary 应当在损益明细抽屉里")
        self.assertNotIn('id="pnl_summary"', page[:page.index("<details class=\"drawer\">")],
                         "pnl_summary 不该再留在抽屉外面")

    def test_total_deposit_is_two_decimals(self):
        """累计入金原来是 711,059.225，三位小数看着像没写完。"""
        engine = ENGINE.read_text(encoding="utf-8")
        self.assertIn("minimumFractionDigits: 2", engine)
        self.assertNotIn("'累计入金 ' + ((m.total_deposit || 200000).toLocaleString())",
                        engine)

    def test_drawdown_label_sits_above_the_trough_not_on_the_end_label(self):
        """最大回撤的谷底常常就是曲线末端，标签要错开。"""
        engine = ENGINE.read_text(encoding="utf-8")
        block = engine[engine.index("var ddLabel = "):engine.index("canvas._chartData")]
        self.assertIn("labY", block, "回撤标签需要单独的纵向偏移")
        # 谷底上方是曲线本身、下方是空白，所以默认放下方，放不下才翻上去
        self.assertIn("fitsBelow", block)
        self.assertIn("below + 12 <= PAD.t + ch", block)
