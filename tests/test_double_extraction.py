"""Track B: double extraction for review round 3 (plan v1), checked without any second extraction."""
import json
import unittest

from intelligence_store import double_extraction as de
from intelligence_store import extraction_review as er


class Plan(unittest.TestCase):
    def setUp(self):
        self.plan = de.load_plan()
        self.queue = de.load_queue()

    def test_plan_pins_the_current_round_3_queue(self):
        self.assertEqual(self.plan['queue']['sha256'], er.ROUND_3_QUEUE_SHA256)
        self.assertEqual(de.QUEUE_SHA256, er.ROUND_3_QUEUE_SHA256)
        groups = {g['id']: len(g['items']) for g in self.queue['groups']}
        self.assertEqual(sum(groups[g] for g in self.plan['in_scope']['groups']), self.plan['in_scope']['entries'])
        self.assertEqual(sum(groups[g] for g in self.plan['out_of_scope']['groups']), self.plan['out_of_scope']['entries'])
        self.assertEqual(self.plan['in_scope']['entries'] + self.plan['out_of_scope']['entries'], self.plan['queue']['entries'])
        self.assertFalse(self.plan['clinical_prediction_validated'])

    def test_blinded_entries_carry_no_values(self):
        items = de.blind_items(self.queue, self.plan['in_scope']['groups'])
        self.assertEqual(len(items), 100)
        self.assertEqual(len({i['blind_id'] for i in items}), 100)
        originals = [it for g in self.queue['groups'] if g['id'] in self.plan['in_scope']['groups'] for it in g['items']]
        for blind, it in zip(items, originals):
            self.assertEqual(de.numbers(blind['fields_to_fill']), [], it['id'])
            self.assertNotIn(it['id'], json.dumps(blind))
            quotes = [v for k, v in it['value'].items() if k.endswith('quote')] if isinstance(it['value'], dict) else []
            for q in quotes:
                self.assertNotIn(q, json.dumps(blind, ensure_ascii=False))

    def test_text_only_entries_are_counted_as_not_comparable(self):
        originals = [it for g in self.queue['groups'] if g['id'] in self.plan['in_scope']['groups'] for it in g['items']]
        self.assertEqual(sum(not de.numbers(it['value']) for it in originals), 33)


class Comparison(unittest.TestCase):
    def test_numbers_decide_agreement(self):
        first = {'dose_mg': [20, 70], 'regimen': '20 mg/m2 then 70 mg/m2 on Days 1, 8, 15', 'quote': 'ignored 99'}
        self.assertEqual(de.compare(first, {'dose_mg': [70, 20], 'regimen': 'Days 1, 8 and 15; 20 then 70 mg/m2', 'quote': 'x'})['result'], 'agree')
        diff = de.compare(first, {'dose_mg': [20, 56], 'regimen': '20 mg/m2 then 56 mg/m2 on Days 1, 8, 15'})
        self.assertEqual((diff['result'], diff['only_first'], diff['only_second']), ('disagree', ['70.0', '70.0'], ['56.0', '56.0']))

    def test_thousands_separators_and_decimal_commas(self):
        self.assertEqual(de.numbers({'a': '1,500 /mm3', 'b': 1500}), ['1500.0', '1500.0'])
        self.assertEqual(de.numbers({'a': '1,5 mg/dL'}), ['1.5'])

    def test_sample_is_fixed(self):
        ids = [f'B-{i:03d}' for i in range(60)]
        s = de.agreement_sample(ids, 20, 20261111)
        self.assertEqual(s, de.agreement_sample(list(reversed(ids)), 20, 20261111))
        self.assertEqual(len(s), 20)
        self.assertEqual(de.agreement_sample(ids[:5], 20, 20261111), ids[:5])


if __name__ == '__main__':
    unittest.main()


class Result(unittest.TestCase):
    """The second extraction of 12 November 2026, compared under the locked plan."""
    def setUp(self):
        self.result = de.load_result()
        self.plan = de.load_plan()

    def test_result_follows_the_locked_plan(self):
        self.assertEqual(self.result['plan']['sha256'], de.PLAN_SHA256)
        self.assertEqual(len(self.result['entries']), self.plan['in_scope']['entries'])
        self.assertEqual(sum(self.result['counts'].values()), 100)
        self.assertEqual(self.result['counts']['not_comparable'], 33)
        self.assertFalse(self.result['clinical_prediction_validated'])

    def test_comparison_and_sample_recompute(self):
        queue = de.load_queue()
        first = {it['id']: it['value'] for g in queue['groups'] for it in g['items']}
        for e in self.result['entries']:
            if e['result'] == 'not_comparable':
                self.assertEqual(de.numbers(first[e['id']]), [])
            elif e['result'] == 'agree':
                # strict reading: every number in the second reader's entry, added notes included
                self.assertEqual(de.compare(first[e['id']], e['second_reader_value'])['result'], 'agree', e['id'])
                self.assertEqual(e.get('quotes_missing', 0), 0)
        agree = [e['id'] for e in self.result['entries'] if e['result'] == 'agree']
        sample = de.agreement_sample(agree, self.plan['owner_review']['agreements']['sample_size'],
                                     self.plan['owner_review']['agreements']['seed'])
        self.assertEqual(self.result['agreement_sample']['ids'], sample)

