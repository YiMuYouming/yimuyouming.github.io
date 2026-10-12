import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sync_portal


class PnlReadbackTest(unittest.TestCase):
    def test_step_one_reads_written_data_independently_of_old_home(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "data").mkdir()
            (root / "data/pnl.json").write_text(json.dumps({"summary": {"last_date": "2026-10-12"}}))
            (root / "index.html").write_text('var PNL_DATA = {"summary":{"last_date":"2026-10-09"}};')
            with patch.object(sync_portal, "PORTAL", root), patch.object(sync_portal, "PNL_DATA_FILE", root / "data/pnl.json"):
                self.assertEqual(sync_portal.read_pnl_source_last_date(), "2026-10-12")
                self.assertEqual(sync_portal.read_pnl_last_date(), "2026-10-09")
