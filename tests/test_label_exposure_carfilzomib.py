"""Carfilzomib label-consistency executable, dry-run on a synthetic extract (no KYPROLIS value is used here)."""
import copy
import json
import math
import unittest

from intelligence_store import label_exposure_carfilzomib as lc
from intelligence_store.label_exposure_iv import infusion_ug_ml

PLAN = json.loads(lc.PLAN_PATH.read_text())
R70, R56, R27 = lc.PRIMARY, lc.SECONDARY, lc.SHORT


def synthetic(cl=100.0, v=10.0, bsa=1.8):
    """A made-up label whose Table 21 is generated from a one-compartment drug with the given CL and V."""
    def cmax(dose, minutes):
        return 1000.0 * infusion_ug_ml(minutes / 60, dose * bsa, minutes / 60, cl, v)

    def avg(doses):
        return sum(d * bsa * 1000.0 / cl for d in doses) / 28
    return {'pk': {
        'auc_c1_avg_ng_h_ml': {'by_regimen': {R70: [avg([20, 70, 70]), 30], R56: [avg([20, 20] + [56] * 4), 30], R27: [1.0, 30]}},
        'auc_ss_ng_h_ml': {'by_regimen': {R70: [avg([70] * 3), 30], R56: [avg([56] * 6), 30], R27: [1.0, 30]}},
        'cmax_c1_ng_ml': {'by_regimen': {R70: [cmax(70, 30), 30], R56: [cmax(56, 30), 30], R27: [cmax(27, 6), 30]}},
        'cl_l_h': {'range': [cl * 0.8, cl * 1.25]}, 'vss_l': {'value': v}, 'half_life_h': {'upper_bound': 1}},
        'special_populations': {k: {'quote': 'synthetic'} for k in
                                ('hepatic_mild_moderate_auc_fold', 'esrd_hemodialysis_auc_fold', 'covariates_no_effect')}}


class DryRun(unittest.TestCase):
    def test_a_label_generated_by_the_model_selects_set_a_and_every_check_passes(self):
        rep = lc.run_check(PLAN, synthetic())
        self.assertEqual(rep['selected_set'], 'A_exposure_derived')
        a = rep['sets_by_bsa']['1.8']['A_exposure_derived']
        self.assertAlmostEqual(a['cl_l_h'], 100.0, places=9)
        for c in lc.PASS_FAIL:
            self.assertEqual(a['checks'][c]['result'], 'pass', c)
        for c in ('C3_cmax_primary', 'C4_auc_ss_primary', 'C5_auc_c1_primary', 'C6_cmax_secondary', 'C7_auc_ss_secondary'):
            self.assertAlmostEqual(a['checks'][c]['ratio'], 1.0, places=9)
        self.assertAlmostEqual(rep['D3_implied_clearance_by_regimen']['ratio_secondary_to_primary'], 1.0, places=9)
        self.assertEqual(set(rep['sets_by_bsa']), {'1.8', '1.6', '2.0'})
        self.assertTrue(rep['numerical_checks']['auc_passed'] and rep['numerical_checks']['continuity_passed'])

    def test_a_peak_the_model_cannot_reach_makes_the_drug_not_eligible(self):
        label = synthetic()
        for r in (R70, R56):
            label['pk']['cmax_c1_ng_ml']['by_regimen'][r][0] *= 3
        rep = lc.run_check(PLAN, label)
        self.assertIsNone(rep['selected_set'])
        self.assertEqual(rep['outcome'], 'not_eligible')
        self.assertIsNone(rep['scenarios'])

    def test_set_b_is_used_only_when_a_fails(self):
        label = synthetic()
        label['pk']['cl_l_h']['range'] = [150.0, 400.0]       # A (CL 100) falls outside; B's midpoint (245) is inside
        rep = lc.run_check(PLAN, label)
        self.assertEqual(rep['sets_by_bsa']['1.8']['A_exposure_derived']['checks']['C1_clearance_in_stated_range']['result'], 'fail')
        self.assertIn(rep['selected_set'], (None, 'B_stated_clearance'))

    def test_average_daily_auc_reading(self):
        # 210 mg/m2 x 1.8 m2 per cycle at CL 100 L/h: 3.78 mg/100 L/h = 3780 ug.h/L over 28 days -> 135 ng.h/mL per day.
        self.assertAlmostEqual(lc.avg_daily_auc_ng_h_ml([70, 70, 70], 1.8, 100.0), 135.0, places=9)
        self.assertAlmostEqual(lc.implied_cl_l_h(R70, 135.0, 1.8), 100.0, places=9)

    def test_half_life_and_accumulation(self):
        rep = lc.run_check(PLAN, synthetic(cl=100.0, v=10.0))
        a = rep['sets_by_bsa']['1.8']['A_exposure_derived']['checks']
        self.assertAlmostEqual(a['C2_half_life']['model'], math.log(2) * 10 / 100, places=12)
        self.assertLess(a['C8_no_accumulation']['model'], 1e-9)

    def test_the_pinned_plan_is_the_one_the_dry_run_used(self):
        self.assertEqual(lc.load_plan(), PLAN)


class Plan(unittest.TestCase):
    def test_plan_names_its_rules(self):
        self.assertEqual(PLAN['status'], 'locked_before_computation')
        self.assertEqual(PLAN['inputs']['body_surface_area_m2']['value'], 1.8)
        self.assertEqual(PLAN['parameter_sets']['order_of_preference'], ['A_exposure_derived', 'B_stated_clearance'])
        self.assertEqual(set(lc.PASS_FAIL), {k for k, c in PLAN['checks'].items() if isinstance(c, dict) and c.get('pass_or_fail')})
        self.assertIn('Badros', PLAN['prespecification_note'])
        self.assertFalse(PLAN['clinical_prediction_validated'])


if __name__ == '__main__':
    unittest.main()
