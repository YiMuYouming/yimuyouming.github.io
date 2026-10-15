"""M1-09 / 2026-10-14 D-35 and 2026-10-15 D-22 appendix."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import sync_portal

class PnlWrapperTests(unittest.TestCase):
    def read(self,data):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'pnl.json';p.write_text(json.dumps(data))
            with patch.object(sync_portal,'PNL_DATA_FILE',p):
                return sync_portal.read_pnl_source_last_date()

    def test_wrapped_summary_date_is_read_from_data(self):
        self.assertEqual(self.read({'schema':'pnl.v1','source':'fixture','data':{'summary':{'last_date':'2026-10-15'}}}),'2026-10-15')

    def test_legacy_unwrapped_payload_is_still_supported(self):
        self.assertEqual(self.read({'summary':{'last_date':'2026-10-14'}}),'2026-10-14')

    def test_missing_inner_date_is_not_invented_from_outer_wrapper(self):
        self.assertIsNone(self.read({'summary':{'last_date':'2026-10-14'},'data':{'summary':{}}}))
