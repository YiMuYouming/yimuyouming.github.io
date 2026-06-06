import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_pnl_data


class ResolveMetaTest(unittest.TestCase):
    def test_estimates_asset_from_existing_deposit_and_latest_nav(self):
        data = {
            "summary": {"total_asset": None, "last_nav": 1.012894},
            "all_sh": {"nav": [1.0, 1.012894]},
        }
        existing = {"meta": {"total_asset": 723535.67, "total_deposit": 711059.2252961266}}

        meta = sync_pnl_data.resolve_meta(data, [existing])

        self.assertEqual(meta["total_deposit"], 711059.2252961266)
        self.assertEqual(meta["total_asset"], 720227.62)

    def test_uses_committed_deposit_when_current_file_has_default_deposit(self):
        data = {"summary": {"total_asset": None, "last_nav": 1.012894}}
        current_bad = {"meta": {"total_asset": 202578.8, "total_deposit": 200000}}
        committed = {"meta": {"total_asset": 723535.67, "total_deposit": 711059.2252961266}}

        meta = sync_pnl_data.resolve_meta(data, [current_bad, committed])

        self.assertEqual(meta["total_deposit"], 711059.2252961266)
        self.assertEqual(meta["total_asset"], 720227.62)

    def test_summary_total_asset_wins_when_present(self):
        data = {"summary": {"total_asset": 712345.67, "total_deposit": 700000, "last_nav": 1.2}}
        existing = {"meta": {"total_asset": 600000, "total_deposit": 500000}}

        meta = sync_pnl_data.resolve_meta(data, [existing])

        self.assertEqual(meta, {"total_asset": 712345.67, "total_deposit": 700000.0})

    def test_extract_existing_pnl_data_from_index_html(self):
        html = '<!-- PNL_DATA_START --><script>\nvar PNL_DATA = {"meta":{"total_asset":1}};\n</script>'

        self.assertEqual(
            sync_pnl_data.extract_existing_pnl_data(html),
            {"meta": {"total_asset": 1}},
        )


if __name__ == "__main__":
    unittest.main()
