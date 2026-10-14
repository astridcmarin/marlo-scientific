"""Simulation 3.0c: bortezomib platelet model and the locked reading check."""
import json
from pathlib import Path
import tempfile
import unittest

from intelligence_store.patient_state import digest
from intelligence_store.bortezomib_pk import standard_regimen
from intelligence_store.bortezomib_platelets import PLAN_SHA256, load_plan, run_check, simulate

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'docs' / 'verification' / 'bortezomib_platelet_check_v1.json'


class Model(unittest.TestCase):
    def test_no_drug_keeps_every_compartment_at_baseline(self):
        for variant in ('myelosuppression', 'platelet_budding'):
            result = simulate(variant, 'ng_per_ml', 'unbounded_as_printed', [], 200.0, record_at=(200.0,))
            self.assertEqual(result['recorded'][200.0], 1.0)

    def test_drug_lowers_then_feedback_restores_platelets(self):
        events = standard_regimen(1.3, cycles=1)
        result = simulate('myelosuppression', 'ng_per_ml', 'unbounded_as_printed', events, 504.0, record_at=(240.0, 504.0))
        self.assertLess(result['recorded'][240.0], 0.8)
        self.assertGreater(result['recorded'][504.0], 0.95)

    def test_budding_in_nm_as_printed_breaks_down(self):
        result = simulate('platelet_budding', 'nM', 'unbounded_as_printed', standard_regimen(1.3, cycles=1), 504.0)
        self.assertEqual(result['status'], 'invalid_state')

    def test_unknown_reading_is_refused(self):
        with self.assertRaises(ValueError):
            simulate('myelosuppression', 'mg_per_l', 'bounded_at_zero', [], 10.0)


class LockedCheck(unittest.TestCase):
    def test_plan_is_pinned(self):
        self.assertEqual(load_plan()['status'], 'locked_before_computation')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'plan.json'
            path.write_bytes((ROOT / 'intelligence_store/data/bortezomib_platelet_check_plan_v1.json').read_bytes() + b' ')
            with self.assertRaises(ValueError):
                load_plan(path)

    def test_committed_report_reproduces_exactly(self):
        committed = json.loads(REPORT.read_text())
        self.assertEqual(committed['plan_sha256'], PLAN_SHA256)
        self.assertEqual(run_check()['report_sha256'], committed['report_sha256'])
        body = {k: v for k, v in committed.items() if k != 'report_sha256'}
        self.assertEqual(digest(body), committed['report_sha256'])

    def test_recorded_decision(self):
        committed = json.loads(REPORT.read_text())
        self.assertEqual(committed['decision']['adopted_primary_reading'],
                         {'units': 'ng_per_ml', 'effect_bound': 'unbounded_as_printed'})
        consistent = [(r['variant'], r['units'], r['effect_bound']) for r in committed['rows'] if r['classification'] == 'consistent']
        self.assertEqual(consistent, [('myelosuppression', 'ng_per_ml', 'unbounded_as_printed'),
                                      ('platelet_budding', 'ng_per_ml', 'unbounded_as_printed')])
        self.assertTrue(all(r.get('numerically_resolved', True) for r in committed['rows']))
        self.assertFalse(committed['clinical_prediction_validated'])


if __name__ == '__main__':
    unittest.main()
