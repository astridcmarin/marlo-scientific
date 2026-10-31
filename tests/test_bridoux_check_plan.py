"""Bridoux 2016 check (planned): the plan is pinned before any observed value is recorded."""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / 'intelligence_store' / 'data' / 'lenalidomide_bridoux_check_plan_v1.json'
PLAN_SHA256 = '7cf4070eb2d979404e8bba5650817b3b93a28bc41438654c7aaa66cafa10e329'


class BridouxPlan(unittest.TestCase):
    def setUp(self):
        raw = PLAN.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), PLAN_SHA256, 'locked plan changed; a change needs a new version')
        self.plan = json.loads(raw)

    def test_locked_before_observed_values(self):
        self.assertEqual(self.plan['status'], 'locked_before_observed_values')
        self.assertFalse(self.plan['clinical_prediction_validated'])
        self.assertIn('stage_1_design', self.plan['filling_procedure'])
        self.assertIn('stage_2_values', self.plan['filling_procedure'])

    def test_pinned_inputs_match(self):
        for ref in self.plan['pinned_inputs'].values():
            self.assertEqual(hashlib.sha256((ROOT / ref['file']).read_bytes()).hexdigest(), ref['sha256'], ref['file'])

    def test_same_rule_as_the_recheck(self):
        recheck = json.loads((ROOT / self.plan['pinned_inputs']['recheck_plan']['file']).read_text())
        self.assertEqual(self.plan['classification_rule'], recheck['classification_rule'])
        self.assertEqual(self.plan['virtual_trial']['trials'], recheck['virtual_trial']['trials'])

    def test_no_observed_exposure_values_in_the_plan(self):
        def keys(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    yield k
                    yield from keys(v)
            elif isinstance(node, list):
                for v in node:
                    yield from keys(v)
        found = set(keys(self.plan))
        for key in ('observed', 'observed_mean', 'auc_mean', 'cl_f_mean', 'groups'):
            self.assertNotIn(key, found)


if __name__ == '__main__':
    unittest.main()
