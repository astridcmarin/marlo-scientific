"""Simulation 3.0f: locked external consistency check of the bortezomib PK component against Ogawa 2008."""
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

from intelligence_store import bortezomib_pk_ogawa_check as check

ROOT = Path(__file__).resolve().parents[1]
TIMES = [0.0833333333333, 0.25, 0.5, 1, 2, 4, 6, 8, 12, 24, 48]


class NCA(unittest.TestCase):
    def test_mono_exponential_known_answers(self):
        conc = [100 * math.exp(-0.1 * t) for t in TIMES]
        exact = check.nca(TIMES, conc, 'linear_up_log_down', 3)
        self.assertAlmostEqual(exact['c0_ng_ml'], 100.0, places=9)
        self.assertAlmostEqual(exact['auc_ng_h_ml'], 1000.0, places=6)
        self.assertAlmostEqual(exact['half_life_h'], math.log(2) / 0.1, places=9)
        linear = check.nca(TIMES, conc, 'linear', 3)
        self.assertGreater(linear['auc_ng_h_ml'], 1000.0)  # linear trapezoids overestimate a falling exponential

    def test_bad_profiles_rejected(self):
        with self.assertRaises(ValueError):
            check.nca(TIMES, [1.0] * 10, 'linear', 3)
        with self.assertRaises(ValueError):
            check.nca(TIMES, [1.0] * 11, 'linear', 3)  # flat terminal phase
        with self.assertRaises(ValueError):
            check.nca(TIMES, [100 * math.exp(-0.1 * t) for t in TIMES], 'spline', 3)

    def test_t_quantiles(self):
        try:
            from scipy.stats import t
        except ImportError:
            self.skipTest('scipy not installed')
        for df, q in check.T975.items():
            self.assertAlmostEqual(q, t.ppf(0.975, df), places=3)


class LockedCheck(unittest.TestCase):
    def test_plan_and_observed_are_pinned(self):
        for path, pin, loader in ((check.PLAN_PATH, check.PLAN_SHA256, check.load_plan),
                                  (check.OBSERVED_PATH, check.OBSERVED_SHA256, check.load_observed)):
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), pin)
            with tempfile.TemporaryDirectory() as tmp:
                changed = Path(tmp) / path.name
                changed.write_bytes(path.read_bytes() + b' ')
                with self.assertRaises(ValueError):
                    loader(changed)
        self.assertEqual(check.load_plan()['status'], 'locked_before_computation')

    def test_committed_report_reproduces_exactly(self):
        committed = json.loads(check.REPORT_PATH.read_text())
        self.assertEqual(check.run_check(), committed)

    def test_day1_profile_holds_only_the_first_dose(self):
        from intelligence_store.bortezomib_pk import concentration_curve
        prof = check.model_profiles(1.3, TIMES)
        single = concentration_curve([(0.0, 1.3)], TIMES)  # day 1 samples end before the 72 h dose
        for a, b in zip(prof['day1_ng_ml'], single):
            self.assertAlmostEqual(a, b, places=12)
        self.assertTrue(all(b > a for a, b in zip(prof['day1_ng_ml'], prof['day11_ng_ml'])))  # carry-over on day 11

    def test_findings_and_flags(self):
        report = check.run_check()
        self.assertIs(report['clinical_prediction_validated'], False)
        self.assertFalse(report['decision']['externally_consistent_at_1_3_mg_m2'])
        lead = next(r for r in report['rows'] if r['dose_mg_m2'] == 1.3)
        primary = lead['readings'][0]['endpoints']
        self.assertEqual(primary['auc_day1']['classification'], 'model_over_predicts')
        self.assertEqual(primary['auc_day11']['classification'], 'consistent')
        self.assertEqual(primary['auc_ratio_day11_over_day1']['classification'], 'model_under_predicts')
        for k in ('auc_day1', 'auc_day11', 'auc_ratio_day11_over_day1'):
            self.assertTrue(lead['robust_across_readings'][k])
        # Context: emulation below the model's own AUC because 48 h sampling misses the slow phase.
        self.assertLess(primary['auc_day1']['model_emulated'], lead['model_without_emulation']['auc_single_dose_to_infinity_ng_h_ml'])


if __name__ == '__main__':
    unittest.main()
