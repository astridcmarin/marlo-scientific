"""What the checks found: one line per locked check, joined with the dataset ledger."""
import hashlib
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
        self.assertEqual(failed, {'kuan', 'falling_clearance', 'iwasaki', 'melphalan_label', 'eligibility_v1', 'eligibility_v2',
                                  'eligibility_llm_c1', 'eligibility_second_annotation_v1', 'carfilzomib_label'})
        self.assertGreaterEqual(self.view['counts']['gap'], 9)

    def test_v7_only_rewords_the_track_c_headline(self):
        import hashlib
        old_raw = cf.FINDINGS_PATH.with_name('check_findings_v6.json').read_bytes()
        new_raw = cf.FINDINGS_PATH.with_name('check_findings_v7.json').read_bytes()
        self.assertEqual(hashlib.sha256(old_raw).hexdigest(), cf.FINDINGS_V6_SHA256)
        self.assertEqual(hashlib.sha256(new_raw).hexdigest(), cf.FINDINGS_V7_SHA256)
        old, new = json.loads(old_raw), json.loads(new_raw)
        self.assertEqual(new['supersedes']['sha256'], cf.FINDINGS_V6_SHA256)
        before, after = {f['id']: f for f in old['findings']}, {f['id']: f for f in new['findings']}
        self.assertEqual(set(before), set(after))
        changed = {k for k in before if before[k] != after[k]}
        self.assertEqual(changed, {'eligibility_llm_c1'})
        self.assertEqual({k: v for k, v in before['eligibility_llm_c1'].items() if k != 'headline'},
                         {k: v for k, v in after['eligibility_llm_c1'].items() if k != 'headline'})
        self.assertIn('Pair-based', after['eligibility_llm_c1']['headline'])

    def test_v8_only_adds_the_reference_re_reading(self):
        old_raw = cf.FINDINGS_PATH.with_name('check_findings_v7.json').read_bytes()
        new_raw = cf.FINDINGS_PATH.with_name('check_findings_v8.json').read_bytes()
        old, new = json.loads(old_raw), json.loads(new_raw)
        self.assertEqual(new['supersedes']['sha256'], cf.FINDINGS_V7_SHA256)
        before, after = {f['id']: f for f in old['findings']}, {f['id']: f for f in new['findings']}
        self.assertEqual(set(after) - set(before), {'eligibility_reference_review_v1'})
        self.assertEqual({k: before[k] for k in before}, {k: after[k] for k in before})
        added = after['eligibility_reference_review_v1']
        self.assertEqual(added['outcome'], 'inconclusive')
        self.assertIn('not blind', added['headline'])
        self.assertIn('stay primary', added['headline'])

    def test_v9_only_adds_the_second_annotation(self):
        old_raw = cf.FINDINGS_PATH.with_name('check_findings_v8.json').read_bytes()
        new_raw = cf.FINDINGS_PATH.with_name('check_findings_v9.json').read_bytes()
        old, new = json.loads(old_raw), json.loads(new_raw)
        self.assertEqual(new['supersedes']['sha256'], cf.FINDINGS_V8_SHA256)
        before, after = {f['id']: f for f in old['findings']}, {f['id']: f for f in new['findings']}
        self.assertEqual(set(after) - set(before), {'eligibility_second_annotation_v1'})
        self.assertEqual({k: before[k] for k in before}, {k: after[k] for k in before})
        added = after['eligibility_second_annotation_v1']
        self.assertEqual(added['outcome'], 'failed')
        self.assertIn('0.90', added['acceptance_rule'])
        self.assertIn('adjudicated', added['headline'])

    def test_v10_only_adds_the_adjudication(self):
        old_raw = cf.FINDINGS_PATH.with_name('check_findings_v9.json').read_bytes()
        old, new = json.loads(old_raw), json.loads(cf.FINDINGS_PATH.with_name('check_findings_v10.json').read_bytes())
        self.assertEqual(new['supersedes']['sha256'], cf.FINDINGS_V9_SHA256)
        before, after = {f['id']: f for f in old['findings']}, {f['id']: f for f in new['findings']}
        self.assertEqual(set(after) - set(before), {'eligibility_adjudication_v1'})
        self.assertEqual({k: before[k] for k in before}, {k: after[k] for k in before})
        added = after['eligibility_adjudication_v1']
        self.assertEqual(added['outcome'], 'mixed')
        self.assertIn('lower bounds', added['acceptance_rule'])
        self.assertIn('measures the readers', added['headline'])

    def test_v13_adds_the_carfilzomib_label_check_only(self):
        old = json.loads(cf.FINDINGS_PATH.with_name('check_findings_v12.json').read_bytes())
        raw = cf.FINDINGS_PATH.with_name('check_findings_v13.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), cf.FINDINGS_V13_SHA256)
        new = json.loads(raw)
        self.assertEqual(new['supersedes']['sha256'], cf.FINDINGS_V12_SHA256)
        self.assertEqual(new['findings'][:-1], old['findings'])
        added = new['findings'][-1]
        self.assertEqual((added['id'], added['outcome']), ('carfilzomib_label', 'failed'))
        rep = json.loads((cf.ROOT / added['report']).read_text())
        self.assertEqual(hashlib.sha256((cf.ROOT / added['report']).read_bytes()).hexdigest(), added['report_file_sha256'])
        self.assertEqual((rep['outcome'], rep['selected_set']), ('not_eligible', None))
        a = rep['sets_by_bsa']['1.8']['A_exposure_derived']
        self.assertEqual(round(a['cl_l_h'], 1), 90.0)
        self.assertEqual([c for c, r in a['checks'].items() if r['result'] == 'fail'], ['C1_clearance_in_stated_range', 'C6_cmax_secondary'])
        b = rep['sets_by_bsa']['1.8']['B_stated_clearance']
        self.assertEqual([c for c, r in b['checks'].items() if r['result'] == 'fail'],
                         ['C4_auc_ss_primary', 'C5_auc_c1_primary', 'C7_auc_ss_secondary'])

    def test_v12_adds_the_round_two_second_annotation_only(self):
        old_raw = cf.FINDINGS_PATH.with_name('check_findings_v11.json').read_bytes()
        old, new = json.loads(old_raw), json.loads(cf.FINDINGS_PATH.with_name('check_findings_v12.json').read_bytes())
        self.assertEqual(new['supersedes']['sha256'], cf.FINDINGS_V11_SHA256)
        self.assertEqual(new['findings'][:-1], old['findings'])
        added = new['findings'][-1]
        self.assertEqual((added['id'], added['outcome']), ('eligibility_second_annotation_v2', 'passed'))
        self.assertIn('Observed lower bound 0.9125', added['acceptance_rule'])
        report = cf.ROOT / added['report']
        self.assertEqual(hashlib.sha256(report.read_bytes()).hexdigest(), added['report_file_sha256'])
        rep = json.loads(report.read_text())
        self.assertEqual(rep['primary']['reliability_reading']['value'], 0.9125)
        self.assertEqual(rep['primary']['reliability_reading']['reading'], 'adequate')
        self.assertEqual(rep['primary']['overall']['exact_agreement'], 378)

    def test_v11_adds_acceptance_rule_v2_for_gupta_and_luo(self):
        old = json.loads(cf.FINDINGS_PATH.with_name('check_findings_v10.json').read_bytes())
        new = json.loads(cf.FINDINGS_PATH.with_name('check_findings_v11.json').read_bytes())
        self.assertEqual(new['supersedes']['sha256'], cf.FINDINGS_V10_SHA256)
        before, after = {f['id']: f for f in old['findings']}, {f['id']: f for f in new['findings']}
        self.assertEqual(set(after) - set(before), {'acceptance_rule_v2_gupta_luo'})
        for k in before:
            if k in ('ixazomib', 'daratumumab_v2'):
                self.assertEqual(after[k]['acceptance_rule'], before[k]['acceptance_rule'] + ' Re-judged under acceptance rule v2 (18 November).')
                self.assertEqual({x: y for x, y in after[k].items() if x != 'acceptance_rule'},
                                 {x: y for x, y in before[k].items() if x != 'acceptance_rule'})
            else:
                self.assertEqual(after[k], before[k], k)

    def test_v14_adds_the_blind_nct01801436_check_only(self):
        old = json.loads(cf.FINDINGS_PATH.with_name('check_findings_v13.json').read_bytes())
        new = json.loads(cf.FINDINGS_PATH.read_bytes())
        self.assertEqual(new['supersedes']['sha256'], cf.FINDINGS_V13_SHA256)
        self.assertEqual(new['findings'][:-1], old['findings'])
        added = new['findings'][-1]
        self.assertEqual((added['id'], added['outcome']), ('nct01801436', 'disagrees'))
        rep = json.loads((cf.ROOT / added['report']).read_text())
        self.assertEqual(hashlib.sha256((cf.ROOT / added['report']).read_bytes()).hexdigest(), added['report_file_sha256'])
        self.assertEqual({m: r['primary_class'] for m, r in rep['results'].items()},
                         {'bortezomib_pk_lignet_2022': 'model_under_predicts', 'bortezomib_pbpk_iwasaki_2020_candidate': 'model_under_predicts'})

    def test_blindness_comes_from_the_ledger(self):
        blind = {r['id']: r['blindness'] for r in self.rows if r['blind']}
        self.assertEqual(blind, {'bridoux_hughes_kim': 'checked_blind_with_deviation', 'dexamethasone_outside': 'checked_blind',
                                 'eligibility_v1': 'checked_blind', 'eligibility_v2': 'checked_blind', 'eligibility_llm_c1': 'checked_blind',
                                 'nct01801436': 'checked_blind'})
        self.assertEqual(self.view['blind'], 6)

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
