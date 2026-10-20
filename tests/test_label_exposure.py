"""Phase 3.1c: label-based exposure engine and the locked pomalidomide consistency check."""
import json
import math
from pathlib import Path
import tempfile
import unittest

from intelligence_store import label_exposure as le


class Model(unittest.TestCase):
    def test_ka_reproduces_tmax_and_rejects_unreachable_tmax(self):
        k = 0.1
        for tmax in (0.5, 2.5, 9.0):
            ka = le.ka_from_tmax(tmax, k)
            self.assertGreater(ka, k)
            self.assertAlmostEqual(math.log(ka / k) / (ka - k), tmax, places=9)
        with self.assertRaises(ValueError):
            le.ka_from_tmax(10.5, k)          # Tmax can never reach 1/k

    def test_steady_state_equals_summed_single_doses(self):
        cl, v, ka, dose, tau = 4.651, 50.33, 1.07, 4, 24
        for t in (0.0, 3.0, 20.0):
            summed = math.fsum(le.single_dose_ng_ml(t + n * tau, dose, cl, v, ka) for n in range(80))
            self.assertAlmostEqual(le.steady_state_ng_ml(t, dose, tau, cl, v, ka) / summed, 1.0, places=12)

    def test_steady_state_auc_is_dose_over_clearance(self):
        ss = le.steady_state_summary(4, 24, 4.651, 50.33, 1.07)
        self.assertAlmostEqual(ss['auc_tau_ng_h_ml_trapezoid'] / (4000 / 4.651), 1.0, places=6)
        self.assertLessEqual(abs(ss['tmax_h_grid'] - ss['tmax_h_closed_form']), le.GRID_H)


class Inputs(unittest.TestCase):
    def test_plan_and_label_are_pinned(self):
        for loader, path in ((le.load_plan, le.PLAN_PATH), (le.load_label, le.LABEL_PATHS['pomalidomide'][0])):
            loader()
            with tempfile.TemporaryDirectory() as tmp:
                changed = Path(tmp) / path.name
                changed.write_bytes(path.read_bytes() + b' ')
                with self.assertRaises(ValueError):
                    loader(path=changed)

    def test_parameter_sets_follow_the_plan_rules(self):
        sets = le.parameter_sets(le.load_label())
        a, b = sets['A_exposure_derived_mm'], sets['B_stated_pooled']
        self.assertAlmostEqual(a['cl_f_l_h'], 4000 / 860)
        self.assertAlmostEqual(a['v_f_l'], a['cl_f_l_h'] * 7.5 / math.log(2))
        self.assertAlmostEqual(b['cl_f_l_h'], math.sqrt(70))
        self.assertAlmostEqual(b['v_f_l'], math.sqrt(62 * 138))


class LockedResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = le.run_check()

    def test_committed_report_reproduces_exactly(self):
        self.assertEqual(self.report, json.loads(le.REPORT_PATH.read_text()))

    def test_numerical_checks_pass(self):
        n = self.report['numerical_checks']
        self.assertTrue(n['superposition_passed'] and n['auc_passed'] and n['tmax_passed'])

    def test_myeloma_set_is_selected_and_the_pooled_set_fails(self):
        self.assertIs(self.report['clinical_prediction_validated'], False)
        d = self.report['decision']
        self.assertEqual(d['selected_set'], 'A_exposure_derived_mm')
        self.assertTrue(d['eligible'] and d['selected_sensitivity_all_pass'])
        a = self.report['parameter_sets']['A_exposure_derived_mm']['primary']['checks']
        self.assertAlmostEqual(a['C3_steady_state_cmax']['ratio'], 0.954, places=3)   # the one informative check for A
        self.assertFalse(a['C5_volume_in_stated_range']['inside'])
        b = self.report['parameter_sets']['B_stated_pooled']['primary']
        self.assertFalse(b['passes_c1_to_c4'])
        self.assertEqual({c for c in le.PASS_FAIL if b['checks'][c]['result'] == 'fail'},
                         {'C1_clearance_vs_exposure', 'C3_steady_state_cmax', 'C4_steady_state_auc'})


if __name__ == '__main__':
    unittest.main()
