"""Lenalidomide renal recheck (Hughes 2019, Kim 2026) with study-matched virtual subjects."""
import hashlib
import json
import subprocess
import unittest
from pathlib import Path

from intelligence_store import renal_group_recheck as rc

ROOT = Path(__file__).resolve().parent.parent


class Plan(unittest.TestCase):
    def test_plan_pinned_and_locked_before_module(self):
        self.assertEqual(hashlib.sha256(rc.PLAN_PATH.read_bytes()).hexdigest(), rc.PLAN_SHA256)
        self.assertEqual(rc.load_plan()['status'], 'locked_before_computation')
        try:
            blob = subprocess.run(['git', 'show', 'd163781:intelligence_store/data/lenalidomide_renal_recheck_plan_v1.json'],
                                  cwd=ROOT, capture_output=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            self.skipTest('git history not available')
        self.assertEqual(hashlib.sha256(blob).hexdigest(), rc.PLAN_SHA256)

    def test_demographics_match_the_publication(self):
        d = rc.load_demographics(rc.load_plan())
        self.assertEqual(d['moderate']['female_male'], [1, 5])
        self.assertEqual(d['moderate']['crcl_range'], [33, 46])
        self.assertEqual(d['normal']['crcl_range'], [83, 145])
        self.assertEqual(sum(sum(d[g]['female_male']) for g in d), 24)

    def test_v1_constants_match_the_v1_reports(self):
        for m, path in rc.V1_REPORTS.items():
            self.assertEqual(json.loads((ROOT / path).read_text())['primary_endpoint_by_group'], rc.V1_PRIMARY[m])


class Subjects(unittest.TestCase):
    def test_truncated_normal_stays_in_range_and_sex_counts_exact(self):
        import random
        d = rc.load_demographics(rc.load_plan())
        rng = random.Random(1)
        for _ in range(200):
            subs = rc.draw_group(rng, d['severe'], 'primary')
            self.assertEqual([s['sex'] for s in subs].count('FEMALE'), 4)
            self.assertTrue(all(17 <= s['crcl'] <= 29 for s in subs))


class LockedResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = rc.run_check()

    def test_committed_report_reproduces_exactly(self):
        self.assertEqual(self.report, json.loads(rc.REPORT_PATH.read_text()))

    def test_findings(self):
        r = self.report['result_by_model']
        self.assertEqual(r['lenalidomide_hughes_2019']['change_from_v1'], {'mild': 'unchanged', 'moderate': 'unchanged', 'severe': 'unchanged'})
        self.assertEqual(r['lenalidomide_kim_2026']['primary']['moderate'], 'model_under_predicts')
        self.assertEqual(r['lenalidomide_kim_2026']['change_from_v1']['moderate'], 'changed')
        for m in r:
            for g in ('moderate', 'severe'):
                self.assertEqual(r[m]['across_scenarios'][g], ['model_under_predicts'])
        self.assertIs(self.report['clinical_prediction_validated'], False)


if __name__ == '__main__':
    unittest.main()
