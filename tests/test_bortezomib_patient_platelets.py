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

    def test_changed_context_is_refused(self):
        name = 'bortezomib_platelet_context_v1.json'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / name
            path.write_bytes((DATA / name).read_bytes() + b' ')
            with self.assertRaises(CovariateEstimationError):
                load_context(path)


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

    def test_low_baselines_bring_warnings_and_the_matching_incidence(self):
        low = patient_platelet_view(self.with_platelets(60, self.revision).id)
        self.assertIn('24%', low['observed_context']['incidence_for_this_baseline'])
        self.assertEqual(low['eligibility_warnings'], [])
        below = self.with_platelets(40, self.revision)
        self.assertIn('usual entry threshold', patient_platelet_view(below.id)['eligibility_warnings'][0])
        lowest = save_revision(self.scenario.id, copy.deepcopy(below.payload['state']) | {'fields': {
            **below.payload['state']['fields'], 'platelet_count': {**below.payload['state']['fields']['platelet_count'], 'value': 20.0}}},
            parent_revision_id=below.id, title='Platelets 20')
        self.assertIn('below every entry threshold', patient_platelet_view(lowest.id)['eligibility_warnings'][0])

    def test_page_and_detail_link(self):
        rev = self.with_platelets(160, self.revision)
        base = f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{rev.id}'
        detail = self.client.get(base).get_data(as_text=True)
        self.assertIn('Bortezomib platelet curve', detail)
        text = self.client.get(base + '/bortezomib-platelets?cycles=2').get_data(as_text=True)
        for expected in ('Hypothetical typical curve — not a prediction for this patient', 'Baseline platelet count',
                         'Observed in the source study', 'Common Toxicity Criteria version 2.0', 'grade 2'):
            self.assertIn(expected, text)
        data = self.client.get(base + '/bortezomib-platelets?format=json').get_json()
        self.assertEqual(data['baseline_1e9_per_l'], 160.0)
        missing = self.client.get(f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{self.revision.id}/bortezomib-platelets')
        self.assertIn('No baseline platelet count', missing.get_data(as_text=True))
        for bad in ('?cycles=9', '?x=1'):
            self.assertEqual(self.client.get(base + '/bortezomib-platelets' + bad).status_code, 400)


if __name__ == '__main__':
    unittest.main()
