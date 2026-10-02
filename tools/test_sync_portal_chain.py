"""S7a：发布链已经改走新生成器，老脚本不再被调用（审计回复 9 第二节第 2 点）。

老脚本这一轮**不删**——先换链、观察两个交易日，S7b 才删。这里守的是
「发布链不再提到它们」，这样谁把老路径悄悄接回去，测试当场红。

为什么要有这条：`convert_review.py` / `convert_daily_note.py` 还在仓库里，
文件还在就容易被当成「还能用」——本轮就差点让每日公开页又走一遍逐词脱敏。
"""

import ast
import importlib.util
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent

_spec = importlib.util.spec_from_file_location("sync_portal", TOOLS / "sync_portal.py")
sync_portal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_portal)

LEGACY_SCRIPTS = ("convert_review.py", "convert_daily_note.py")


def _referenced_filenames() -> set[str]:
    """sync_portal 源码里提到的所有工具脚本文件名。"""
    tree = ast.parse((TOOLS / "sync_portal.py").read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value.endswith(".py"):
                names.add(node.value.rsplit("/", 1)[-1])
    return names


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

    def test_legacy_scripts_are_still_on_disk(self):
        """老脚本这一轮不删，S7b 才删。留着是为了出问题能直接退回老链。"""
        for legacy in LEGACY_SCRIPTS:
            self.assertTrue((TOOLS / legacy).is_file(), f"{legacy} 不该在 S7a 被删掉")

    def test_home_is_rendered_whole_not_patched_with_regex(self):
        source = (TOOLS / "sync_portal.py").read_text(encoding="utf-8")
        for banned in ("replace_exact_once", "re.sub(", "INDEX_SENTINEL"):
            self.assertNotIn(banned, source, f"首页不该再用 {banned} 就地改写")

    def test_daily_public_page_path_is_the_new_one(self):
        self.assertEqual(
            REPO / "daily" / "2026-10-08.html",
            sync_portal.daily_public_page("2026-10-08"),
        )

    def test_review_index_comes_from_the_sealed_bundle_cli(self):
        argv = sync_portal.review_index_json("2026-09-30", REPO / "out" / "x.json")
        self.assertTrue(argv[0].endswith("export_daily_bundle.py"))
        self.assertIn("--print-review-index", argv)
        self.assertIn("2026-09-30", argv)


if __name__ == "__main__":
    unittest.main()