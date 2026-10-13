"""One sync includes newly approved writing; external data is fixture-only."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import sync_portal
import writing_index
import build_daily_page


class SyncWritingIndexTest(unittest.TestCase):
    def run_sync(self, root, *, fail_index=False):
        writing = root / 'writing'
        writing.mkdir()
        (writing / 'new.md').write_text('---\nkind: daily\ndate: 2026-10-08\nstatus: published\n'
            'published_at: "2026-10-08T18:00:00+08:00"\ntitle: 夹具手记\n---\n\n已批准的新增原话。')
        index = root / 'writing-index.json'
        index.write_text('{"entries": [], "issues": []}')
        page = root / 'daily/2026-10-08.html'
        calls = []
        def local_steps(command, **kwargs):
            calls.append(Path(command[1]).name)
            argv = command[2:]
            name = calls[-1]
            if name == 'writing_index.py':
                code = 1 if fail_index else writing_index.main(argv)
            elif name == 'build_daily_page.py':
                code = build_daily_page.main(argv)
            else:
                code = 0  # remote PnL / privacy service never called
            return SimpleNamespace(returncode=code, stdout='', stderr='')
        with patch.multiple(sync_portal, PORTAL=root, WRITING_ROOT=writing, WRITING_INDEX=index), \
             patch.object(sync_portal, 'find_review_note', return_value=root / 'note.md'), \
             patch.object(sync_portal, 'find_reading_sidecar', return_value=None), \
             patch.object(sync_portal, 'load_review_index_fields', return_value={'date': '2026-10-08', '情绪值': 47.6}), \
             patch.object(sync_portal, 'read_pnl_source_last_date', return_value='2026-10-08'), \
             patch.object(sync_portal, 'read_pnl_last_date', return_value='2026-10-08'), \
             patch.object(sync_portal, 'daily_public_page', return_value=page), \
             patch.object(sync_portal.subprocess, 'run', side_effect=local_steps), contextlib.redirect_stdout(io.StringIO()):
            code = sync_portal.main(['--date', '2026-10-08'])
        return code, calls, page

    def test_new_approved_writing_appears_in_one_sync(self):
        with tempfile.TemporaryDirectory() as td:
            code, calls, page = self.run_sync(Path(td))
            self.assertEqual(code, 0)
            self.assertIn('已批准的新增原话。', page.read_text())
            self.assertLess(calls.index('writing_index.py'), calls.index('build_daily_page.py'))

    def test_index_failure_stops_before_daily_page(self):
        with tempfile.TemporaryDirectory() as td:
            code, calls, page = self.run_sync(Path(td), fail_index=True)
            self.assertNotEqual(code, 0)
            self.assertNotIn('build_daily_page.py', calls)
            self.assertFalse(page.exists())
