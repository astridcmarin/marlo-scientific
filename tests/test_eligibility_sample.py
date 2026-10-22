"""Phase 4.1c: validation sample, annotation guide and locked validation plan."""
import hashlib
import json
from pathlib import Path
import unittest

from intelligence_store import eligibility_sample as es

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'intelligence_store' / 'data'
PINS = {DATA / 'eligibility_validation_plan_v1.json': '2061c0a0a9a4ee94fd9331a47d6ca5692d23ef3cffac3081ebfacf63eb4c0b8c',
        DATA / 'eligibility_validation_sample_v1.json': 'b49e505c3d9004de5047e3fc56920bc012df606d24517e8fbbae79db39f8b93d',
        ROOT / 'docs' / 'ELIGIBILITY_ANNOTATION_GUIDE.md': '3818133ea58d172bad0369fbe4b33f08018e169e7f86182eabe313b888f29a45'}


class Locked(unittest.TestCase):
    def test_files_are_pinned_and_cross_referenced(self):
        for path, sha in PINS.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), sha, path.name)
        plan = json.loads((DATA / 'eligibility_validation_plan_v1.json').read_text())
        self.assertEqual(plan['status'], 'locked_before_annotation_and_extraction')
        self.assertEqual(plan['inputs']['sample']['sha256'], PINS[DATA / 'eligibility_validation_sample_v1.json'])
        self.assertEqual(plan['inputs']['annotation_guide']['sha256'], PINS[ROOT / 'docs' / 'ELIGIBILITY_ANNOTATION_GUIDE.md'])
        self.assertEqual(len(plan['criterion_types']), 8)


class Sample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.drawn = es.draw()
        cls.stored = json.loads((DATA / 'eligibility_validation_sample_v1.json').read_text())

    def test_redrawing_reproduces_the_stored_sample(self):
        for key in ('validation_sample', 'annotation_order', 'development_set', 'allocation', 'group_sizes'):
            self.assertEqual(self.drawn[key], self.stored[key], key)

    def test_sizes_disjoint_and_proportional(self):
        d = self.drawn
        self.assertEqual(len(set(d['validation_sample'])), 120)
        self.assertEqual(sorted(d['annotation_order']), sorted(d['validation_sample']))
        self.assertEqual(len(set(d['development_set'])), 200)
        self.assertFalse(set(d['validation_sample']) & set(d['development_set']))
        for g, n in d['allocation'].items():
            self.assertLessEqual(abs(n - 120 * d['group_sizes'][g] / d['eligible_trials']), 1)

    def test_allocation_rule(self):
        self.assertEqual(es.allocation({'phase_1': 1, 'phase_1_2': 1, 'phase_2': 1, 'phase_2_3_or_3': 0, 'other': 0}, 2),
                         {'phase_1': 1, 'phase_1_2': 1, 'phase_2': 0, 'phase_2_3_or_3': 0, 'other': 0})
        self.assertEqual(es.phase_group(['PHASE2', 'PHASE3']), 'phase_2_3_or_3')
        self.assertEqual(es.phase_group([]), 'other')


if __name__ == '__main__':
    unittest.main()
