"""Digital human 1.1d: the time-course check plan is pinned and locked before the model is built."""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'intelligence_store' / 'data' / 'lenalidomide_body_map_time_course_plan_v1.json'
PLAN_SHA256 = 'a92c4d1c88186cc0a6509e2ee5ab6a93efe64d81ec42cc9c07792913570751cc'


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


if __name__ == '__main__':
    unittest.main()
