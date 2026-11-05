"""Bridoux 2016 check (2.1h): the committed report regenerates under the locked plan, and its reading is recorded."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_reproduction import assert_reproduces  # noqa: E402

from intelligence_store import lenalidomide_bridoux_check as bc  # noqa: E402
from intelligence_store.patient_state import digest  # noqa: E402


class LockedReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.committed = json.loads(bc.REPORT_PATH.read_text())
        cls.fresh = bc.run_check()

    def test_committed_report_reproduces(self):
        assert_reproduces(self, self.fresh, self.committed)
        body = {k: v for k, v in self.committed.items() if k != 'report_sha256'}
        self.assertEqual(digest(body), self.committed['report_sha256'])

    def test_inputs_are_the_pinned_files(self):
        self.assertEqual(self.committed['plan_sha256'], bc.PLAN_SHA256)
        self.assertEqual(self.committed['design_sha256'], bc.DESIGN_SHA256)
        self.assertEqual(self.committed['observed_sha256'], bc.OBSERVED_SHA256)
        self.assertEqual(self.committed['trials'], 10000)
        self.assertEqual(self.committed['seed'], 20261101)

    def test_observed_ratios_follow_from_table_2(self):
        obs = bc.load_observed()['groups']
        dn = {g: obs[g]['auc24_gm'] / obs[g]['dose_mg_per_24h'] for g in bc.SIMULATED}
        for m in bc.MODELS:
            for row in self.committed['scenarios']['primary'][m]:
                if 'dose_normalised_ratio_to_normal' in row:
                    self.assertAlmostEqual(row['dose_normalised_ratio_to_normal']['observed'], dn[row['group']] / dn['normal'])

    def test_result_and_its_reading(self):
        r = self.committed['result_by_model']
        for m in bc.MODELS:
            self.assertEqual(r[m]['primary']['mild'], 'consistent')
            self.assertEqual(r[m]['primary']['severe'], 'model_under_predicts')
            self.assertEqual(r[m]['primary']['moderate'], 'model_under_predicts')
        self.assertTrue(r['lenalidomide_hughes_2019']['robust_across_scenarios']['moderate'])
        self.assertFalse(r['lenalidomide_kim_2026']['robust_across_scenarios']['moderate'])
        self.assertFalse(self.committed['clinical_prediction_validated'])
        self.assertNotIn('esrd', {row['group'] for row in self.committed['scenarios']['primary']['lenalidomide_hughes_2019']})


if __name__ == '__main__':
    unittest.main()
