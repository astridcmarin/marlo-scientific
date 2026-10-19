"""Simulation 3.0g: locked check of the Kuan 2012 bortezomib PK model (saturable return) against Ogawa 2008."""
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

from intelligence_store import bortezomib_pk_kuan_check as check

TIMES = [0.0833333333333, 0.25, 0.5, 1, 2, 4, 6, 8, 12, 24, 48]


class Pinned(unittest.TestCase):
    def test_extract_and_plan_are_pinned_and_locked(self):
        for path, pin, loader in ((check.EXTRACT_PATH, check.EXTRACT_SHA256, check.load_extract),
                                  (check.PLAN_PATH, check.PLAN_SHA256, check.load_plan)):
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), pin)
            with tempfile.TemporaryDirectory() as tmp:
                changed = Path(tmp) / path.name
                changed.write_bytes(path.read_bytes() + b' ')
                with self.assertRaises(ValueError):
                    loader(changed)
        self.assertEqual(check.load_plan()['status'], 'locked_before_computation')

    def test_transcribed_values(self):
        p = check.parameters(check.load_extract(), 'table2_posterior_mean')
        self.assertEqual(p, {'CL': 10.8, 'V1': 14.1, 'Q2': 46.3, 'Q3': 51.7, 'V2': 349, 'V3': 895, 'Km': 0.06, 'Vm': 0.0926})
        self.assertEqual(check.parameters(check.load_extract(), 'table3_posterior_median')['V2'], 210)


class Solver(unittest.TestCase):
    def setUp(self):
        self.p = check.parameters(check.load_extract(), 'table2_posterior_mean')

    def test_linear_reference_matches_the_exact_solution(self):
        k21 = self.p['Q2'] / self.p['V2']
        rk, _ = check.simulate(self.p, 2.0, TIMES, return_override=k21, dose_times_h=(0.0,))
        exact = check._exact_linear(self.p, 2.0, TIMES, k21)
        for t in TIMES:
            self.assertAlmostEqual(rk[t] / exact[t], 1.0, places=6)
        self.assertAlmostEqual(check._exact_linear(self.p, 2.0, [0.0], k21)[0.0], 1000 * 2.0 / self.p['V1'], places=9)

    def test_amount_is_conserved_under_both_readings(self):
        for reading in check.READINGS:
            _, balance = check.simulate(self.p, 2.0, [1.0, 300.0], reading, step_h=0.01)
            self.assertLess(balance, 1e-9)

    def test_readings_differ_as_described(self):
        # Reading A: return rate constant Vm/(Km + C2) is about 1.5 per hour when Peripheral 2 is nearly empty.
        self.assertAlmostEqual(self.p['Vm'] / self.p['Km'], 1.5433, places=3)
        a, _ = check.simulate(self.p, 2.0, [24.0], 'A_rate_constant', step_h=0.01, dose_times_h=(0.0,))
        b, _ = check.simulate(self.p, 2.0, [24.0], 'B_clearance', step_h=0.01, dose_times_h=(0.0,))
        self.assertGreater(a[24.0], b[24.0])  # under B almost nothing returns from Peripheral 2

    def test_unknown_reading_rejected(self):
        with self.assertRaises(ValueError):
            check.simulate(self.p, 2.0, [1.0], 'C_other')


class LockedResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = check.run_check()

    def test_committed_report_reproduces_exactly(self):
        self.assertEqual(self.report, json.loads(check.REPORT_PATH.read_text()))

    def test_numerical_checks_pass(self):
        checks = self.report['numerical_checks']
        self.assertTrue(checks['linear_reference_passed'] and checks['step_halving_passed'] and checks['amount_balance_passed'])

    def test_findings(self):
        self.assertIs(self.report['clinical_prediction_validated'], False)
        self.assertEqual(self.report['result_at_1_3_mg_m2'],
                         {'auc_day1': 'model_over_predicts', 'auc_day11': 'consistent',
                          'auc_ratio_day11_over_day1': 'model_under_predicts'})
        self.assertFalse(self.report['decision']['resolves_3_0f_findings_at_1_3_mg_m2'])
        # Under every reading, parameter set and body size, no condition reproduces the day 1 to day 11 rise at 1.3 mg/m2.
        for condition in self.report['conditions']:
            lead = next(r for r in condition['rows'] if r['dose_mg_m2'] == 1.3)['nca_readings'][0]['endpoints']
            self.assertEqual(lead['auc_ratio_day11_over_day1']['classification'], 'model_under_predicts')
            self.assertLess(lead['auc_ratio_day11_over_day1']['model'], 1.5)


if __name__ == '__main__':
    unittest.main()
