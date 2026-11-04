"""Simulation 2.0d: renal pathways v2, built and run as its locked plan states."""
import json
import unittest

from intelligence_store import lenalidomide_renal_pathways_v2 as rp2
from intelligence_store.lenalidomide_renal_pathways import calibrate, load_evidence, pathways
from intelligence_store.patient_state import digest
from tests.report_reproduction import assert_reproduces


class Model(unittest.TestCase):
    def test_k1_is_the_current_model(self):
        cal = calibrate(load_evidence(), 110, 0.77)
        for crcl in (15, 40, 90):
            self.assertAlmostEqual(rp2.clearances_v2(cal, crcl, 1.0)['total_ml_min'],
                                   pathways(cal, crcl, 'A_intact_nephron')['total_ml_min'], places=10)

    def test_larger_k_lowers_clearance_below_the_reference(self):
        cal = calibrate(load_evidence(), 110, 0.77)
        self.assertLess(rp2.clearances_v2(cal, 40, 2.0)['renal_ml_min'], rp2.clearances_v2(cal, 40, 1.0)['renal_ml_min'])
        self.assertAlmostEqual(rp2.clearances_v2(cal, 110, 2.0)['renal_ml_min'], rp2.clearances_v2(cal, 110, 1.0)['renal_ml_min'])

    def test_rejects_bad_input(self):
        cal = calibrate(load_evidence(), 110, 0.77)
        with self.assertRaises(rp2.RenalPathwaysV2Error):
            rp2.clearances_v2(cal, 0, 1.0)


class LockedReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.committed = json.loads(rp2.REPORT_PATH.read_text())
        cls.fresh = rp2.run_check()

    def test_committed_report_reproduces(self):
        assert_reproduces(self, self.fresh, self.committed)
        body = {k: v for k, v in self.committed.items() if k != 'report_sha256'}
        self.assertEqual(digest(body), self.committed['report_sha256'])

    def test_recorded_result(self):
        d = self.committed['decision']
        self.assertAlmostEqual(d['k'], 1.4787, places=3)
        self.assertFalse(d['k_at_bound'])
        self.assertEqual(d['deciding_comparisons'], {'bridoux_moderate': 'model_over_predicts', 'bridoux_severe': 'consistent',
                                                     'kim_moderate': 'consistent', 'kim_severe': 'consistent'})
        self.assertEqual(d['outcome'], 'partial_reported_not_adopted')
        self.assertEqual(self.committed['classification'], 'checks_on_seen_but_unfitted_data_not_blind')
        self.assertFalse(self.committed['clinical_prediction_validated'])

    def test_current_model_comparator_recorded(self):
        v1 = self.committed['primary']
        self.assertEqual({g: v1['bridoux']['v1'][g]['classification'] for g in ('moderate', 'severe')},
                         {'moderate': 'consistent', 'severe': 'consistent'})
        self.assertEqual({g: v1['kim']['v1'][g]['classification'] for g in ('control', 'moderate', 'severe')},
                         {g: 'consistent' for g in ('control', 'moderate', 'severe')})

    def test_numerical_checks(self):
        n = self.committed['numerical_checks']
        self.assertTrue(n['k1_equals_2_0a_pass'] and n['secretion_non_negative_and_falls_with_crcl_pass'])
        self.assertTrue(self.committed['primary']['fit']['not_above_grid'])


if __name__ == '__main__':
    unittest.main()
