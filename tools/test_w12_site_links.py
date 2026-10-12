import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import portal_check


class PublishedLinksTest(unittest.TestCase):
    def test_ready_state_loading_is_not_a_page_placeholder(self):
        with tempfile.TemporaryDirectory() as td:
            page = Path(td) / "page.html"
            page.write_text('<title>Page</title><script>if (document.readyState === "loading") init();</script><p>Published</p>')
            issues, _ = portal_check.check_placeholders(page, portal_check.parse_html(page))
            self.assertEqual(issues, [])

    def test_script_debug_words_are_not_visible_placeholders(self):
        with tempfile.TemporaryDirectory() as td:
            page = Path(td) / "page.html"
            page.write_text('<title>Page</title><script>const state = "loading TODO draft";</script><p>Published</p>')
            scan = portal_check.parse_html(page)
            self.assertNotIn("TODO", scan["text"])
            self.assertIn("Published", scan["text"])

    def test_base_href_and_directory_index_follow_browser_resolution(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            (root / "v1").mkdir()
            (root / "report").mkdir()
            (root / "report/index.html").write_text("<title>Report</title>")
            page = root / "v1/index.html"
            page.write_text('<base href="../"><a href="report/">Report</a>')
            with patch.object(portal_check, "PORTAL", root):
                self.assertEqual(portal_check.check_broken_links(page, portal_check.parse_html(page)), [])

    def test_public_scan_excludes_generator_templates_and_scratch_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            for rel in ("index.html", "review-notes/2026-07-01.html", "templates/home.html", "out/preview/index.html"):
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("<title>fixture</title>")
            with patch.object(portal_check, "PORTAL", root):
                files = {str(p.relative_to(root)) for p in portal_check.get_files(False)}
            self.assertEqual(files, {"index.html", "review-notes/2026-07-01.html"})

    def test_missing_public_link_still_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            page = root / "index.html"
            page.write_text('<a href="absent.html">missing</a>')
            with patch.object(portal_check, "PORTAL", root):
                self.assertTrue(portal_check.check_broken_links(page, portal_check.parse_html(page)))
