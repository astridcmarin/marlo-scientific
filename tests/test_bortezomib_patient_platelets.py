"""Patient Lab 2.2b: bortezomib platelet curves in a synthetic patient's absolute counts."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_kim_pk_runs as fixtures  # noqa: E402

from intelligence_store.covariate_estimation import CovariateEstimationError
from intelligence_store.patient_state import SCHEMA_V2
from intelligence_store.patient_state_revisions import save_revision
from intelligence_store.bortezomib_platelet_evidence import load_model_extract
from intelligence_store.bortezomib_platelets import simulate
from intelligence_store.bortezomib_pk import standard_regimen
from intelligence_store.bortezomib_patient_platelets import grade_for, load_context, patient_platelet_view

DATA = Path(__file__).resolve().parents[1] / 'intelligence_store' / 'data'


class ModelProperties(unittest.TestCase):
    def test_fraction_of_baseline_does_not_depend_on_the_starting_count(self):
        events = standard_regimen(1.3, cycles=1)
        for variant in ('myelosuppression', 'platelet_budding'):
            results = []
            for circ0 in (40.0, 171.0, 400.0):
                extract = copy.deepcopy(load_model_extract())
                extract['pd_model']['variants'][variant]['circ0_1e9_per_l'] = circ0
                r = simulate(variant, 'ng_per_ml', 'unbounded_as_printed', events, 504.0, record_at=(240.0, 504.0), extract=extract)
                results.append(r['recorded'])
            for other in results[1:]:
                for t in (240.0, 504.0):
                    self.assertAlmostEqual(other[t], results[0][t], places=12)

    def test_grading_bands(self):
        grading = load_context()['grading']
        self.assertEqual([grade_for(c, grading) for c in (80, 75, 74.9, 50, 49.9, 10, 9.9)], [None, None, 2, 2, 3, 3, 4])

    def test_ctcae_v5_bands_differ_only_at_grades_3_and_4(self):
        from intelligence_store.bortezomib_patient_platelets import load_ctcae_v5
        v5, v2 = load_ctcae_v5(), load_context()['grading']
        self.assertEqual([grade_for(c, v5) for c in (75, 60, 49.9, 25, 24.9, 9.9)], [None, 2, 3, 3, 4, 4])
        self.assertEqual([grade_for(c, v2) for c in (24.9, 9.9)], [3, 4])

    def test_changed_context_is_refused(self):
        from intelligence_store.bortezomib_patient_platelets import load_ctcae_v5
        for name, loader in (('bortezomib_platelet_context_v1.json', load_context),
                             ('platelet_grading_ctcae_v5_v1.json', load_ctcae_v5)):
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / name
                path.write_bytes((DATA / name).read_bytes() + b' ')
                with self.assertRaises(CovariateEstimationError):
                    loader(path)


class Scope(unittest.TestCase):
    def state(self, value):
        from intelligence_store.patient_state import example_state
        st = example_state()
        st['fields']['platelet_count'] = {'value': value, 'unit': '10^9/L', 'origin': 'synthetic_input'}
        return st

    def test_bands_and_refusal(self):
        from intelligence_store.bortezomib_patient_platelets import platelet_scope
        rule = lambda v: platelet_scope(self.state(v))['scope_evaluation']
        self.assertEqual(rule(29.9)['status'], 'out_of_scope')
        for v in (30, 49.9, 50, 1000):
            r = rule(v)
            self.assertEqual((r['status'], r['weakest_rule_tier'], r['flags']), ('in_scope', 'inside_model_data', []), v)
        self.assertIn('usual entry threshold', rule(40)['rules'][0]['band_note'])
        self.assertIn('At or above', rule(50)['rules'][0]['band_note'])

    def test_scope_matches_the_context_and_evidence_status(self):
        import json, hashlib
        from intelligence_store.bortezomib_patient_platelets import load_platelet_scope
        scope = load_platelet_scope()
        root = DATA.parents[1]
        for ref in scope['evidence'].values():
            self.assertEqual(hashlib.sha256((root / ref['file']).read_bytes()).hexdigest(), ref['sha256'], ref['file'])
        eligibility = load_context()['eligibility']
        rule = scope['state_rules'][0]
        self.assertEqual(rule['range'], [eligibility['minimum_with_extensive_marrow_involvement_1e9_per_l'], None])
        self.assertEqual(rule['tier_by_band'][0]['range'][0], eligibility['minimum_platelets_1e9_per_l'])
        status = json.loads((root / scope['evidence']['evidence_status']['file']).read_text())['models']
        self.assertEqual(status['bortezomib_platelets_lignet_2022']['layers']['external_consistency']['status'], 'not_done')
        self.assertEqual(status['bortezomib_pk_lignet_2022']['layers']['external_consistency']['result_at_1_3_mg_m2']['auc_day1'], 'model_over_predicts')
        self.assertEqual({o['tier'] for o in scope['outputs']['supported']}, {'inside_model_data'})
        self.assertFalse(scope['clinical_prediction_validated'])

    def test_stale_seven_fold_exposure_claim_is_gone(self):
        from intelligence_store.bortezomib_platelets import platelet_timecourse
        text = ' '.join(platelet_timecourse(1)['limitations'])
        self.assertNotIn('7-fold', text)
        self.assertIn('Ogawa 2008', text)


class PatientView(unittest.TestCase):
    setUp = fixtures.KimPKRunTests.setUp
    tearDown = fixtures.KimPKRunTests.tearDown

    def with_platelets(self, value, parent=None):
        parent = getattr(self, '_latest', self.revision)
        state = copy.deepcopy(fixtures.full_state())
        state['schema_version'] = SCHEMA_V2
        state['fields']['platelet_count'] = {'value': value, 'unit': '10^9/L', 'origin': 'synthetic_input',
                                             'observed_at': None, 'source_ref': 'Invented for test'}
        self._latest = save_revision(self.scenario.id, state, parent_revision_id=parent.id, title=f'Platelets {value}')
        return self._latest

    def test_v1_record_reports_missing_platelet_count(self):
        view = patient_platelet_view(self.revision.id)
        self.assertEqual(view['status'], 'missing_platelet_count')
        self.assertFalse(view['clinical_prediction_validated'])

    def test_absolute_curves_scale_the_typical_fraction(self):
        rev = self.with_platelets(160, self.revision)
        view = patient_platelet_view(rev.id, cycles=1)
        self.assertEqual(view['status'], 'completed')
        from intelligence_store.bortezomib_platelets import platelet_timecourse
        typical = platelet_timecourse(1)
        for name, v in view['variants'].items():
            for a, f in zip(v['absolute_1e9_per_l'], typical['variants'][name]['fraction_of_baseline']):
                self.assertAlmostEqual(a, 160 * f, places=9)
        self.assertAlmostEqual(view['observed_context']['illustrative_average_individual_nadir_1e9_per_l'], 64.0)
        self.assertIn('at most 1%', view['observed_context']['incidence_for_this_baseline'])
        self.assertEqual(view['eligibility_warnings'], [])
        self.assertEqual(view['current_grading']['system'], 'CTCAE v5.0')
        for v in view['variants'].values():
            self.assertIn('typical_curve_grade_at_lowest_ctcae_v5', v)

    def test_low_baselines_bring_warnings_and_the_matching_incidence(self):
        low = patient_platelet_view(self.with_platelets(60, self.revision).id)
        self.assertIn('24%', low['observed_context']['incidence_for_this_baseline'])
        self.assertEqual(low['eligibility_warnings'], [])
        below = self.with_platelets(40, self.revision)
        self.assertIn('usual entry threshold', patient_platelet_view(below.id)['eligibility_warnings'][0])
        lowest = save_revision(self.scenario.id, copy.deepcopy(below.payload['state']) | {'fields': {
            **below.payload['state']['fields'], 'platelet_count': {**below.payload['state']['fields']['platelet_count'], 'value': 20.0}}},
            parent_revision_id=below.id, title='Platelets 20')
        refused = patient_platelet_view(lowest.id)
        self.assertEqual(refused['status'], 'outside_model_scope')        # scope v1: below 30 is refused
        self.assertIn('below every entry threshold', refused['message'].lower())
        self.assertNotIn('variants', refused)
        self.assertEqual(refused['scope_evaluation']['status'], 'out_of_scope')
        allowed = patient_platelet_view(below.id)['scope_evaluation']
        self.assertEqual((allowed['status'], allowed['weakest_rule_tier']), ('in_scope', 'inside_model_data'))

    def test_page_and_detail_link(self):
        rev = self.with_platelets(160, self.revision)
        base = f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{rev.id}'
        detail = self.client.get(base).get_data(as_text=True)
        self.assertIn('Bortezomib platelet curve', detail)
        text = self.client.get(base + '/bortezomib-platelets?cycles=2').get_data(as_text=True)
        for expected in ('Hypothetical typical effect curve', 'Baseline platelet count',
                         'Observed in the source study', 'Common Toxicity Criteria version 2.0', 'grade 2', 'CTCAE v5.0'):
            self.assertIn(expected, text)
        data = self.client.get(base + '/bortezomib-platelets?format=json').get_json()
        self.assertEqual(data['baseline_1e9_per_l'], 160.0)
        missing = self.client.get(f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{self.revision.id}/bortezomib-platelets')
        self.assertIn('No baseline platelet count', missing.get_data(as_text=True))
        low = save_revision(self.scenario.id, copy.deepcopy(rev.payload['state']) | {'fields': {
            **rev.payload['state']['fields'], 'platelet_count': {**rev.payload['state']['fields']['platelet_count'], 'value': 20.0}}},
            parent_revision_id=rev.id, title='Platelets 20')
        out = self.client.get(f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{low.id}/bortezomib-platelets')
        self.assertEqual(out.status_code, 200)
        self.assertIn("Outside the model's scope", out.get_data(as_text=True))
        self.assertIn('/models/bortezomib_platelets_lignet_2022/scope', text)
        for bad in ('?cycles=9', '?x=1'):
            self.assertEqual(self.client.get(base + '/bortezomib-platelets' + bad).status_code, 400)


if __name__ == '__main__':
    unittest.main()
