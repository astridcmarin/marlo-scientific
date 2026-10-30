"""Simulation 3.0k: the Iwasaki 2020 check (fast parts; the full run is the committed report)."""
import json
import random
import unittest

from intelligence_store import bortezomib_pbpk_iwasaki as model
from intelligence_store import bortezomib_pbpk_iwasaki_check as c


class Check(unittest.TestCase):
    def setUp(self):
        self.p = model.parameters()

    def test_plan_is_pinned(self):
        self.assertEqual(c.load_plan()['plan_version'], 'bortezomib-pbpk-iwasaki-check-plan-v1.0')

    def test_fast_rhs_equals_the_transcribed_equations(self):
        rhs = c._rhs_factory(self.p)
        rng = random.Random(7)
        for _ in range(30):
            st = {s: rng.uniform(0, 400) for s in model.STATE}
            ref = model.derivatives(st, self.p)
            got = rhs(*[st[s] for s in model.STATE])
            for i, s in enumerate(model.STATE):
                self.assertAlmostEqual(got[i], ref[s], delta=1e-9 * max(1.0, abs(ref[s])))
            self.assertAlmostEqual(got[6], model.metabolic_rate(st, self.p), places=12)

    def test_dose_per_kg(self):
        self.assertAlmostEqual(c.bsa_du_bois(58, 160), 1.5989, places=3)
        self.assertAlmostEqual(c.dose_ug_per_kg(1.3, 'ogawa'), 35.84, places=1)
        self.assertAlmostEqual(c.dose_ug_per_kg(1.3, 'can1004'), 32.30, places=1)

    def test_short_run_conserves_mass_and_occupancy_is_bounded(self):
        sim = c.simulate(self.p, 35.84, {1.0, 24.0}, dose_times_h=(0.0,))
        self.assertLess(sim['mass_balance_error'], 1e-9)
        self.assertGreater(sim['conc'][1.0], sim['conc'][24.0])
        sim = c.simulate(self.p, 35.84, {24.0}, dose_times_h=(0.0, 12.0))
        self.assertTrue(0 < sim['occupancy_before_dose'][12.0] < 1)

    def test_committed_report(self):
        r = json.loads(c.REPORT_PATH.read_text())
        self.assertEqual(r['plan_sha256'], c.PLAN_SHA256)
        self.assertFalse(r['decision']['resolves_3_0f_and_3_0h_findings'])
        self.assertTrue(r['decision']['robust'])
        self.assertTrue(all(r['numerical_checks'][k] for k in ('mass_balance_passed', 'step_halving_passed')))
        self.assertTrue(r['numerical_checks']['closed_form_without_binding']['passed'])
        self.assertFalse(r['clinical_prediction_validated'])


if __name__ == '__main__':
    unittest.main()
