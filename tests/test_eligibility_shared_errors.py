"""The shared-error review list (13 November 2026)."""
import unittest

from intelligence_store import eligibility_shared_errors as se
from intelligence_store import eligibility_validation_v2 as v2


class SharedErrors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.view = se.build()

    def test_lists_exactly_the_pairs_both_extractors_got_wrong(self):
        import json
        from pathlib import Path
        report = json.loads((Path(__file__).resolve().parents[1] / 'docs/verification/eligibility_validation_llm_c1.json').read_text())
        neither = {t: c['neither'] for t, c in report['paired_with_v1_1'].items()}
        self.assertEqual(self.view['counts'], neither)
        self.assertEqual(self.view['total'], sum(neither.values()))
        for i in self.view['items']:
            self.assertIn(i['v1_1']['outcome'], se.OUTCOMES)
            self.assertIn(i['llm_run_1']['outcome'], se.OUTCOMES)
            self.assertIn(i['type'], v2.TYPES)

    def test_record_validation(self):
        first = self.view['items'][0]['id']
        ok = {'view_sha256': self.view['view_sha256'], 'decisions': {first: {'decision': 'annotation_stands', 'note': ''}}}
        self.assertEqual(se.validate_record(ok, self.view), [])
        bad = {'view_sha256': 'x', 'decisions': {first: {'decision': 'annotation_needs_correcting', 'note': ' '}, 'NCT0:x': {'decision': 'trial_unclear'}}}
        self.assertEqual(len(se.validate_record(bad, self.view)), 3)


if __name__ == '__main__':
    unittest.main()
