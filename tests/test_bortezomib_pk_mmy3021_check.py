"""Simulation 3.0m: locked check of the constant-clearance bortezomib PK component against MMY-3021 day 11 exposure."""
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from intelligence_store import bortezomib_pk_mmy3021_check as check
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
        plan = check.load_plan()
        self.assertEqual(plan['status'], 'locked_before_computation')
        self.assertEqual(plan['data']['observed_sha256'], check.OBSERVED_SHA256)

    def test_plan_committed_before_module(self):
        """The plan's locking commit is an ancestor of HEAD, and the plan file there equals the pinned one."""
        try:
            blob = subprocess.run(['git', 'show', 'b921f21:intelligence_store/data/bortezomib_pk_mmy3021_check_plan_v1.json'],
                                  cwd=ROOT, capture_output=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            self.skipTest('git history not available')
        self.assertEqual(hashlib.sha256(blob).hexdigest(), check.PLAN_SHA256)

    def test_observed_values(self):
        obs = check.load_observed()
        t = obs['table1_iv_day11']
        self.assertEqual((t['n'], t['auc_last_ng_h_ml'], t['cmax_ng_ml']), (14, [151, 42.9], [223, 101]))
        self.assertEqual(len(obs['design']['pk_sampling_times_after_dose_h']), 13)


class Profiles(unittest.TestCase):
    def test_day11_matches_the_can1004_module(self):
        times = check.load_observed()['design']['pk_sampling_times_after_dose_h']
        ours = check.day11_profile(times)
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
        self.assertIs(self.report['clinical_prediction_validated'], False)
        d = self.report['decision']
        self.assertTrue(d['consistent_with_mmy3021_day11'])
        self.assertFalse(d['can1004_day11_finding_reproduced'])
        self.assertFalse(d['robust_primary'])
        self.assertEqual(self.report['classifications_across_readings']['auc_last_day11'], ['consistent', 'model_under_predicts'])
        self.assertEqual(self.report['classifications_across_readings']['cmax_day11'], ['model_under_predicts'])
        primary = self.report['readings'][0]['endpoints']['auc_last_day11']
        self.assertAlmostEqual(primary['interval_95'][0], 151 - 2.1604 * 42.9 / 14 ** 0.5, places=9)


if __name__ == '__main__':
    unittest.main()
