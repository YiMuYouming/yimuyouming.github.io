import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_portal


class _StubRun:
    """记录子进程调用并按脚本名决定退出码，避免测试真的触网或写盘。"""

    def __init__(self, fail_on: str | None = None) -> None:
        self.calls: list[list[str]] = []
        self.fail_on = fail_on

    def __call__(self, command, cwd=None, **kwargs):
        self.calls.append([str(item) for item in command])
        code = 1 if self.fail_on and self.fail_on in " ".join(self.calls[-1]) else 0
        return mock.Mock(returncode=code)

    def scripts(self) -> list[str]:
        return [Path(call[1]).name for call in self.calls]


def _run_main(argv: list[str], stub: _StubRun) -> tuple[int, str]:
    buffer = io.StringIO()
    with mock.patch.object(sync_portal.subprocess, "run", stub), contextlib.redirect_stdout(
        buffer
    ):
        code = sync_portal.main(argv)
    return code, buffer.getvalue()


class PortalSyncEntryTests(unittest.TestCase):
    def test_finds_review_note_by_trading_date(self):
        note = sync_portal.find_review_note("2026-09-15")

        self.assertIsNotNone(note, "应当按交易日定位到 Vault 的 ReviewNote")
        self.assertIn("2026_9_15", note.name)
        self.assertEqual(note.name, "2026_9_15_Tuesday_ReviewNote.md")

    def test_unknown_date_has_no_review_note(self):
        self.assertIsNone(sync_portal.find_review_note("1999-01-01"))

    def test_rejects_malformed_date_before_any_step_runs(self):
        """参数错误必须在触网或写盘之前返回，否则定时任务会白跑一轮。"""
        self.assertEqual(1, sync_portal.main(["--date", "2026/09/15"]))

    def test_home_pnl_reader_reports_latest_date(self):
        """回读用于确认第一步真的生效，而不是只看子进程退出码。"""
        last_date = sync_portal.read_pnl_last_date()

        self.assertIsNotNone(last_date)
        self.assertRegex(last_date, r"^\d{4}-\d{2}-\d{2}$")


class PortalSyncOrderTests(unittest.TestCase):
    """三条链必须按 首页数据 → 复盘详情页 → 手记 固定顺序跑。"""

    def test_real_run_executes_three_chains_in_order(self):
        stub = _StubRun()

        code, out = _run_main(["--date", "2026-09-15"], stub)

        self.assertEqual(0, code, out)
        self.assertEqual(
            ["sync_pnl_data.py", "convert_review.py", "convert_daily_note.py"],
            stub.scripts(),
            "复盘详情页曾经整条链漏跑，顺序与完整性都要盯住",
        )
        self.assertNotIn("--dry-run", " ".join(stub.calls[1]))

    def test_dry_run_covers_all_three_steps_without_running_convert_review(self):
        """convert_review.py 没有 --dry-run：预演时只能不执行，绝不能写盘。"""
        stub = _StubRun()

        code, out = _run_main(["--date", "2026-09-15", "--dry-run"], stub)

        self.assertEqual(0, code, out)
        self.assertIn("① 首页数据", out)
        self.assertIn("② 复盘详情页", out)
        self.assertIn("③ 每日市场手记", out)
        self.assertLess(out.index("① 首页数据"), out.index("② 复盘详情页"))
        self.assertLess(out.index("② 复盘详情页"), out.index("③ 每日市场手记"))
        self.assertEqual(
            ["sync_pnl_data.py", "convert_daily_note.py"],
            stub.scripts(),
            "预演不得真的执行 convert_review.py",
        )
        self.assertIn("[dry-run]", out)

    def test_skip_review_leaves_the_other_two_chains_running(self):
        stub = _StubRun()

        code, out = _run_main(["--date", "2026-09-15", "--skip-review"], stub)

        self.assertEqual(0, code, out)
        self.assertEqual(
            ["sync_pnl_data.py", "convert_daily_note.py"], stub.scripts()
        )
        self.assertNotIn("② 复盘详情页", out)

    def test_skip_reading_stops_before_both_note_chains(self):
        stub = _StubRun()

        code, out = _run_main(["--date", "2026-09-15", "--skip-reading"], stub)

        self.assertEqual(0, code, out)
        self.assertEqual(["sync_pnl_data.py"], stub.scripts())
        self.assertIn("跳过复盘详情页与手记", out)

    def test_review_page_failure_stops_before_the_daily_note(self):
        stub = _StubRun(fail_on="convert_review.py")

        code, out = _run_main(["--date", "2026-09-15"], stub)

        self.assertEqual(4, code, out)
        self.assertEqual(
            ["sync_pnl_data.py", "convert_review.py"], stub.scripts()
        )

    def test_daily_note_failure_is_reported_after_the_review_page(self):
        stub = _StubRun(fail_on="convert_daily_note.py")

        code, out = _run_main(["--date", "2026-09-15"], stub)

        self.assertEqual(5, code, out)
        self.assertIn("已完成: ① 首页数据 → ② 复盘详情页", out)

    def test_missing_review_page_on_disk_is_a_failure_not_a_success(self):
        """子进程退出码不足以证明页面存在：没落盘就等于这一步没做。"""
        stub = _StubRun()
        with mock.patch.object(
            sync_portal, "review_page", lambda day: Path("/nonexistent/review.html")
        ):
            code, out = _run_main(["--date", "2026-09-15"], stub)

        self.assertEqual(4, code, out)
        self.assertIn("复盘详情页未生成", out)


if __name__ == "__main__":
    unittest.main()
