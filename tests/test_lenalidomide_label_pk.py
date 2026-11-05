"""The rest of REVLIMID section 12.3 and section 7 (5 November 2026), for owner review round 3."""
import json
import re
import unittest

from intelligence_store import lenalidomide_label as ll


def quotes(node, path=''):
    if isinstance(node, dict):
        for k, v in node.items():
            if k.endswith('quote') and isinstance(v, str):
                yield f'{path}/{k}', v
            else:
                yield from quotes(v, f'{path}/{k}')


def numbers(node):
    if isinstance(node, bool):
        return
    if isinstance(node, (int, float)):
        yield node
    elif isinstance(node, list):
        for v in node:
            yield from numbers(v)
    elif isinstance(node, dict):
        for v in node.values():
            yield from numbers(v)


class LabelPkExtract(unittest.TestCase):
    def setUp(self):
        self.d = ll.load_label_pk_extract()

    def test_same_label_file_as_the_reviewed_extract(self):
        self.assertEqual(self.d['source']['file_reviewed'], ll.load_label_extract()['source']['file_reviewed'])

    def test_marked_unreviewed_and_not_validated(self):
        self.assertIn('Not yet reviewed by the platform owner', self.d['source']['extraction'])
        self.assertFalse(self.d['clinical_prediction_validated'])

    def test_every_number_appears_in_its_own_quote(self):
        """Each block's numbers are transcribed from that block's quotes (locations excluded)."""
        def blocks(node):
            if isinstance(node, dict):
                qs = [v for k, v in node.items() if k.endswith('quote') and isinstance(v, str)]
                if qs:
                    yield node, ' '.join(qs)
                for k, v in node.items():
                    if isinstance(v, dict):
                        yield from blocks(v)
        checked = 0
        for block, text in blocks(self.d):
            found = {float(x) for x in re.findall(r'\d+(?:\.\d+)?', text)}
            for k, v in block.items():
                if k.endswith('quote') or k in ('location', 'note'):
                    continue
                for n in numbers(v):
                    self.assertIn(float(n), found, (k, n))
                    checked += 1
        self.assertGreaterEqual(checked, 18)

    def test_key_values(self):
        a, e = self.d['absorption'], self.d['elimination']
        self.assertEqual(a['tmax']['tmax_range_h'], [0.5, 6])
        self.assertEqual((a['food_effect']['auc_decrease_percent_approx'], a['food_effect']['cmax_decrease_percent_approx']), (20, 50))
        self.assertFalse(a['bioavailability']['stated'])
        self.assertEqual(e['excretion']['radioactive_dose_percent_10_days'], {'urine': 90, 'feces': 4})
        self.assertEqual(e['excretion']['unchanged_in_urine_24_h_percent_of_radioactive_dose'], 82)
        self.assertEqual(self.d['drug_interactions_7']['digoxin']['digoxin_cmax_and_auc_increase_percent'], 14)

    def test_quotes_are_sentences_with_locations(self):
        qs = list(quotes(self.d))
        self.assertEqual(len(qs), 20)
        for path, q in qs:
            self.assertTrue(q.rstrip().endswith(('.', ')]', '.]')), path)

    def test_changed_file_is_refused(self):
        original = ll.PK_EXTRACT_SHA256
        try:
            ll.PK_EXTRACT_SHA256 = '0' * 64
            with self.assertRaises(ValueError):
                ll.load_label_pk_extract()
        finally:
            ll.PK_EXTRACT_SHA256 = original


if __name__ == '__main__':
    unittest.main()
