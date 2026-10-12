import tempfile
import unittest
from pathlib import Path
import build_archive_index


class ArchiveRegenerationTest(unittest.TestCase):
    def test_isolated_history_source_regenerates_relative_links(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            (root / "review-notes").mkdir()
            (root / "review-notes/2026-06-05.html").write_text("<title>source</title>")
            text, groups = build_archive_index.build(root)
        self.assertEqual(sum(group["count"] for group in groups), 1)
        self.assertIn('href="../review-notes/2026-06-05.html"', text)
        self.assertNotIn(str(root), text)
