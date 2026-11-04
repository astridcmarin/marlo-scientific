"""Simulation 2.0e: the 2.0a comparison across bioavailability, run as plan v3 states."""
import json
import unittest

from intelligence_store import lenalidomide_renal_pathways_f as rf
from intelligence_store.lenalidomide_renal_pathways import load_evidence
from intelligence_store.patient_state import digest
from tests.report_reproduction import assert_reproduces


class Model(unittest.TestCase):
    def test_renal_clearance_does_not_depend_on_f(self):
        ev = load_evidence()
        a, b = rf.calibrate_f(ev, 1.0), rf.calibrate_f(ev, 0.9)
        self.assertAlmostEqual(a['renal_ml_min'], b['renal_ml_min'])
        self.assertLess(b['non_renal_ml_min'], a['non_renal_ml_min'])
        self.assertAlmostEqual(rf.calibrate_f(ev, 0.85)['non_renal_ml_min'], 0.0, places=6)


class LockedReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.committed = json.loads(rf.REPORT_PATH.read_text())
        cls.fresh = rf.run_check()

    def test_committed_report_reproduces(self):
        assert_reproduces(self, self.fresh, self.committed)
        body = {k: v for k, v in self.committed.items() if k != 'report_sha256'}
        self.assertEqual(digest(body), self.committed['report_sha256'])

    def test_recorded_decision(self):
        d = self.committed['decision']
        self.assertEqual(d['D1_band_status']['moderate']['status'], 'depends_on_bioavailability')
        self.assertEqual(d['D1_band_status']['severe']['status'], 'depends_on_bioavailability')
        self.assertEqual(d['D2_faster_than_proportional'], 'not_established')
        self.assertEqual(d['D3_non_renal']['status'], 'depends_on_bioavailability')
        self.assertFalse(d['D4_myeloma_note']['moderate']['holds_at_every_F'])
        self.assertEqual(self.committed['classification'], 'checks_on_seen_data_not_blind')
        self.assertFalse(self.committed['clinical_prediction_validated'])

    def test_lower_f_worsens_the_end_stage_prediction(self):
        esrd = {F: s['esrd_auc_by_residual_crcl']['0'] for F, s in self.committed['scenarios'].items()}
        self.assertLess(esrd['1.00'], esrd['0.95'])
        self.assertLess(esrd['0.95'], esrd['0.90'])
        self.assertIsNone(esrd['0.85'])

    def test_numerical_check(self):
        self.assertLess(self.committed['numerical_checks']['F1_reproduces_2_0a_max_relative_difference'], 1e-12)


if __name__ == '__main__':
    unittest.main()
