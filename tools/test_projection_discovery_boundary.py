import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sync_portal


class DiscoveryBoundary(unittest.TestCase):
    def test_corrupt_index_stops_public_converters(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            note = root / 'note.md'
            note.write_text('---\ndate: 2026-09-24\n---\n')
            folder = root / 'artifacts/review-reading/2026/2026-09-24'
            folder.mkdir(parents=True)
            (folder / '_index.json').write_text('{ broken')
            with patch.object(sync_portal, 'MARKET_WATCH_ROOT', root), \
                 patch.object(sync_portal, 'find_review_note', return_value=note), \
                 patch.object(sync_portal, 'run_step', return_value=True) as run, \
                 patch.object(sync_portal, 'read_pnl_last_date', return_value='2026-09-24'), \
                 contextlib.redirect_stdout(io.StringIO()):
                code = sync_portal.main(['--date', '2026-09-24', '--dry-run'])
            self.assertNotEqual(0, code)
            self.assertEqual(1, run.call_count, 'only home step may have run')
