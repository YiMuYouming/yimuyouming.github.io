import atexit
import contextlib
import json
import io
import shutil
import tempfile
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
        joined = " ".join(self.calls[-1])
        code = 1 if self.fail_on and self.fail_on in joined else 0
        stdout = kwargs.get("text") and not code
        payload = json.dumps({"date": "2026-10-08", "情绪值": 47.6}, ensure_ascii=False) \
            if stdout else ""
        return mock.Mock(returncode=code, stdout=payload, stderr="" if not code else "stub failed")

    def scripts(self) -> list[str]:
        return [Path(call[1]).name for call in self.calls]

    def review_index_fields(self, day: str) -> dict:
        self.calls.append([sys.executable, "review_index_fields", day])
        return {"date": day, "情绪值": 47.6}


_TEMP_ROOT: Path | None = None


def _day_of(argv: list[str]) -> str:
    return argv[argv.index("--date") + 1] if "--date" in argv else "2026-10-08"


def _run_main(argv: list[str], stub: _StubRun, *, public_page: Path | None = None) -> tuple[int, str]:
    """跑 sync_portal.main，挡掉子进程与 Vault 依赖。

    ReviewNote 的定位一律给一个假路径：这些用例要守的是**发布链的顺序与完整性**，
    不是 Vault 里恰好有没有那一天的文件（那会让用例随时间漂）。
    """
    buffer = io.StringIO()
    # 页面「已落盘」这件事单独造出来：sync_portal 会检查文件在不在，
    # 而这里子进程是假的，不会真的写文件。默认值指向存在的临时文件，
    # 「未落盘算失败」那条用例自己把它换成不存在的路径。
    global _TEMP_ROOT
    if _TEMP_ROOT is None:
        _TEMP_ROOT = Path(tempfile.mkdtemp(prefix="portal-sync-test-"))
        atexit.register(lambda: shutil.rmtree(_TEMP_ROOT, ignore_errors=True))
    day = _day_of(argv)
    public_page = public_page or (_TEMP_ROOT / "daily" / f"{day}.html")
    home = _TEMP_ROOT / "index.html"
    if public_page.is_relative_to(_TEMP_ROOT):
        public_page.parent.mkdir(parents=True, exist_ok=True)
        public_page.write_text("<html></html>", encoding="utf-8")
    home.write_text("<html></html>", encoding="utf-8")
    with mock.patch.object(sync_portal.subprocess, "run", stub), \
         mock.patch.object(sync_portal, "load_review_index_fields", stub.review_index_fields), \
         mock.patch.object(sync_portal, "find_review_note",
                           lambda day: Path("/tmp/fake-ReviewNote.md")), \
         mock.patch.object(sync_portal, "find_reading_sidecar",
                           lambda note, day: None), \
         mock.patch.object(sync_portal, "daily_public_page",
                           lambda day: public_page), \
         mock.patch.object(sync_portal, "home_page", lambda: home), \
         contextlib.redirect_stdout(buffer):
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
    """三条链必须按 首页数据 → 每日公开页 → 整页首页 固定顺序跑（W8 S7a）。"""

    def test_real_run_executes_three_chains_in_order(self):
        stub = _StubRun()

        code, out = _run_main(["--date", "2026-10-08"], stub)

        self.assertEqual(0, code, out)
        self.assertEqual(
            [
                "sync_pnl_data.py",
                "review_index_fields",
                "build_daily_page.py",
                "build_home.py",
                "portal_check.py",
            ],
            stub.scripts(),
            "每日公开页曾经整条链漏跑，顺序与完整性都要盯住；"
            "④ 隐私红线门禁是 2026-09-28 新增的固定最后一步",
        )
        self.assertNotIn("--dry-run", " ".join(stub.calls[1]))
        self.assertIn("--redline", " ".join(stub.calls[-1]))

    def test_dry_run_does_not_render_the_home_or_write_pages(self):
        """预演绝不能写盘：不执行没有 --dry-run 的取指标那一步。"""
        stub = _StubRun()

        code, out = _run_main(["--date", "2026-10-08", "--dry-run"], stub)

        self.assertEqual(0, code, out)
        self.assertIn("① 首页数据", out)
        self.assertIn("②a 取封存市场指标", out)
        self.assertIn("②b 每日公开页", out)
        self.assertIn("③ 首页整页渲染", out)
        self.assertLess(out.index("②a"), out.index("②b"))
        self.assertLess(out.index("②b"), out.index("③ 首页整页渲染"))
        # ②a 只读封存库、往 stdout 打印，不写任何东西——所以预演也照跑，
        # ②b 才有指标可读（落在仓库外的临时文件）。真正不许写的是 ②b 和 ③。
        self.assertIn("review_index_fields", stub.scripts())
        self.assertIn("build_daily_page.py", stub.scripts())
        self.assertNotIn("build_home.py", stub.scripts(),
                         "预演不得真的整页渲染首页")
        # 真正不许写盘的是 ②b（build_daily_page 自己支持 --dry-run）
        self.assertIn("--dry-run", " ".join(stub.calls[-1]))
        self.assertIn("[dry-run]", out)

    def test_skip_review_leaves_the_home_chain_running(self):
        stub = _StubRun()

        code, out = _run_main(["--date", "2026-10-08", "--skip-review"], stub)

        self.assertEqual(0, code, out)
        self.assertIn("build_home.py", stub.scripts(),
                      "跳过每日公开页后，首页仍须整页渲染")
        self.assertIn("④ 隐私红线", out)

    def test_skip_reading_stops_before_both_note_chains(self):
        stub = _StubRun()

        code, out = _run_main(["--date", "2026-10-08", "--skip-reading"], stub)

        self.assertEqual(0, code, out)
        self.assertEqual(["sync_pnl_data.py"], stub.scripts())
        self.assertIn("跳过复盘详情页与手记", out)

    def test_daily_page_failure_stops_before_the_home_render(self):
        stub = _StubRun(fail_on="build_daily_page.py")

        code, out = _run_main(["--date", "2026-10-08"], stub)

        self.assertEqual(4, code, out)
        self.assertNotIn("build_home.py", stub.scripts(),
                         "每日公开页失败就不该继续渲染首页")

    def test_home_failure_is_reported_after_the_daily_page(self):
        stub = _StubRun(fail_on="build_home.py")

        code, out = _run_main(["--date", "2026-10-08"], stub)

        self.assertEqual(5, code, out)
        self.assertIn("已完成: ① 首页数据 → ② 每日公开页", out)

    def test_missing_daily_page_on_disk_is_a_failure_not_a_success(self):
        """子进程退出码不足以证明页面存在：没落盘就等于这一步没做。"""
        stub = _StubRun()
        code, out = _run_main(
            ["--date", "2026-10-08"], stub,
            public_page=Path("/nonexistent/d.html"),
        )

        self.assertEqual(4, code, out)
        self.assertIn("每日公开页未生成", out)


if __name__ == "__main__":
    unittest.main()


class RedLineGateTests(unittest.TestCase):
    """红线命中必须让整个同步失败，未生成的页面不得进入发布。"""

    def test_redline_hit_stops_sync_with_code_6(self):
        stub = _StubRun(fail_on="portal_check.py")
        code, out = _run_main(["--date", "2026-09-15"], stub)
        self.assertEqual(6, code, out)
        self.assertIn("隐私红线命中", out)
        self.assertIn("portal_check.py", " ".join(stub.calls[-1]))

    def test_gate_is_last_step(self):
        stub = _StubRun()
        code, out = _run_main(["--date", "2026-09-15"], stub)
        self.assertEqual(0, code, out)
        self.assertEqual("portal_check.py", stub.scripts()[-1])
        self.assertIn("--redline", " ".join(stub.calls[-1]))
