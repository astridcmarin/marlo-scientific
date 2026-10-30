"""Simulation 3.2a: the Gupta 2017 ixazomib model and its locked external consistency check."""
import json
import math
import tempfile
import unittest
from pathlib import Path

from intelligence_store import ixazomib_pk_gupta as model
from intelligence_store import ixazomib_pk_gupta_check as c

DATA = Path(model.__file__).parent / 'data'


class Model(unittest.TestCase):
    def setUp(self):
        self.extract = model.load_extract()
        self.p = model.typical_parameters(self.extract)

    def test_extract_is_pinned_and_refuses_changes(self):
        raw = json.loads(model.EXTRACT_PATH.read_text())
        raw['parameters']['fixed_effects']['cl_l_h']['value'] = 2.0
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'x.json'
            path.write_text(json.dumps(raw))
            with self.assertRaises(ValueError):
                model.load_extract(path)

    def test_log_estimates_back_transform_to_stated_values(self):
        for name, entry in self.extract['parameters']['fixed_effects'].items():
            if 'log_estimate' not in entry:
                continue
            self.assertLess(abs(math.exp(entry['log_estimate']) / entry['value'] - 1), 0.02, name)

    def test_bsa_form_reproduces_stated_effects(self):
        v4 = self.extract['parameters']['fixed_effects']['v4_l']['value']
        self.assertAlmostEqual(model.typical_parameters(self.extract, 1.5)['v4'] / v4 - 1, -0.37, delta=0.005)
        self.assertAlmostEqual(model.typical_parameters(self.extract, 2.25)['v4'] / v4 - 1, 0.46, delta=0.005)

    def test_rates_are_roots_and_half_life_matches_article(self):
        rates = model.disposition_rates(self.p)
        k10, k12, k21 = self.p['cl'] / self.p['v2'], self.p['q3'] / self.p['v2'], self.p['q3'] / self.p['v3']
        k13, k31 = self.p['q4'] / self.p['v2'], self.p['q4'] / self.p['v4']
        a2 = k10 + k12 + k13 + k21 + k31
        a1 = k10 * k21 + k10 * k31 + k12 * k31 + k13 * k21 + k21 * k31
        a0 = k10 * k21 * k31
        for lam in rates:
            self.assertAlmostEqual(lam ** 3 - a2 * lam ** 2 + a1 * lam - a0, 0.0, places=12)
        self.assertAlmostEqual(math.prod(rates), a0, places=14)
        self.assertAlmostEqual(math.log(2) / rates[-1] / 24, 9.5, delta=0.2)      # article: 9.5 days

    def test_impulse_response_starts_at_one_over_v2(self):
        self.assertAlmostEqual(sum(model.impulse_coefficients(self.p)), 1 / self.p['v2'], places=12)

    def test_closed_form_matches_integration(self):
        times = [0.1, 0.5, 2, 30, 300]
        closed = model.concentration(times, 4.0, self.p)
        rk = model.integrate(times, 4.0, self.p, step_h=0.002)
        self.assertEqual(closed[0], 0.0)                       # before the 13 min lag
        for a, b in zip(closed[1:], rk[1:]):
            self.assertAlmostEqual(a / b['conc'], 1.0, places=8)

    def test_linear_in_dose(self):
        a = model.concentration([1, 100], 1.5, self.p)
        b = model.concentration([1, 100], 3.0, self.p)
        for x, y in zip(a, b):
            self.assertAlmostEqual(y / x, 2.0, places=12)


class Check(unittest.TestCase):
    def test_plan_v1_0_unchanged_and_v1_1_amends_it(self):
        v10 = json.loads((DATA / 'ixazomib_pk_gupta_check_plan_v1.json').read_text())
        v11 = c.load_plan()
        self.assertEqual(v11['plan_version'], 'ixazomib-pk-gupta-check-plan-v1.1')
        self.assertEqual({k: v for k, v in v11.items() if k not in ('plan_version', 'amendments')},
                         {k: v for k, v in v10.items() if k != 'plan_version'})
        self.assertIn('9b8ef3d87dc78b5242f1008c41f4fe0fab39c97aa098786304e5d8de703bae51', v11['amendments'][0]['supersedes'])
        self.assertEqual(v11['comparison']['scenarios'], list(c.SCENARIOS))

    def test_observed_inputs(self):
        _, observed = c.load_inputs(c.load_plan())
        obs = c._observed(observed)
        self.assertEqual(obs[('renal', 'normal')]['cmax'], 25.8)          # page image; text layer reads 258
        self.assertEqual(obs[('hepatic', 'severe')]['dose_mg'], 1.5)
        self.assertEqual(c.sampling_times(observed, 'renal', 'esrd')[8:10], [29, 30])
        hep = observed['studies']['hepatic']['table2']['groups']
        for g in hep.values():                                             # dose normalisation is internally consistent
            self.assertLess(abs(g['auc_last_ng_h_ml']['gm'] / g['dose_mg'] / g['dose_normalised_auc_last']['gm'] - 1), 0.01)

    def test_nca(self):
        t = [1, 2, 3, 4]
        r = c.nca(t, [4.0, 2.0, 1.0, 0.4])
        self.assertEqual(r['t_last'], 3)                                   # 0.4 is below the LLOQ
        self.assertAlmostEqual(r['auc_last'], 2 + 3 + 1.5)
        r = c.nca(t, [4.0, 2.0, 1.0, 0.4], 'linear_up_log_down')
        self.assertAlmostEqual(r['auc_last'], 2 + 2 / math.log(2) + 1 / math.log(2))
        self.assertFalse(c.pk_evaluable([0.6, 0.55, 0.4]))
        self.assertTrue(c.pk_evaluable([0.6, 0.55, 0.5]))

    def test_committed_report_regenerates_exactly(self):
        committed = json.loads(c.REPORT_PATH.read_text())
        fresh = json.loads(json.dumps(c.run_check()))
        self.assertEqual(fresh, committed)
        self.assertEqual(committed['plan_sha256'], c.PLAN_SHA256)
        self.assertTrue(all(committed['numerical_checks'][k] for k in ('closed_form_vs_runge_kutta_pass', 'auc_pass', 'mass_balance_pass')))
        self.assertFalse(committed['decision']['registration_may_be_proposed'])
        self.assertFalse(committed['clinical_prediction_validated'])


if __name__ == '__main__':
    unittest.main()
