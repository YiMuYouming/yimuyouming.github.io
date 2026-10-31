import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

ENTRY = Path(__file__).with_name('build_period_review.py')
if ENTRY.is_file():
    spec = importlib.util.spec_from_file_location('build_period_review', ENTRY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
else:
    mod = None


def report(kind='weekly'):
    return {'kind':kind,'id':'2026-W44' if kind=='weekly' else '2026-10',
            'start':'2026-10-26','end':'2026-10-30',
            'sessions':['2026-10-26','2026-10-27','2026-10-28','2026-10-29','2026-10-30'],
            'title':'W44 周总结' if kind=='weekly' else '10月总结',
            'summary':'反复修复中，先把原计划执行完整。',
            'lead':'低仓位限制了回撤，执行仍需改善。',
            'account_return':-0.8157,'benchmark_return':-2.4857,
            'sections':[{'title':'市场节奏','paragraphs':['周中修复未能延续。']},
                        {'title':'操作反思','paragraphs':['止损触发后按原计划处理。']}],
            'note':'统计截至各交易日收盘，收益按期间净值计算。'}


class PeriodReviewTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(mod, 'public week/month review builder is required')

    def test_public_page_has_metrics_navigation_and_no_internal_language(self):
        for kind in ('weekly','monthly'):
            page = mod.render_report(report(kind))
            self.assertIn('-0.82%',page)
            self.assertIn('约-2.49%',page)
            self.assertIn('+1.67',page)
            self.assertIn('weekly-review.css',page)
            self.assertIn('../index.html',page)
            self.assertIn('aria-label=',page)
            for word in ('审计','门禁','回执','封存','source_gaps','/Users/'):
                self.assertNotIn(word,page)

    def test_internal_text_and_private_payload_fail_before_rendering(self):
        for value in ('审计完成','门禁通过','回执齐全','封存通过','/Users/private',
                      '买入2000股','成交16.70元'):
            item=report();item['lead']=value
            with self.assertRaisesRegex(ValueError,'public'):
                mod.render_report(item)
        item=report();item['ticket_id']='secret'
        with self.assertRaisesRegex(ValueError,'field'):
            mod.render_report(item)

    def test_text_is_escaped_and_sessions_are_unique_and_in_range(self):
        item=report();item['lead']='原计划 <script>alert(1)</script>'
        page=mod.render_report(item)
        self.assertNotIn('<script>',page)
        self.assertIn('&lt;script&gt;',page)
        for sessions in (['2026-10-26','2026-10-26'],['2026-11-02'],[]):
            item=report();item['sessions']=sessions
            with self.assertRaisesRegex(ValueError,'session'):
                mod.render_report(item)

    def test_build_archives_both_periods_idempotently_and_check_is_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);reviews=root/'review-notes';reviews.mkdir()
            archive=reviews/'index.html';archive.write_text(
                '<span><strong>0</strong> 周覆盖</span>'
                '<span><strong>0</strong> 份周度总结</span>'
                '<span><strong>0</strong> 份月度复盘</span>'
                '<div class="weekly-grid">\n</div>'
                '<div id="monthly-reviews" class="divider">月度总结</div>')
            home=root/'index.html';home.write_text('existing home')
            payload={'schema':'public-period-review.v1','reports':[report(),report('monthly')]}
            with self.assertRaisesRegex(ValueError,'stale'):
                mod.build(root,payload,check=True)
            self.assertEqual(home.read_text(),'existing home')
            mod.build(root,payload)
            before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            mod.build(root,payload);mod.build(root,payload,check=True)
            after={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(before,after)
            self.assertIn('weekly-2026-10-26_10-30.html',archive.read_text())
            self.assertIn('monthly-2026-10-26_10-30.html',archive.read_text())
            self.assertIn('<strong>1</strong> 份月度复盘',archive.read_text())
            self.assertIn('W44', (root/'weekly/index.html').read_text())
            self.assertIn('10月', (root/'monthly/index.html').read_text())
            self.assertEqual(home.read_text(),'existing home')


if __name__=='__main__':unittest.main()
