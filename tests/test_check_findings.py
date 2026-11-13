"""What the checks found: one line per locked check, joined with the dataset ledger."""
import json
import unittest

from intelligence_store import check_findings as cf
from intelligence_store import dataset_ledger as dl
from intelligence_store.model_scorecards import cited_report


class Findings(unittest.TestCase):
    def setUp(self):
        self.view = cf.findings_view()
        self.rows = [r for a in self.view['areas'] for r in a['rows']]

    def test_every_ledger_check_has_one_line(self):
        ledger_reports = {u['report'] for u in dl.load_ledger()['uses'] if u['report']}
        self.assertEqual({r['report'] for r in self.rows}, ledger_reports)
        self.assertEqual(len(self.rows), len(ledger_reports))

    def test_failures_are_listed(self):
        failed = {r['id'] for r in self.rows if r['outcome'] == 'failed'}
        self.assertEqual(failed, {'kuan', 'falling_clearance', 'iwasaki', 'melphalan_label', 'eligibility_v1', 'eligibility_v2', 'eligibility_llm_c1'})
        self.assertGreaterEqual(self.view['counts']['gap'], 9)

    def test_v7_only_rewords_the_track_c_headline(self):
        import hashlib
        old_raw = cf.FINDINGS_PATH.with_name('check_findings_v6.json').read_bytes()
        self.assertEqual(hashlib.sha256(old_raw).hexdigest(), cf.FINDINGS_V6_SHA256)
        old, new = json.loads(old_raw), json.loads(cf.FINDINGS_PATH.read_bytes())
        self.assertEqual(new['supersedes']['sha256'], cf.FINDINGS_V6_SHA256)
        before, after = {f['id']: f for f in old['findings']}, {f['id']: f for f in new['findings']}
        self.assertEqual(set(before), set(after))
        changed = {k for k in before if before[k] != after[k]}
        self.assertEqual(changed, {'eligibility_llm_c1'})
        self.assertEqual({k: v for k, v in before['eligibility_llm_c1'].items() if k != 'headline'},
                         {k: v for k, v in after['eligibility_llm_c1'].items() if k != 'headline'})
        self.assertIn('Pair-based', after['eligibility_llm_c1']['headline'])

    def test_blindness_comes_from_the_ledger(self):
        blind = {r['id']: r['blindness'] for r in self.rows if r['blind']}
        self.assertEqual(blind, {'bridoux_hughes_kim': 'checked_blind_with_deviation', 'dexamethasone_outside': 'checked_blind',
                                 'eligibility_v1': 'checked_blind', 'eligibility_v2': 'checked_blind', 'eligibility_llm_c1': 'checked_blind'})
        self.assertEqual(self.view['blind'], 5)

    def test_outcomes_match_recorded_decisions(self):
        """Spot checks against the reports' own decision fields."""
        rows = {r['id']: r for r in self.rows}
        def report(i):
            return json.loads((cf.ROOT / rows[i]['report']).read_text())
        self.assertFalse(report('melphalan_label')['decision']['eligible'])
        self.assertTrue(report('dexamethasone_outside')['decision']['curve_consistent_with_outside_data'])
        self.assertEqual(report('pathways_2_0d')['decision']['outcome'], 'partial_reported_not_adopted')
        self.assertEqual(report('time_course_v2')['display_decision']['body_map_shows'], 'v1')
        self.assertFalse(report('reece')['decision']['reproduces_reece_at_1_3'])
        self.assertEqual(report('falling_clearance')['decision']['forms_carrying_rise_over'], [])

    def test_every_report_is_served(self):
        for r in self.rows:
            self.assertIsNotNone(cited_report(r['report_name']), r['report_name'])

    def test_changed_findings_file_is_refused(self):
        old = cf.FINDINGS_SHA256
        try:
            cf.FINDINGS_SHA256 = '0' * 64
            with self.assertRaises(cf.FindingsError):
                cf.findings_view()
        finally:
            cf.FINDINGS_SHA256 = old


if __name__ == '__main__':
    unittest.main()
