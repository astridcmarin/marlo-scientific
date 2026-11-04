"""Digital human 1.1d: the time-course model, its numerical checks, and the locked consistency check report."""
import json
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_reproduction import assert_reproduces  # noqa: E402

from intelligence_store import body_map_time_course as tc  # noqa: E402
from intelligence_store.body_map import explorer_map  # noqa: E402
from intelligence_store.patient_state import digest  # noqa: E402


class Model(unittest.TestCase):
    def test_clearance_is_the_body_map_clearance(self):
        for crcl in (20, 40, 65, 110):
            view = explorer_map(crcl)
            self.assertAlmostEqual(tc.clearances(crcl)['total'], view['totals']['total_ml_min'] * 0.06)

    def test_curve_peaks_at_the_target_at_calibration_and_conserves_mass(self):
        course = tc.time_course(110.0, hours=120.0, step_h=0.5)
        self.assertAlmostEqual(course['tmax_h'], 1.0, places=3)
        for row in course['rows']:
            self.assertAlmostEqual(sum(row['pct_dose'].values()), 100.0, places=6)
        self.assertAlmostEqual(course['rows'][-1]['pct_dose']['urine'] / 100.0, course['fraction_excreted_unchanged'], places=3)

    def test_lower_kidney_function_means_a_longer_half_life(self):
        halves = [tc.time_course(c, hours=1)['half_life_h'] for c in (140, 110, 65, 40, 20)]
        self.assertEqual(halves, sorted(halves))


class LockedReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.committed = json.loads(tc.REPORT_PATH.read_text())
        cls.fresh = tc.run_check()

    def test_committed_report_reproduces(self):
        assert_reproduces(self, self.fresh, self.committed)
        body = {k: v for k, v in self.committed.items() if k != 'report_sha256'}
        self.assertEqual(digest(body), self.committed['report_sha256'])

    def test_numerical_checks_pass(self):
        checks = self.committed['numerical_checks']
        self.assertTrue(all(checks[k] for k in ('closed_form_vs_rk4_pass', 'mass_balance_pass', 'urine_total_equals_fe_pass',
                                                'calibration_tmax_pass')))

    def test_ci_rule(self):
        row = self.committed['primary']['moderate']['rows'][0]
        s = math.sqrt(math.log(1 + (row['observed_gcv_pct'] / 100) ** 2))
        self.assertLess(row['observed_ci90'][0], row['observed_gm'] * math.exp(-s / math.sqrt(row['n'])))

    def test_recorded_result(self):
        r = self.committed['result']['primary']
        self.assertEqual({g: r[g]['cmax_ng_ml'] for g in r}, {g: 'model_under_predicts' for g in ('mild', 'moderate', 'severe')})
        self.assertEqual(r['moderate']['terminal_half_life_h'], 'consistent')
        self.assertEqual(r['mild']['terminal_half_life_h'], 'model_over_predicts')
        self.assertEqual(self.committed['primary']['normal']['rows'][0]['classification'], 'model_under_predicts')
        self.assertFalse(self.committed['clinical_prediction_validated'])


class LockedReportV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.committed = json.loads(tc.REPORT_V2_PATH.read_text())
        cls.fresh = tc.run_check_v2()

    def test_committed_report_reproduces(self):
        assert_reproduces(self, self.fresh, self.committed)
        body = {k: v for k, v in self.committed.items() if k != 'report_sha256'}
        self.assertEqual(digest(body), self.committed['report_sha256'])

    def test_numerical_checks_pass_in_every_scenario(self):
        for name, s in self.committed['scenarios'].items():
            checks = s['numerical_checks']
            self.assertTrue(all(checks[k] for k in ('closed_form_vs_rk4_pass', 'mass_balance_pass', 'urine_total_equals_fe_pass')), name)

    def test_kim_volumes_on_the_total_scale(self):
        d = self.committed['scenarios']['primary']['parameters']
        self.assertAlmostEqual(d['vc_l'], 29.963, places=3)
        self.assertGreater(self.committed['scenarios']['sensitivity_bsa_1_9']['parameters']['vc_l'], d['vc_l'])

    def test_display_decision_keeps_v1(self):
        dd = self.committed['display_decision']
        self.assertEqual((dd['v2_cmax_consistent_groups'], dd['v2_half_life_consistent_impaired'],
                          dd['v1_half_life_consistent_impaired']), (2, 1, 2))
        self.assertEqual(dd['body_map_shows'], 'v1')

    def test_recorded_primary_result(self):
        r = self.committed['result']['primary']
        self.assertEqual(r['primary_cmax'], {'normal': 'consistent', 'mild': 'model_under_predicts',
                                             'moderate': 'consistent', 'severe': 'model_under_predicts'})
        self.assertEqual(r['primary_half_life']['moderate'], 'model_under_predicts')
        self.assertFalse(self.committed['clinical_prediction_validated'])


if __name__ == '__main__':
    unittest.main()
