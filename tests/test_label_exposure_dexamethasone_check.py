"""Phase 3.1g: label-based dexamethasone curve against the NEOFORDEX EPAR studies (MM-017, CPA-402-11)."""
import json
import math
from pathlib import Path
import tempfile
import unittest

from intelligence_store import label_exposure_dexamethasone_check as chk


class Inputs(unittest.TestCase):
    def test_plan_and_extract_are_pinned(self):
        for loader, path in ((chk.load_plan, chk.PLAN_PATH), (chk.load_observed, chk.OBSERVED_PATH)):
            with tempfile.TemporaryDirectory() as tmp:
                changed = Path(tmp) / path.name
                changed.write_bytes(path.read_bytes() + b' ')
                with self.assertRaises(ValueError):
                    loader(changed)
        plan = chk.load_plan()
        self.assertEqual(plan['status'], 'locked_before_computation')
        self.assertEqual(plan['source']['sha256'], chk.load_observed()['source']['file_reviewed']['sha256'])

    def test_transcribed_values(self):
        o = chk.load_observed()
        self.assertEqual(o['MM_017']['day2_dex_alone']['auc_inf_ng_h_ml'], [3661, 43.8])
        self.assertEqual(o['CPA_402_11']['reference']['auc_inf_ug_h_l'], [1213.52, 423.72])

    def test_intervals(self):
        lo, hi = chk.ci_geometric(100.0, 30.0, 6)
        self.assertAlmostEqual(math.sqrt(lo * hi), 100.0)
        self.assertEqual(chk.ci_arithmetic(10.0, 2.0, 24), [10.0 - 2.0687 * 2 / math.sqrt(24), 10.0 + 2.0687 * 2 / math.sqrt(24)])


class LockedResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = chk.run_check()

    def test_committed_report_reproduces_exactly(self):
        self.assertEqual(self.report, json.loads(chk.REPORT_PATH.read_text()))

    def test_findings(self):
        r = self.report
        self.assertIs(r['clinical_prediction_validated'], False)
        self.assertTrue(r['decision']['curve_consistent_with_outside_data'])
        self.assertEqual(r['primary_mm017_auc_inf_40mg']['classification'], 'consistent')
        self.assertAlmostEqual(r['primary_mm017_auc_inf_40mg']['ratio_model_to_observed'], 0.696, places=3)
        cpa = r['secondary']['cpa_402_11_20mg']
        self.assertEqual({a: cpa[a]['auc_inf']['classification'] for a in cpa}, {'test': 'consistent', 'reference': 'consistent'})
        self.assertEqual(r['decision']['cmax_classifications'],
                         {'mm017': 'consistent', 'cpa_test': 'model_over_predicts', 'cpa_reference': 'model_under_predicts'})
        self.assertIsNone(r['descriptive']['spoorenberg_2014_scaled_to_20mg']['classification'])


if __name__ == '__main__':
    unittest.main()
