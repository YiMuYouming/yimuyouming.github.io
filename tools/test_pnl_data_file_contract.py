"""sync_pnl_data 只写数据文件，不碰 index.html（审计回复 10 第二节第 12 条）。

首页整页由 build_home 渲染；取数脚本再去就地改 index.html，两个写入者就会
互相覆盖。2026-10-01 的定时同步在工作树里留下过一份没人认领的 index.html
改动，就是这个结构问题的信号。
"""

import ast
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
PORTAL = TOOLS.parent


def _source(name: str) -> str:
    return (TOOLS / name).read_text(encoding="utf-8")


class SyncPnlDataWritesOnlyDataTests(unittest.TestCase):
    def test_sync_pnl_data_has_no_write_target_pointing_at_index_html(self):
        """只查「写」：把 index.html 当作目标打开的代码必须没有。

        `v1/index.html` 与 `git show HEAD:index.html` 是**读**兜底（取旧入金本金
        与历史净值），S7a 之后首页整页由 build_home 渲染，这两处读留着没问题。
        """
        tree = ast.parse(_source("sync_pnl_data.py"))
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id not in {"open", "write_text"}:
                continue
            rendered = ast.dump(node.args[0]) if node.args else ""
            for keyword in node.keywords:
                if keyword.arg == "mode":
                    rendered += ast.dump(keyword.value)
            if "index.html" in rendered and "v1/" not in rendered \
                    and "HEAD:index.html" not in rendered:
                offenders.append(ast.dump(node)[:120])
        self.assertEqual([], offenders, "sync_pnl_data 不该再写 index.html")

    def test_sync_pnl_data_description_no_longer_promises_index_html(self):
        source = _source("sync_pnl_data.py")
        self.assertNotIn('description="同步 PnL + 市场快照到 portal/index.html"', source)

    def test_data_out_is_a_json_file(self):
        source = _source("sync_pnl_data.py")
        self.assertIn("data" , source)
        self.assertIn('DATA_OUT.write_text', source)

    def test_build_home_reads_the_json_by_default(self):
        source = _source("build_home.py")
        self.assertIn("PNL_DATA_FILE", source)
        self.assertIn('"data" / "pnl.json"', source)

    def test_sync_portal_passes_the_data_file_to_build_home(self):
        source = _source("sync_portal.py")
        self.assertIn('"--pnl-from", str(PNL_DATA_FILE)', source)

    def test_home_page_is_written_only_by_build_home(self):
        """首页只有一个写入者：build_home。"""
        writers = []
        for path in sorted(TOOLS.glob("*.py")):
            if path.name in {"build_home.py", "sync_pnl_data.py"}:
                continue
            text = path.read_text(encoding="utf-8")
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                        and node.func.id == "write_text" and node.args:
                    first = node.args[0]
                    target = None
                    if isinstance(first, ast.Name):
                        target = first.id
                    if target and target == "html":
                        writers.append(path.name)
        self.assertEqual([], writers, "还有别的工具在写 index.html 的 html 变量")


if __name__ == "__main__":
    unittest.main()
