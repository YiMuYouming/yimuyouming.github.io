"""M1-02 / 2026-10-15 D-22: keep the shipped checker self-test in discovery."""
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import portal_check

class PortalCheckerSelfTest(unittest.TestCase):
    def test_cli_self_test_passes(self):
        r=subprocess.run([sys.executable,str(Path(__file__).with_name('portal_check.py')),'--self-test'],text=True,capture_output=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_ready_state_is_counted_as_suppressed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'state.html';p.write_text("<html><script>if (document.readyState === 'loading') { init(); }</script></html>")
            issues,suppressed=portal_check.check_placeholders(p,portal_check.parse_html(p),collect_suppressed=True)
        self.assertFalse(issues)
        self.assertTrue(suppressed)

    def test_real_loading_placeholder_still_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'loading.html';p.write_text('<html><body>Loading</body></html>')
            issues,_=portal_check.check_placeholders(p,portal_check.parse_html(p),collect_suppressed=True)
        self.assertTrue(issues)
