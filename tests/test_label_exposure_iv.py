"""Phase 3.1f: intravenous label-based engine and the locked melphalan (EVOMELA) consistency check."""
import json
import math
from pathlib import Path
import tempfile
import unittest

from intelligence_store import label_exposure_iv as iv
from intelligence_store.capability_levels import drug_level


class Model(unittest.TestCase):
    def test_infusion_rises_then_decays_and_approaches_a_bolus(self):
        cl, v = 13.3, 24.0
        self.assertEqual(iv.infusion_ug_ml(0.0, 100, 0.5, cl, v), 0.0)
        peak = iv.infusion_ug_ml(0.5, 100, 0.5, cl, v)
        self.assertAlmostEqual(peak, 100 / 0.5 / cl * (1 - math.exp(-cl / v * 0.5)))
        self.assertLess(iv.infusion_ug_ml(2.0, 100, 0.5, cl, v), peak)
        self.assertAlmostEqual(iv.infusion_ug_ml(1.0, 100, 1e-7, cl, v) / iv.bolus_ug_ml(1.0, 100, cl, v), 1.0, places=6)

    def test_auc_is_dose_over_clearance(self):
        s = iv.summary(100, 0.5, 13.3, 24.0)
        self.assertAlmostEqual(s['auc_inf_ug_min_ml_numerical'] / s['auc_inf_ug_min_ml_exact'], 1.0, places=8)


class Inputs(unittest.TestCase):
    def test_plan_and_label_are_pinned(self):
        for loader, path in ((iv.load_plan, iv.PLAN_PATH), (iv.load_label, iv.LABEL_PATH)):
            with tempfile.TemporaryDirectory() as tmp:
                changed = Path(tmp) / path.name
                changed.write_bytes(path.read_bytes() + b' ')
                with self.assertRaises(ValueError):
                    loader(changed)

    def test_parameter_sets_follow_the_plan_rules(self):
        sets = iv.parameter_sets(iv.load_label())
        a, b = sets['A_exposure_derived_mm'], sets['B_stated_ranges']
        self.assertAlmostEqual(a['cl_l_h_m2'] * 1000 / 60, 100000 / 451)
        self.assertAlmostEqual(a['v_l_m2'], a['cl_l_h_m2'] * 1.25 / math.log(2))
        self.assertAlmostEqual(b['cl_l_h_m2'] * 1000 / 60, math.sqrt(250 * 325))
        self.assertAlmostEqual(b['v_l_m2'], math.sqrt(35.5 * 185.7))


class LockedResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = iv.run_check()

    def test_committed_report_reproduces_exactly(self):
        self.assertEqual(self.report, json.loads(iv.REPORT_PATH.read_text()))

    def test_numerical_checks_pass(self):
        n = self.report['numerical_checks']
        self.assertTrue(n['auc_passed'] and n['bolus_limit_passed'] and n['continuity_passed'])

    def test_melphalan_is_not_eligible_and_why(self):
        self.assertIs(self.report['clinical_prediction_validated'], False)
        self.assertEqual(self.report['decision'], dict(self.report['decision'], selected_set=None, eligible=False))
        a = self.report['parameter_sets']['A_exposure_derived_mm']
        self.assertEqual(a['primary']['checks']['C3_cmax_end_of_infusion']['result'], 'fail')
        self.assertAlmostEqual(a['primary']['checks']['C3_cmax_end_of_infusion']['ratio'], 0.628, places=3)
        self.assertTrue(all(s['cmax_result'] == 'fail' for s in a['infusion_sensitivity']))
        b = self.report['parameter_sets']['B_stated_ranges']['primary']['checks']
        self.assertEqual(b['C2_half_life']['result'], 'fail')          # the label's ranges imply ~197 min, not 75
        self.assertGreater(b['C2_half_life']['model'], 190)

    def test_level_is_unchanged(self):
        self.assertEqual(drug_level('Melphalan', True)['id'], 'knowledge_only')


if __name__ == '__main__':
    unittest.main()
