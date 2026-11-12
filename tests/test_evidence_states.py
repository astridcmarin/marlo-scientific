"""The evidence-state ladder (plan docs/EVIDENCE_CONNECTIONS_PLAN.md, update 3)."""
import unittest

from intelligence_store import evidence_states as es

DATA = 'intelligence_store/data/'


class States(unittest.TestCase):
    def setUp(self):
        self.states = es.states()

    def test_every_queued_extract_has_exactly_one_state(self):
        self.assertTrue(self.states)
        for f, s in self.states.items():
            self.assertIn(s['state'], es.STATES, f)
            self.assertEqual(s['label'], es.LABELS[s['state']])

    def test_reviewed_only_with_a_full_matching_review_record(self):
        for f, s in self.states.items():
            if s['state'] == 'reviewed_by_owner':
                self.assertEqual(s['counts']['matches'], sum(s['counts'].values()), f)
            self.assertNotEqual(s['state'], 'agreed_by_two_extractions', 'No double-extraction record exists yet')

    def test_known_states(self):
        self.assertEqual(self.states[DATA + 'hughes_parameter_extract_v1.json']['state'], 'reviewed_by_owner')
        self.assertEqual(self.states[DATA + 'hughes_parameter_precision_v2.json']['state'], 'extracted')
        self.assertEqual(self.states[DATA + 'fda_renal_impairment_guidance_2024_v1.json']['state'], 'extracted')

    def test_model_checks_are_reported_separately_from_the_value(self):
        s = self.states[DATA + 'hughes_parameter_extract_v1.json']
        self.assertIn('lenalidomide_hughes_2019', s['models_checked_against_outside_data'])
        self.assertTrue(set(s['models_checked_against_outside_data']).isdisjoint(s['models_not_checked']))


if __name__ == '__main__':
    unittest.main()
