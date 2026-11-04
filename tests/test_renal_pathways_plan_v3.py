"""Simulation 2.0e: the bioavailability re-check plan is pinned and locked before the model is run."""
import hashlib
import json
import unittest
from pathlib import Path

from intelligence_store import dataset_ledger as dl

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'intelligence_store' / 'data' / 'lenalidomide_renal_pathways_plan_v3.json'
PLAN_SHA256 = 'ccbd8fcbf2674e8e167fdc7acfbf5916fe6ebe15eab938ccc4bbc2c5c9f47bc9'
MASS_BALANCE_SHA256 = 'fac0021e7354b96deb0201ea00a17837fb58b6c2ed2786d15b0706cb3a34430a'


class LockedPlan(unittest.TestCase):
    def setUp(self):
        raw = PLAN.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), PLAN_SHA256, 'locked plan changed; a change needs a new version')
        self.plan = json.loads(raw)

    def test_locked_not_blind_and_not_validated(self):
        self.assertEqual(self.plan['status'], 'locked_before_computation')
        self.assertIn('Not blind', self.plan['what_is_known_before_computation'])
        self.assertFalse(self.plan['clinical_prediction_validated'])

    def test_inputs_pinned(self):
        for ref in self.plan['pinned_inputs'].values():
            self.assertEqual(hashlib.sha256((ROOT / ref['file']).read_bytes()).hexdigest(), ref['sha256'], ref['file'])
        self.assertEqual(self.plan['pinned_inputs']['mass_balance']['sha256'], MASS_BALANCE_SHA256)

    def test_datasets_pass_the_ledger_gate(self):
        self.assertIs(dl.validate_plan_datasets(self.plan), self.plan)
        self.assertTrue(all(d['role'] not in dl.BLIND_ROLES for d in self.plan['datasets']))

    def test_scenarios_and_decision_fixed(self):
        s = self.plan['scenarios']
        self.assertEqual(s['F_best_supported'], [1.0, 0.95, 0.90])
        self.assertEqual(s['F_lower_bound'], 0.85)
        self.assertEqual(set(self.plan['decision_rule']), {'D1_band_status', 'D2_recorded_finding', 'D3_non_renal_arrow',
                                                           'D4_myeloma_note', 'not_changed'})

    def test_mass_balance_quotes_carry_their_numbers(self):
        mb = json.loads((ROOT / self.plan['pinned_inputs']['mass_balance']['file']).read_text())['values']
        self.assertIn('90.3', mb['urine_radioactivity_pct_dose']['quote'])
        self.assertIn('87.0–94.6', mb['urine_radioactivity_pct_dose']['quote'])
        self.assertIn('84%', mb['unchanged_in_urine_pct_dose_cited']['quote'])


if __name__ == '__main__':
    unittest.main()
