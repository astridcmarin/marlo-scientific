"""Phase 3.2d: the five label extracts of 4 November 2026 are pinned, quoted and located."""
import re
import unittest

from intelligence_store import drug_label_extracts as dle


def numbers(obj):
    if isinstance(obj, bool) or obj is None:
        return []
    if isinstance(obj, (int, float)):
        return [obj]
    if isinstance(obj, dict):
        return [n for v in obj.values() for n in numbers(v)]
    if isinstance(obj, list):
        return [n for v in obj for n in numbers(v)]
    return []


def in_quote(n, quote):
    q = quote.replace(',', '')
    forms = {f'{n:g}', f'{n}', f'{n:.1f}', f'{n:.2f}'}
    return any(re.search(r'(?<![\d.])' + re.escape(f) + r'(?![\d])', q) for f in forms)


class Extracts(unittest.TestCase):
    def test_all_pinned_and_flags_false(self):
        for drug in dle.EXTRACTS:
            doc = dle.load_extract(drug)
            self.assertFalse(doc['clinical_prediction_validated'])
            self.assertEqual(len(doc['source']['file_reviewed']['sha256']), 64)
            self.assertIn('dailymed.nlm.nih.gov', doc['source']['url'])

    def test_every_value_has_quote_location_and_check(self):
        for drug in dle.EXTRACTS:
            for e in dle.entries(drug):
                self.assertTrue(e['quote'].strip(), (drug, e['key']))
                self.assertRegex(e['location'], r'^section [\d.]+, PDF pages? \d+(-\d+)?$', (drug, e['key']))
                self.assertIn(e['check'], ('text', 'text_and_rendered_page'))

    def test_numbers_appear_in_their_quote(self):
        """Values quoted from running text must appear in the quoted sentence. Table values (quote = table title) were
        read from the rendered page; fold changes stated as percentages are checked as the percentage."""
        for drug in dle.EXTRACTS:
            for e in dle.entries(drug):
                if e['quote'].startswith('Table '):
                    continue
                for field, value in e.items():
                    if field in ('quote', 'location', 'check', 'section', 'key', 'stated_as', 'note', 'population', 'statistic', 'n', 'interval_h'):   # interval_h is read from 'once daily'
                        continue
                    for n in numbers(value):
                        if field == 'value' and 'stated_as' in e and '%' in e['stated_as']:
                            n = round((n - 1) * 100)
                        if field == 'value' and e.get('stated_as', '').startswith(('comparable', 'not', 'unknown')):
                            continue
                        if field in ('upper_bound',) and n < 0.1:
                            n = round(n * 100, 1)
                        self.assertTrue(in_quote(n, e['quote']), (drug, e['key'], field, n))

    def test_antibodies_are_not_label_engine_candidates(self):
        for drug in ('isatuximab', 'elotuzumab'):
            self.assertNotIn(drug, dle.LABEL_ENGINE_CANDIDATES)
            self.assertIn('antibody', dle.load_extract(drug)['modality'])

    def test_changed_file_is_refused(self):
        name, _ = dle.EXTRACTS['selinexor']
        old = dle.EXTRACTS['selinexor']
        try:
            dle.EXTRACTS['selinexor'] = (name, '0' * 64)
            with self.assertRaises(dle.LabelExtractError):
                dle.load_extract('selinexor')
        finally:
            dle.EXTRACTS['selinexor'] = old


if __name__ == '__main__':
    unittest.main()
