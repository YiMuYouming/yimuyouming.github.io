"""test_sync_weekly_dry_run.py — W8 S4：sync_weekly_review 加 --dry-run

`--dry-run` 只打印要改什么，不写盘。写完盘前能先看清它会动哪些文件的哪些行。
"""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_tool = Path(__file__).resolve().parent
sys.path.insert(0, str(_tool))                   # sync_weekly_review 与本文件同目录
_spec = importlib.util.spec_from_file_location("srw", _tool / "sync_weekly_review.py")
srw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(srw)


class ParserTest(unittest.TestCase):
    def test_dry_run_flag_exists_and_defaults_off(self):
        args = srw.build_parser().parse_args(["sync", "--page", "x.html"])
        self.assertFalse(args.dry_run)
        args = srw.build_parser().parse_args(["sync", "--page", "x.html", "--dry-run"])
        self.assertTrue(args.dry_run)


class DryRunTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _site(self):
        (self.root / "review-notes").mkdir(parents=True)
        (self.root / "index.html").write_text("<html>home</html>", encoding="utf-8")
        (self.root / "review-notes" / "index.html").write_text(
            "<html>archive</html>", encoding="utf-8")

    def test_dry_run_reports_without_touching_anything(self):
        self._site()
        before = {
            path: path.read_bytes()
            for path in sorted(self.root.rglob("*.html"))
        }
        code = srw.main(["sync", "--page",
                         str(self.root / "review-notes" / "weekly-2026-09-28_09-30.html"),
                         "--root", str(self.root), "--dry-run"])
        # 页面不存在时 dry-run 仍要如实报缺，不写盘
        self.assertEqual(code, 1)
        for path, blob in before.items():
            self.assertEqual(path.read_bytes(), blob, f"{path} 被 dry-run 改了")

    def test_missing_page_is_a_clear_error(self):
        self._site()
        self.assertEqual(1, srw.main([
            "sync", "--page", str(self.root / "review-notes" / "weekly-2026-09-28_09-30.html"),
            "--root", str(self.root), "--dry-run"]))


if __name__ == "__main__":
    unittest.main()
