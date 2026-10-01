"""test_writing_index.py — W8 S1：公开写作 frontmatter → writing-index.json

用夹具，不读 Vault 真文件（开工单 W8 第四节 S1）。
"""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent / "writing_index.py"
_spec = importlib.util.spec_from_file_location("writing_index", MODULE_PATH)
writing_index = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(writing_index)


DAILY_PUBLISHED = """---
type: writing
kind: daily
date: 2026-10-08
title: 10-08 手记
status: published
published_at: 2026-10-08
tags: [投资, 写作]
summary: 一句话
---

# 2026-10-08

正文自由。
"""

DAILY_DRAFT = DAILY_PUBLISHED.replace("status: published", "status: draft")

ESSAY_PUBLISHED = """---
type: essay
title: 情绪周期里的三次误判
created: 2026-09-12
updated: 2026-10-01
status: published
published_at: 2026-10-01
series: 交易体系
data_asof: 2026-09-30 15:00 Hermes
summary: 说清这篇写什么
---

# 情绪周期里的三次误判

正文。
"""

ESSAY_MISSING_TITLE = """---
type: essay
status: published
published_at: 2026-10-01
---

正文。
"""

WEEKLY_PUBLISHED = """---
type: writing
kind: weekly
week: W41
status: published
published_at: 2026-10-10
---

# W41 周记

正文。
"""


def write(root: Path, rel: str, body: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


class WritingIndexTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_only_published_files_are_indexed(self):
        write(self.root, "每日/2026-10-08.md", DAILY_PUBLISHED)
        write(self.root, "每日/2026-10-09.md", DAILY_DRAFT)
        write(self.root, "文章/2026-09-12-情绪周期.md", ESSAY_PUBLISHED)

        payload = writing_index.build_index(self.root)

        paths = [entry["path"] for entry in payload["entries"]]
        self.assertEqual(sorted(paths), ["文章/2026-09-12-情绪周期.md", "每日/2026-10-08.md"])
        self.assertTrue(all(entry["status"] == "published" for entry in payload["entries"]))
        self.assertEqual(payload["issues"], [])

    def test_entry_fields(self):
        path = write(self.root, "每日/2026-10-08.md", DAILY_PUBLISHED)
        entry = writing_index.build_index(self.root)["entries"][0]
        self.assertEqual(entry["path"], "每日/2026-10-08.md")
        self.assertEqual(entry["kind"], "daily")
        self.assertEqual(entry["date"], "2026-10-08")
        self.assertEqual(entry["title"], "10-08 手记")
        self.assertEqual(entry["series"], "")
        self.assertEqual(entry["status"], "published")
        self.assertEqual(entry["published_at"], "2026-10-08")
        self.assertEqual(entry["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_series_only_present_for_essays(self):
        write(self.root, "文章/2026-09-12-情绪周期.md", ESSAY_PUBLISHED)
        entry = writing_index.build_index(self.root)["entries"][0]
        self.assertEqual(entry["series"], "交易体系")
        self.assertEqual(entry["kind"], "essay")

    def test_weekly_kind_needs_week(self):
        write(self.root, "周记/W41.md", WEEKLY_PUBLISHED)
        payload = writing_index.build_index(self.root)
        self.assertEqual(payload["entries"][0]["kind"], "weekly")
        self.assertEqual(payload["entries"][0]["week"], "W41")

    def test_published_file_missing_required_field_becomes_an_issue_not_an_entry(self):
        write(self.root, "文章/2026-09-12-无标题.md", ESSAY_MISSING_TITLE)
        payload = writing_index.build_index(self.root)
        self.assertEqual(payload["entries"], [])
        self.assertEqual(len(payload["issues"]), 1)
        issue = payload["issues"][0]
        self.assertEqual(issue["path"], "文章/2026-09-12-无标题.md")
        self.assertIn("title", issue["missing"])
        self.assertTrue(issue["reason"])

    def test_draft_missing_field_is_not_an_issue(self):
        write(self.root, "文章/草稿.md", ESSAY_MISSING_TITLE.replace("published", "draft"))
        payload = writing_index.build_index(self.root)
        self.assertEqual(payload["entries"], [])
        self.assertEqual(payload["issues"], [])

    def test_unknown_status_is_an_issue(self):
        write(self.root, "每日/坏状态.md", DAILY_PUBLISHED.replace("status: published", "status: secret"))
        payload = writing_index.build_index(self.root)
        self.assertEqual(payload["entries"], [])
        self.assertEqual(payload["issues"][0]["reason"], "status_unknown")

    def test_index_is_deterministic_and_sorted(self):
        write(self.root, "每日/2026-10-08.md", DAILY_PUBLISHED)
        write(self.root, "文章/a.md", ESSAY_PUBLISHED)
        write(self.root, "文章/b.md", ESSAY_PUBLISHED)
        first = writing_index.build_index(self.root)
        second = writing_index.build_index(self.root)
        self.assertEqual(first["entries"], second["entries"])
        self.assertEqual(
            [entry["path"] for entry in first["entries"]],
            sorted(entry["path"] for entry in first["entries"]),
        )

    def test_payload_carries_no_machine_specific_path_or_timestamp(self):
        write(self.root, "每日/2026-10-08.md", DAILY_PUBLISHED)
        payload = writing_index.build_index(self.root)
        self.assertNotIn("source_root", payload)
        self.assertNotIn("generated_at", payload)
        self.assertEqual(
            writing_index.render(payload),
            writing_index.render(writing_index.build_index(self.root)),
        )

    def test_body_hash_is_of_the_source_file_not_the_frontmatter(self):
        path = write(self.root, "每日/2026-10-08.md", DAILY_PUBLISHED)
        entry = writing_index.build_index(self.root)["entries"][0]
        self.assertEqual(entry["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_cli_writes_json_and_check_detects_drift(self):
        write(self.root, "每日/2026-10-08.md", DAILY_PUBLISHED)
        out = Path(self._tmp.name) / "out" / "writing-index.json"
        self.assertEqual(
            writing_index.main(["--root", str(self.root), "--out", str(out)]), 0
        )
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "writing_index.v1")
        self.assertEqual(payload["entries"][0]["path"], "每日/2026-10-08.md")
        # check：未变则 0
        self.assertEqual(
            writing_index.main(["--root", str(self.root), "--out", str(out), "--check"]), 0
        )
        # 新增一篇已发布写作后 check 必须失败
        write(self.root, "每日/2026-10-09.md", DAILY_PUBLISHED.replace("10-08", "10-09"))
        self.assertEqual(
            writing_index.main(["--root", str(self.root), "--out", str(out), "--check"]), 1
        )


if __name__ == "__main__":
    unittest.main()