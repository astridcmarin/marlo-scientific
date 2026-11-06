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



class Display(unittest.TestCase):
    def test_view_carries_every_section_quote_with_a_location(self):
        view = ll.label_pk_view()
        self.assertEqual([s['id'] for s in view['sections']], ['absorption', 'elimination', 'interactions'])
        shown = [q for s in view['sections'] for i in s['items'] for q in i['quotes']]
        all_quotes = [q for _, q in quotes(ll.load_label_pk_extract())]
        self.assertEqual(sorted(set(shown)), sorted(q for q in all_quotes if q in shown))
        self.assertEqual(len(shown), 19)  # all but the mantle-cell lymphoma absorption sentence
        self.assertTrue(all(i['location'] for s in view['sections'] for i in s['items']))

    def test_guided_path_step_is_read_from_the_extract(self):
        from intelligence_store.guided_path import lenalidomide_path
        step = next(s for s in lenalidomide_path()['steps'] if s['id'] == 'pharmacokinetics')
        for text in ('Peak at 0.5-6 h', 'AUC about 20%', 'Cmax about 50%', '3-5 h', 'about 90%', '82% as unchanged',
                     'about 30% removed in a 4-hour', 'up 14%'):
            self.assertIn(text, step['found'])
        self.assertIn('have not been reviewed yet', step['checked'])
        self.assertIn('No interaction is modelled', step['missing'])

    def test_pages(self):
        from flask import Flask
        app = Flask(__name__)
        app.config.update(TESTING=True)
        app.add_url_rule('/', 'home', lambda: 'Home')
        from landscape_ui import register_landscape
        register_landscape(app)
        client = app.test_client()
        html = client.get('/landscape/drugs/lenalidomide/special-populations').get_data(as_text=True)
        for text in ('Label pharmacokinetics and drug interactions (quoted)', 'Digoxin (section 7.1)',
                     'Transporters (in vitro)', 'Not stated by the label', 'have not been reviewed yet'):
            self.assertIn(text, html)
        self.assertNotIn('sp-label-pk', client.get('/landscape/drugs/ixazomib/special-populations').get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
