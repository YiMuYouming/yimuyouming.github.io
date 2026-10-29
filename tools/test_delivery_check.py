"""H12：每日交付检查——收益数据日期＝当天；首页最新随笔日期＝当天；UI版本＝已部署版本。任一不符报红。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import delivery_check as dc

DAY = "2026-10-29"


def _pnl(last_date, data_date):
    return {"data": {"summary": {"last_date": last_date}, "today_sh": {"data_date": data_date}}}


def _index(latest_row_date, entries):
    essay = '<h3>长文</h3><ul class="writing-list"><li><span class="writing-date">2026-10-12</span></li></ul>'
    rows = essay + f'<h3>每日手记</h3><ul class="writing-list"><li><a class="writing-row" href="daily/{latest_row_date}.html"><span class="writing-date">{latest_row_date}</span></a></li></ul>'
    index = {"entries": entries, "schema": "writing_index.v1"}
    return rows + "<script>var WRITING_INDEX = " + json.dumps(index, ensure_ascii=False) + ";</script>"


def _entry(date, kind="daily", status="published"):
    return {"date": date, "kind": kind, "status": status}


class Checks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "data").mkdir()

    def write(self, pnl=None, html=None):
        if pnl is not None:
            (self.root / "data/pnl.json").write_text(json.dumps(pnl), encoding="utf-8")
        if html is not None:
            (self.root / "index.html").write_text(html, encoding="utf-8")

    def test_pnl_date_must_be_the_day(self):
        self.write(pnl=_pnl(DAY, DAY))
        self.assertTrue(dc.check_pnl_date(self.root, DAY)["ok"])
        self.write(pnl=_pnl("2026-10-28", DAY))
        result = dc.check_pnl_date(self.root, DAY)
        self.assertFalse(result["ok"])
        self.assertIn("2026-10-28", result["detail"])

    def test_missing_pnl_file_is_red_not_skipped(self):
        result = dc.check_pnl_date(self.root, DAY)
        self.assertFalse(result["ok"])
        self.assertIn("读不到", result["detail"])

    def test_latest_diary_date_must_be_the_day(self):
        self.write(html=_index(DAY, [_entry("2026-10-28"), _entry(DAY)]))
        self.assertTrue(dc.check_latest_diary(self.root, DAY)["ok"])

    def test_homepage_stuck_on_an_older_day_is_red(self):
        # 10-29 的真实情形：数据页更新了，但首页手记最新只到 23 日
        self.write(html=_index("2026-10-23", [_entry("2026-10-23"), _entry(DAY, status="draft")]))
        result = dc.check_latest_diary(self.root, DAY)
        self.assertFalse(result["ok"])
        self.assertIn("2026-10-23", result["detail"])

    def test_index_published_but_row_missing_on_homepage_is_red(self):
        self.write(html=_index("2026-10-28", [_entry(DAY)]))
        self.assertFalse(dc.check_latest_diary(self.root, DAY)["ok"])

    def test_ui_version_is_the_hash_of_what_is_served(self):
        self.write(html="<html>v1</html>")
        local = dc.ui_version((self.root / "index.html").read_bytes())
        ok = dc.check_ui_version(self.root, fetch=lambda url: b"<html>v1</html>", url="https://x/")
        self.assertTrue(ok["ok"])
        self.assertEqual(local, ok["local"])
        stale = dc.check_ui_version(self.root, fetch=lambda url: b"<html>old</html>", url="https://x/")
        self.assertFalse(stale["ok"])
        self.assertIn("未部署", stale["detail"])

    def test_ui_version_fetch_failure_is_red(self):
        self.write(html="x")
        def boom(url):
            raise OSError("down")
        result = dc.check_ui_version(self.root, fetch=boom, url="https://x/")
        self.assertFalse(result["ok"])
        self.assertIn("读不到", result["detail"])

    def test_run_is_red_if_any_check_is_red(self):
        self.write(pnl=_pnl(DAY, DAY), html=_index(DAY, [_entry(DAY)]))
        results, code = dc.run(self.root, DAY, fetch=lambda url: (self.root / "index.html").read_bytes(), url="https://x/")
        self.assertEqual(0, code)
        self.assertEqual(3, len(results))
        self.write(pnl=_pnl("2026-10-28", DAY))
        _results, code = dc.run(self.root, DAY, fetch=lambda url: (self.root / "index.html").read_bytes(), url="https://x/")
        self.assertEqual(1, code)


if __name__ == "__main__":
    unittest.main()
