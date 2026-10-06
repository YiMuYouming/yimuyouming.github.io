"""S7a/S7b：发布链改走新生成器，老脚本已删（审计回复 9 第二节第 2 点、
审计回复 10 第三节第 13 条）。

S7a 时老脚本还在，这里守「发布链不再提到它们」；S7b 把它们**删掉**了，
所以断言翻过来：文件必须不在，且全仓不再有任何 `import convert_review` /
`import convert_daily_note`，`sync_weekly_review` 也不许再正则改首页。

为什么要有这条：文件还在就容易被当成「还能用」——S7a 前就差点让每日公开页
又走一遍逐词脱敏。
"""

import ast
import importlib.util
import re
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent

_spec = importlib.util.spec_from_file_location("sync_portal", TOOLS / "sync_portal.py")
sync_portal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_portal)

LEGACY_SCRIPTS = ("convert_review.py", "convert_daily_note.py")
LEGACY_MODULES = ("convert_review", "convert_daily_note")


def _referenced_filenames() -> set[str]:
    """sync_portal 源码里提到的所有工具脚本文件名。"""
    tree = ast.parse((TOOLS / "sync_portal.py").read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value.endswith(".py"):
                names.add(node.value.rsplit("/", 1)[-1])
    return names


def _imports_legacy(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name in LEGACY_MODULES for alias in node.names):
                return True
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[-1] in LEGACY_MODULES:
            return True
    return False


class PublishChainSwitchedTests(unittest.TestCase):
    def test_publish_chain_no_longer_calls_the_legacy_scripts(self):
        referenced = _referenced_filenames()
        for legacy in LEGACY_SCRIPTS:
            self.assertNotIn(
                legacy, referenced,
                f"发布链里还出现 {legacy}——它已被 build_daily_page/build_home 取代",
            )

    def test_new_generators_are_wired(self):
        referenced = _referenced_filenames()
        self.assertIn("build_daily_page.py", referenced)
        self.assertIn("build_home.py", referenced)

    def test_legacy_scripts_are_gone(self):
        """S7b：老转换路径连同守着它的测试一起删掉。"""
        for legacy in LEGACY_SCRIPTS:
            self.assertFalse((TOOLS / legacy).exists(), f"{legacy} 应在 S7b 被删掉")

    def test_no_module_imports_the_legacy_converters(self):
        offenders = [
            path.name for path in sorted(TOOLS.glob("*.py"))
            if _imports_legacy(path)
        ]
        self.assertEqual([], offenders, f"还在 import 老转换器：{offenders}")

    def test_weekly_sync_no_longer_patches_the_home_page(self):
        source = (TOOLS / "sync_weekly_review.py").read_text(encoding="utf-8")
        for banned in ("rebuild_recent_review_timeline", "extract_recent_daily_cards"):
            self.assertNotIn(banned, source, f"周报同步不该再重建首页时间线（{banned}）")
        self.assertNotIn("convert_review", source, "周报同步不该再依赖老转换器")
        self.assertNotIn('PORTAL / "index.html"', source, "周报同步不该再写首页")

    def test_home_is_rendered_whole_not_patched_with_regex(self):
        source = (TOOLS / "sync_portal.py").read_text(encoding="utf-8")
        for banned in ("replace_exact_once", "re.sub(", "INDEX_SENTINEL"):
            self.assertNotIn(banned, source, f"首页不该再用 {banned} 就地改写")

    def test_daily_public_page_path_is_the_new_one(self):
        self.assertEqual(
            REPO / "daily" / "2026-10-08.html",
            sync_portal.daily_public_page("2026-10-08"),
        )

    def test_review_index_comes_from_the_live_sealed_bundle_reader(self):
        """门户取指标必须走**还活着**的入口。

        旧断言锁的是 `export_daily_bundle.py --print-review-index`，而那个
        CLI 分支在 W3 改成 daily bundle 导出时被删了（现在只收
        ``--review/--market-watch-root/--dashboard-root/--out-root``）。
        断言一条死命令等于把「门户跑不起来」固化成契约——W9 S9 实测
        ``sync_portal --dry-run`` 就在②a 直接退出码 2。

        ``review_index_fields(date)`` 这个函数还在，门户改为进程内调它。
        """
        argv = sync_portal.review_index_json("2026-09-30", REPO / "out" / "x.json")
        self.assertEqual(argv, [], "取指标不该再 shell 调一个已删的 CLI")

        entry = sync_portal.MARKET_WATCH_ROOT / "scripts" / "export_daily_bundle.py"
        source = entry.read_text(encoding="utf-8")
        self.assertNotIn(
            "--print-review-index", source,
            "被调方不该把已删的 CLI 名字留着当契约",
        )
        self.assertIn("def review_index_fields", source, "函数入口必须还在")

    def test_index_loader_uses_a_real_import_not_a_file_alias(self):
        """``load_review_index_fields`` 必须用普通 import，不能用别名加载。

        ``export_daily_bundle.py`` 顶层有
        ``from scripts.export_decision_plan import ...``。用
        ``spec_from_file_location`` 别名加载时，它所在仓的 ``scripts`` 包没被
        注册进 ``sys.modules``，那个 import 直接失败 →
        ``No module named 'scripts.export_decision_plan'``，
        ``sync_portal`` 在②a 挂掉（W9 S9 确认跑实测）。

        ★ 只约束**这一个函数**：``find_reading_sidecar`` 里的别名加载是另一回事
        （``review_reading_index.py`` 没有 ``scripts.*`` 顶层 import），别连坐。
        """
        import inspect

        source = inspect.getsource(sync_portal.load_review_index_fields)
        code = "\n".join(
            line for line in source.splitlines() if not line.strip().startswith("#")
        )
        code = code.split('"""', 2)[0] + code.split('"""', 2)[-1]  # 去掉 docstring
        self.assertNotIn(
            "spec_from_file_location", code,
            "别名加载会让 export_daily_bundle 顶层的 scripts.* import 失败",
        )
        self.assertIn("from scripts import export_daily_bundle", code)


if __name__ == "__main__":
    unittest.main()

class ReviewNoteLookupTests(unittest.TestCase):
    """Vault 里 ReviewNote 有补零和不补零两种写法，两种都要能找到。"""

    def _lookup(self, files):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "W41_第41周").mkdir()
            for name in files:
                (root / "W41_第41周" / name).write_text("x", encoding="utf-8")
            original = sync_portal.REVIEW_ROOT
            sync_portal.REVIEW_ROOT = root
            try:
                return sync_portal.find_review_note("2026-10-08")
            finally:
                sync_portal.REVIEW_ROOT = original

    def test_padded_date_is_found(self):
        found = self._lookup(["2026_10_08_Thursday_ReviewNote.md"])
        self.assertIsNotNone(found, "10-08 的笔记是补零写法，必须能找到")

    def test_unpadded_date_is_still_found(self):
        found = self._lookup(["2026_10_8_Thursday_ReviewNote.md"])
        self.assertIsNotNone(found)

    def test_absent_day_returns_none(self):
        self.assertIsNone(self._lookup(["2026_10_09_Friday_ReviewNote.md"]))
