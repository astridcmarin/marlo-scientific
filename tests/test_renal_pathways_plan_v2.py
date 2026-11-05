"""Simulation 2.0d: the renal pathways v2 plan is pinned and locked before the model is built or run."""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'intelligence_store' / 'data' / 'lenalidomide_renal_pathways_plan_v2.json'
PLAN_SHA256 = 'fd97319efd3b44e84e6e3ef994179803b86d262c544e2feb6a71be66eb0c6ad8'


class LockedPlan(unittest.TestCase):
    def setUp(self):
        raw = PLAN.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), PLAN_SHA256, 'locked plan changed; a change needs a new version')
        self.plan = json.loads(raw)

    def test_locked_and_not_validated(self):
        self.assertEqual(self.plan['status'], 'locked_before_computation')
        self.assertFalse(self.plan['clinical_prediction_validated'])
        self.assertFalse(self.plan['ready_for_patient_simulation'])

    def test_pinned_inputs_exist_unchanged(self):
        for ref in self.plan['pinned_inputs'].values():
            self.assertEqual(hashlib.sha256((ROOT / ref['file']).read_bytes()).hexdigest(), ref['sha256'], ref['file'])

    def test_one_parameter_fitted_on_the_build_study_only(self):
        fitted = self.plan['model']['fitted']
        self.assertEqual(fitted['parameter'], 'k')
        self.assertIn('CC-5013-PK-001 impaired groups only', fitted['data'])
        self.assertIn('no check in this plan is blind', self.plan['what_is_known_before_computation'])

    def test_decision_needs_four_of_four(self):
        self.assertIn('four of four', self.plan['decision_rule']['adopt'])
        self.assertIn('never \'validated\'', self.plan['decision_rule']['wording'])
