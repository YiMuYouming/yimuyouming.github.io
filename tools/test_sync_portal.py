import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_portal


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


if __name__ == "__main__":
    unittest.main()
