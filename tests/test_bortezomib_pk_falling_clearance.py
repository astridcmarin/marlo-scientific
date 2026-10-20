"""Simulation 3.0i: falling-clearance forms calibrated on CAN-1004, to be checked against Ogawa 2008."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from intelligence_store import bortezomib_pk_falling_clearance as fc


class Plan(unittest.TestCase):
    def test_plan_is_pinned_and_locked(self):
        self.assertEqual(hashlib.sha256(fc.PLAN_PATH.read_bytes()).hexdigest(), fc.PLAN_SHA256)
        with tempfile.TemporaryDirectory() as tmp:
            changed = Path(tmp) / fc.PLAN_PATH.name
            changed.write_bytes(fc.PLAN_PATH.read_bytes() + b' ')
            with self.assertRaises(ValueError):
                fc.load_plan(changed)
        plan = fc.load_plan()
        self.assertEqual(plan['status'], 'locked_before_computation')
        self.assertEqual(set(plan['model']['forms']), set(fc.FORMS))
        self.assertEqual(plan['external_check']['endpoints']['primary'][0]['name'], 'auc_ratio_day11_over_day1')


class Model(unittest.TestCase):
    def setUp(self):
        self.p = fc.parameters()

    def test_lower_clearance_uses_only_the_can1004_ratio(self):
        self.assertAlmostEqual(self.p['clearance_ratio'], 6.60 / 17.9, places=12)
        self.assertAlmostEqual(self.p['cl_low_l_h_m2'], self.p['cl1_l_h_m2'] * 6.60 / 17.9, places=12)

    def test_forms(self):
        p = self.p
        self.assertAlmostEqual(fc.clearance('A_time', 0.0, p, 100.0, 1.3), p['cl1_l_h_m2'])
        self.assertAlmostEqual(fc.clearance('A_time', 1e6, p, 1.0, 1.3), p['cl_low_l_h_m2'])
        # Form B: CL1 for the whole first interval, then steps down with each earlier dose, less at a lower dose.
        self.assertEqual(fc.clearance('B_prior_dose', 1.0, p, 71.9, 1.3), p['cl1_l_h_m2'])
        day4, day11 = fc.clearance('B_prior_dose', 1.0, p, 72.0, 1.3), fc.clearance('B_prior_dose', 1.0, p, 240.0, 1.3)
        self.assertTrue(p['cl1_l_h_m2'] > day4 > day11 > p['cl_low_l_h_m2'])
        self.assertGreater(fc.clearance('B_prior_dose', 1.0, p, 240.0, 0.7), day11)
        with self.assertRaises(ValueError):
            fc.clearance('C_other', 1.0, p, 1.0, 1.3)

    def test_a_sample_at_a_dose_time_is_pre_dose(self):
        conc, _ = fc.simulate('A_time', 0.0, self.p, 1.3, [72.0, 72.0 + 1e-6])
        self.assertLess(conc[72.0] * 2, conc[72.0 + 1e-6])


class LockedResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = fc.run_check()

    def test_committed_report_reproduces_exactly(self):
        self.assertEqual(self.report, json.loads(fc.REPORT_PATH.read_text()))

    def test_numerical_checks_pass(self):
        checks = self.report['numerical_checks']
        self.assertTrue(checks['k0_check_passed'] and checks['step_halving_passed'] and checks['amount_balance_passed'])

    def test_neither_form_can_be_calibrated_so_neither_is_checked(self):
        self.assertIs(self.report['clinical_prediction_validated'], False)
        self.assertEqual(self.report['decision']['forms_carrying_rise_over'], [])
        for form in fc.FORMS:
            entry = self.report['forms'][form]
            cal = entry['calibration']
            self.assertFalse(cal['calibratable'])
            self.assertIsNone(cal['k'])
            self.assertLess(cal['reachable_ng_h_ml']['at_k_max'], cal['target_ng_h_ml'])
            self.assertNotIn('ogawa_rows', entry)
        # Form A reaches the target only in the limit where clearance is low from the start: no falling clearance left.
        self.assertGreater(self.report['forms']['A_time']['calibration']['reachable_ng_h_ml']['limit_k_to_infinity'], 241)
        self.assertLess(self.report['forms']['B_prior_dose']['calibration']['reachable_ng_h_ml']['limit_k_to_infinity'], 241)

    def test_post_hoc_section_is_labelled_and_outside_the_decision(self):
        post = self.report['post_hoc_not_in_plan']
        self.assertIn('not part of the decision', post['status'])
        a_top = next(r for r in post['can1004_at_range_top_and_limit'] if r['form'] == 'A_time' and r['k'] == 10.0)
        self.assertAlmostEqual(a_top['can1004_auc_last_day1_ng_h_ml'], 109.5, places=1)


if __name__ == '__main__':
    unittest.main()
