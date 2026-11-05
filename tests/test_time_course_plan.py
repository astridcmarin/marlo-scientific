"""Digital human 1.1d: the time-course check plan is pinned and locked before the model is built."""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'intelligence_store' / 'data' / 'lenalidomide_body_map_time_course_plan_v1.json'
PLAN_SHA256 = 'a92c4d1c88186cc0a6509e2ee5ab6a93efe64d81ec42cc9c07792913570751cc'
PLAN_V2 = ROOT / 'intelligence_store' / 'data' / 'lenalidomide_body_map_time_course_plan_v2.json'
PLAN_V2_SHA256 = '4c7b429e5d01da3eb31e0f86f2647af5d6adea116f6b7cd7fb78181b93ad6a1e'


class LockedPlan(unittest.TestCase):
    def test_pinned_and_locked(self):
        raw = PLAN.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), PLAN_SHA256, 'locked plan changed; a change needs a new version')
        plan = json.loads(raw)
        self.assertEqual(plan['status'], 'locked_before_computation')
        self.assertFalse(plan['clinical_prediction_validated'])
        self.assertIn('not an independent or blind test', plan['prespecification_note'])

    def test_pinned_inputs_exist_unchanged(self):
        plan = json.loads(PLAN.read_text())
        for ref in plan['pinned_inputs'].values():
            if isinstance(ref, dict):
                self.assertEqual(hashlib.sha256((ROOT / ref['file']).read_bytes()).hexdigest(), ref['sha256'], ref['file'])


class LockedPlanV2(unittest.TestCase):
    def test_pinned_locked_and_supersedes_v1(self):
        raw = PLAN_V2.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), PLAN_V2_SHA256, 'locked plan changed; a change needs a new version')
        plan = json.loads(raw)
        self.assertEqual(plan['status'], 'locked_before_computation')
        self.assertEqual(plan['supersedes']['sha256'], PLAN_SHA256)
        for ref in plan['pinned_inputs'].values():
            if isinstance(ref, dict):
                self.assertEqual(hashlib.sha256((ROOT / ref['file']).read_bytes()).hexdigest(), ref['sha256'], ref['file'])

    def test_distribution_is_kim_on_the_total_scale_and_nothing_is_fitted(self):
        plan = json.loads(PLAN_V2.read_text())
        kim = json.loads((ROOT / 'intelligence_store/data/kim_2026_model_extract_v1.json').read_text())['parameters']
        d = plan['model']['distribution_and_absorption']
        fu = kim['fraction_unbound']['value']
        self.assertAlmostEqual(d['central_volume_l']['total'], kim['unbound_central_volume_l']['value'] * fu, places=4)
        self.assertAlmostEqual(d['peripheral_volume_l']['total'], kim['unbound_peripheral_volume_l']['value'] * fu, places=4)
        self.assertEqual(d['absorption_rate_per_h'], kim['absorption_rate_h']['value'])
        self.assertIn('fits nothing', plan['prespecification_note'])


if __name__ == '__main__':
    unittest.main()
