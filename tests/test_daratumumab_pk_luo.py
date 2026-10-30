"""Simulation 3.2b: the Luo 2021 daratumumab model and its locked check (fast parts; the full run is the committed
report, which is checked here but not regenerated: it takes about 20 minutes)."""
import json
import math
import random
import tempfile
import unittest
from pathlib import Path

from intelligence_store import daratumumab_pk_luo as model
from intelligence_store import daratumumab_pk_luo_check as c


class Model(unittest.TestCase):
    def setUp(self):
        self.extract = model.load_extract()
        self.p = model.typical_parameters(self.extract)

    def test_extract_is_pinned_and_refuses_changes(self):
        raw = json.loads(model.EXTRACT_PATH.read_text())
        raw['parameters']['fixed_effects']['vmax_mg_h']['value'] = 2.0
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'x.json'
            path.write_text(json.dumps(raw))
            with self.assertRaises(ValueError):
                model.load_extract(path)

    def test_covariate_equations(self):
        base = model.typical_parameters(self.extract)
        self.assertAlmostEqual(base['cl'], 0.00496)
        self.assertAlmostEqual(base['v1'], 5.25)
        self.assertAlmostEqual(model.typical_parameters(self.extract, igg=True)['cl'] / base['cl'], 2.26)
        self.assertAlmostEqual(model.typical_parameters(self.extract, male=True)['v1'] / base['v1'], 0.895)
        self.assertAlmostEqual(model.typical_parameters(self.extract, male=False, sex_factor_on='female')['v1'] / base['v1'], 0.895)
        self.assertAlmostEqual(model.typical_parameters(self.extract, albumin_g_l=37 * 2)['cl'] / base['cl'], 2 ** -1.85)
        self.assertAlmostEqual(model.typical_parameters(self.extract, weight_kg=78.6 * 2)['v1'] / base['v1'], 2 ** 0.91)

    def test_mass_balance_and_saturation_ceiling(self):
        dose = 16 * 78.6
        r = model.simulate(self.p, [(0.0, dose, 7.0)], [7.0, 500.0])
        total = r['amount_central_mg'] + r['amount_peripheral_mg'] + r['removed_linear_mg'] + r['removed_saturable_mg']
        self.assertAlmostEqual(total / dose, 1.0, places=10)
        self.assertLessEqual(r['removed_saturable_mg'], self.p['vmax'] * 500.0)          # never more than Vmax per hour
        self.assertGreater(r['at'][7.0]['conc'], r['at'][500.0]['conc'])

    def test_dose_nonlinearity_direction(self):
        # Saturable elimination: doubling the dose more than doubles the AUC.
        a = model.simulate(self.p, [(0.0, 8 * 78.6, 7.0)], [7.0], until_fraction_of_max=0.001)['auc_infinity']
        b = model.simulate(self.p, [(0.0, 16 * 78.6, 7.0)], [7.0], until_fraction_of_max=0.001)['auc_infinity']
        self.assertGreater(b / a, 2.0)

    def test_linear_limit(self):
        q = dict(self.p, vmax=0.0)
        r = model.simulate(q, [(0.0, 600.0, 7.0)], [7.0], until_fraction_of_max=0.001)
        self.assertAlmostEqual(r['auc_infinity'] / (600.0 / q['cl']), 1.0, places=3)


class Check(unittest.TestCase):
    def test_plan_is_pinned_and_matches_the_code(self):
        plan = c.load_plan()
        self.assertEqual(plan['plan_version'], 'daratumumab-pk-luo-check-plan-v1.0')
        self.assertEqual(plan['comparison']['scenarios'], list(c.SCENARIOS))
        self.assertEqual(plan['simulation']['virtual_trials'], 1000)

    def test_observed_inputs(self):
        _, observed = c.load_inputs(c.load_plan())
        got = {e[0]: (c.observed_value(observed, e[5])['mean'], c.observed_value(observed, e[5])['n']) for e in c.ENDPOINTS}
        self.assertEqual(got['sirius_8.cmax'], (138.7, 18))
        self.assertEqual(got['sirius_8.auc_inf'], (21070.0, 15))
        self.assertEqual(got['gen501_16.cmax'], (263.4, 40))
        self.assertEqual(got['gen501_16.auc_0_7d'], (25123.3, 20))
        for _, group, _, _, n, *_ in c.ENDPOINTS:
            self.assertLessEqual(n, c.GROUPS[group][1])

    def test_patient_draws_use_the_same_random_numbers_in_every_scenario(self):
        extract = model.load_extract()
        om = c._omegas(extract, 'exact')
        a = [c.draw_patient(random.Random(5), extract, {}, om)[0] for _ in range(1)]
        b = [c.draw_patient(random.Random(5), extract, {'p_igg': 0.4}, om)[0] for _ in range(1)]
        self.assertAlmostEqual(math.log(a[0]['v1']), math.log(b[0]['v1']))          # V1 does not depend on IgG

    def test_committed_report(self):
        r = json.loads(c.REPORT_PATH.read_text())
        self.assertEqual(r['plan_sha256'], c.PLAN_SHA256)
        self.assertEqual(r['trials'], 1000)
        self.assertTrue(all(r['numerical_checks'][k] for k in ('mass_balance_pass', 'step_halving_pass', 'linear_auc_pass')))
        self.assertEqual(sorted(r['scenarios']), sorted(c.SCENARIOS))
        self.assertFalse(r['clinical_prediction_validated'])
        body = dict(r)
        claimed = body.pop('report_sha256')
        from intelligence_store.patient_state import digest
        self.assertEqual(digest(body), claimed)


if __name__ == '__main__':
    unittest.main()
