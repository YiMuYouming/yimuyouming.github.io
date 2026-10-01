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
        self.assertEqual(
            json.loads(blob.replace("<\\/", "</"))["summary"]["last_date"], "2026-09-30"
        )

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


if __name__ == "__main__":
    unittest.main()
