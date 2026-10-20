"""Simulation 3.0h: locked check of the constant-clearance bortezomib PK component against CAN-1004 (FDA review)."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from intelligence_store import bortezomib_pk_can1004_check as check
from intelligence_store.bortezomib_pk import concentration_curve


class Pinned(unittest.TestCase):
    def test_plan_and_observed_are_pinned_and_locked(self):
        for path, pin, loader in ((check.PLAN_PATH, check.PLAN_SHA256, check.load_plan),
                                  (check.OBSERVED_PATH, check.OBSERVED_SHA256, check.load_observed)):
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), pin)
            with tempfile.TemporaryDirectory() as tmp:
                changed = Path(tmp) / path.name
                changed.write_bytes(path.read_bytes() + b' ')
                with self.assertRaises(ValueError):
                    loader(changed)
        self.assertEqual(check.load_plan()['status'], 'locked_before_computation')

    def test_transcribed_values_match_the_quoted_rows(self):
        obs = check.load_observed()
        iv, quotes = obs['table7']['iv'], obs['table7']['row_quotes']
        self.assertIn('104 (99.0)', quotes[0])
        self.assertIn('241 (82.0)', quotes[0])
        self.assertEqual(iv['auc_last_ng_h_ml'], {'day1': [104, 99.0], 'day11': [241, 82.0]})
        self.assertEqual(iv['auc_inf_ng_h_ml'], {'day1': [183, 158], 'day11': [409, 187]})
        self.assertEqual(len(obs['design']['pk_sampling_times_after_dose_h']), 12)
        self.assertEqual(obs['design']['pk_sampling_times_after_dose_h'][-1], 72)


class Profiles(unittest.TestCase):
    def test_day1_holds_only_the_first_dose_and_72h_is_pre_dose(self):
        times = check.load_observed()['design']['pk_sampling_times_after_dose_h']
        prof = check.model_profiles(times)
        single = concentration_curve([(0.0, check.DOSE_MG_M2)], times)
        for a, b in zip(prof['day1_ng_ml'], single):
            self.assertAlmostEqual(a, b, places=12)
        self.assertTrue(all(b > a for a, b in zip(prof['day1_ng_ml'], prof['day11_ng_ml'])))


class LockedResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = check.run_check()

    def test_committed_report_reproduces_exactly(self):
        self.assertEqual(self.report, json.loads(check.REPORT_PATH.read_text()))

    def test_findings(self):
        self.assertIs(self.report['clinical_prediction_validated'], False)
        decision = self.report['decision']
        self.assertEqual(decision['result'], {'auc_last_day1': 'consistent', 'auc_last_day11': 'model_under_predicts'})
        self.assertFalse(decision['consistent_with_can1004'])
        self.assertFalse(decision['ogawa_day1_finding_reproduced'])
        self.assertTrue(decision['robust_primary'])
        ratio = self.report['readings'][0]['endpoints']['ratio_of_means_auc_last_day11_over_day1']
        self.assertLess(ratio['model_emulated'], ratio['observed'])


if __name__ == '__main__':
    unittest.main()
