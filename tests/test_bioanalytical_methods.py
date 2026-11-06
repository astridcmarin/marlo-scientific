"""Reviewer's checklist O8: the assays behind the lenalidomide kidney-function datasets."""
import re
import unittest

from flask import Flask

from intelligence_store import lenalidomide_label as ll


class Extract(unittest.TestCase):
    def setUp(self):
        self.d = ll.load_bioanalytical_methods()
        self.s = {s['id']: s for s in self.d['studies']}

    def test_every_dataset_used_for_kidney_checks_is_covered(self):
        self.assertEqual(set(self.s), {'cc5013_pk001', 'bridoux_2016', 'kim_2026', 'hughes_2019'})

    def test_numbers_appear_in_their_quotes(self):
        for s in self.d['studies']:
            text = ' '.join(s['quotes']).replace(',', '').replace(' 000', '000')
            found = {float(x) for x in re.findall(r'\d+(?:\.\d+)?', text)}
            for key in ('plasma_range_ng_ml', 'plasma_lloq_ng_ml', 'urine_range_ng_ml', 'urine_lloq_ng_ml'):
                for v in ([s[key]] if isinstance(s.get(key), (int, float)) else s.get(key) or []):
                    self.assertIn(float(v), found, (s['id'], key, v))

    def test_cited_methods_say_so(self):
        self.assertIn('[14]', self.s['bridoux_2016']['quotes'][0])
        self.assertIn('Chen N', self.s['bridoux_2016']['quotes'][1])
        self.assertNotIn('plasma_range_ng_ml', self.s['hughes_2019'])
        self.assertIn('Not yet reviewed by the platform owner', self.d['extraction'])

    def test_changed_file_is_refused(self):
        original = ll.ASSAY_SHA256
        try:
            ll.ASSAY_SHA256 = '0' * 64
            with self.assertRaises(ValueError):
                ll.load_bioanalytical_methods()
        finally:
            ll.ASSAY_SHA256 = original


class Page(unittest.TestCase):
    def test_lenalidomide_page(self):
        app = Flask(__name__)
        app.config.update(TESTING=True)
        app.add_url_rule('/', 'home', lambda: 'Home')
        from landscape_ui import register_landscape
        register_landscape(app)
        html = app.test_client().get('/landscape/drugs/lenalidomide/special-populations').get_data(as_text=True)
        for text in ('Assays behind the kidney data', 'chiral LC/MS/MS', '5–200 ng/mL; LLOQ 5 ng/mL', 'not stated in the paper',
                     'as described previously [14]'):
            self.assertIn(text, html)


if __name__ == '__main__':
    unittest.main()
