"""Simulation 3.0n: reproduction check of the bortezomib PK component against Reece 2011 (not an outside check)."""
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from intelligence_store import bortezomib_pk_reece_reproduction as check
from intelligence_store import bortezomib_pk_can1004_check as can

ROOT = Path(__file__).resolve().parent.parent


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

    def test_plan_committed_before_module(self):
        try:
            blob = subprocess.run(['git', 'show', '1c3591f:intelligence_store/data/bortezomib_pk_reece_reproduction_plan_v1.json'],
                                  cwd=ROOT, capture_output=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            self.skipTest('git history not available')
        self.assertEqual(hashlib.sha256(blob).hexdigest(), check.PLAN_SHA256)

    def test_observed_values(self):
        t2 = check.load_observed()['table2']
        self.assertEqual(t2['1.3']['c1d1']['auc48'], [34.6, 19.8, 12])
        self.assertEqual(t2['1.3']['c1d11']['auc48'], [82.4, 28.6, 11])
        self.assertEqual(t2['1.3']['c3d11']['auc48'], [85.2, 18.7, 9])
        self.assertEqual(t2['1.0']['c1d1']['auc48'], [26.5, 12.4, 11])


class Profiles(unittest.TestCase):
    def test_cycle1_matches_the_can1004_module(self):
        times = check.load_observed()['design']['pk_sampling_times_after_dose_h']
        ours = check.profile(1.3, 240.0, times)
        theirs = can.model_profiles(times)['day11_ng_ml']
        for a, b in zip(ours, theirs):
            self.assertAlmostEqual(a, b, places=12)


class LockedResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = check.run_check()

    def test_committed_report_reproduces_exactly(self):
        self.assertEqual(self.report, json.loads(check.REPORT_PATH.read_text()))

    def test_findings(self):
        d = self.report['decision']
        self.assertFalse(d['reproduces_reece_at_1_3'])
        self.assertEqual(d['result']['auc48_c1d1_1.3'], 'model_over_predicts')
        self.assertFalse(d['robust_primary'])
        robust = self.report['classifications_across_readings']
        self.assertEqual(robust['auc48_c1d1_1.3'], ['model_over_predicts'])
        self.assertEqual(robust['auc48_c1d1_1.0'], ['model_over_predicts'])
        e = self.report['readings'][0]['endpoints']
        self.assertLess(e['ratio_auc48_c1d11_over_c1d1_1.3']['model_emulated'], e['ratio_auc48_c1d11_over_c1d1_1.3']['observed'])
        self.assertIs(self.report['clinical_prediction_validated'], False)


if __name__ == '__main__':
    unittest.main()
