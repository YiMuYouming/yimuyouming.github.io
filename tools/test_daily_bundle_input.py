import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_review
import convert_daily_note


READING = '''---
date: 2026-09-02
note_schema: yimu.review.v2
stage_final: done
daily_bundle_ref: private-generation
---
## 一、当日复盘
### 一句话结论
市场正在分化，先观察持续性。
## 二、心得与教训
### 今日认知
1. 把观察和行动分开，等到条件清楚。
## 三、次日预案
### 明日观察
关注强板块能否延续。
'''
MACHINE = '''---
date: 2026-09-02
weekday: 周三
stage_red_team: done
stage_final: done
情绪值: 55
涨停家数: 30
跌停家数: 8
盘后持仓: 示例股 900股 成本价 23.45
---
SECRET_MACHINE_LEDGER
review_sha256: abc-private-hash
'''


class PortalBundleTests(unittest.TestCase):
    def test_both_converters_use_reading_and_safe_machine_facts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            note = root / '2026_9_2_Wednesday_ReviewNote.md'
            note.write_text(READING)
            with patch('daily_bundle_input.resolve_bundle_reading', return_value={
                    'reading_text': READING, 'machine_text': MACHINE}), \
                    patch.object(convert_review, 'REVIEW_NOTES', root):
                _, path = convert_review.convert_md_to_html(note)
                html = path.read_text()
                daily = convert_daily_note.build_daily_note(note)
            self.assertIn('市场正在分化', html)
            self.assertIn('30涨停', html)
            self.assertIn('市场正在分化', str(daily))
            for secret in ('private-generation', 'SECRET_MACHINE_LEDGER', 'abc-private-hash', '900股', '23.45'):
                self.assertNotIn(secret, html)
                self.assertNotIn(secret, str(daily))

    def test_invalid_explicit_bundle_does_not_publish_as_legacy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            note = root / '2026_9_2_Wednesday_ReviewNote.md'
            note.write_text(READING)
            with patch('daily_bundle_input.resolve_bundle_reading', side_effect=ValueError('invalid')), \
                    patch.object(convert_review, 'REVIEW_NOTES', root):
                with self.assertRaises(ValueError):
                    convert_review.convert_md_to_html(note)
            self.assertFalse((root / '2026-09-02.html').exists())


if __name__ == '__main__':
    unittest.main()
