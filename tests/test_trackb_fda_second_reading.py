"""The second reading of the 21 out-of-scope FDA entries (13 November 2026): pinned, complete and matched to the queue."""
import hashlib
import json
import unittest
from pathlib import Path

from intelligence_store import double_extraction as dx
from intelligence_store import extraction_review as er

ROOT = Path(__file__).resolve().parents[1]


class FdaSecondReading(unittest.TestCase):
    def test_pinned_and_complete(self):
        d = er.fda_second_reading()
        plan, queue = dx.load_plan(), dx.load_queue()
        ids = [it['id'] for g in queue['groups'] if g['id'] in plan['out_of_scope']['groups'] for it in g['items']]
        self.assertEqual(len(ids), plan['out_of_scope']['entries'])
        self.assertEqual(sorted(e['id'] for e in d['entries']), sorted(ids))
        self.assertTrue(all(e['blind_id'] == dx.opaque_id(e['id']) for e in d['entries']))
        self.assertEqual(d['counts'], {'agree': 10, 'disagree': 2, 'not_comparable': 9})
        raw = (ROOT / d['second_reading']['file']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), d['second_reading']['sha256'])
        self.assertEqual(len(raw.decode().strip().splitlines()), 21)
        self.assertFalse(d['clinical_prediction_validated'])

    def test_comparison_rule_reproduces(self):
        """Every comparable entry's result follows from the plan's number rule (quotes are checked against the PDFs off-repository)."""
        d = er.fda_second_reading()
        queue = {it['id']: it['value'] for g in dx.load_queue()['groups'] for it in g['items']}
        for e in d['entries']:
            if not dx.numbers(queue[e['id']]):
                self.assertEqual(e['result'], 'not_comparable')
                continue
            t = dx._template(queue[e['id']]) if isinstance(queue[e['id']], dict) else {'quote': None}
            restricted = {k: e['second_reader_value'].get(k) for k in t} if isinstance(t, dict) else e['second_reader_value']
            c = dx.compare(queue[e['id']], restricted)
            self.assertEqual(c['result'] == 'agree' and not e['missing_quotes'], e['result'] == 'agree', e['id'])


if __name__ == '__main__':
    unittest.main()
