"""Reviewer's checklist R7: what is known about lenalidomide in dialysis, from pinned sources."""
import unittest

from flask import Flask

from intelligence_store import dialysis_evidence as de
from intelligence_store.lenalidomide_esrd_dialysis import EVIDENCE_SHA256
from intelligence_store.lenalidomide_label import EXTRACT_SHA256, PK_EXTRACT_SHA256


class View(unittest.TestCase):
    def setUp(self):
        self.v = de.build()

    def test_pins_match_owning_modules(self):
        self.assertEqual(de.SOURCES['esrd'][1], EVIDENCE_SHA256)
        self.assertEqual(de.SOURCES['label'][1], EXTRACT_SHA256)
        self.assertEqual(de.SOURCES['label_pk'][1], PK_EXTRACT_SHA256)

    def test_paired_values_and_derived_ratios(self):
        rows = {r['quantity'].split(' ')[0]: r for r in self.v['cc5013']['rows']}
        self.assertEqual(rows['AUCinf']['off'], [11121, 2133])
        self.assertEqual(rows['AUCinf']['on'], [6830, 919])
        self.assertAlmostEqual(rows['AUCinf']['ratio_on_to_off'], 6830 / 11121)
        self.assertAlmostEqual(rows['CL/F']['ratio_on_to_off'], 62 / 39)
        self.assertIsNone(rows['Terminal']['ratio_on_to_off'])

    def test_removal_label_and_myeloma(self):
        text = ' '.join(r['text'] for r in self.v['removal'])
        self.assertIn('146 mL/min', text)
        self.assertIn('31% removed', text)
        self.assertIn('Approximately 30% of the drug in body was removed', text)
        self.assertEqual(self.v['label_row']['regimen'], '5 mg once daily; on dialysis days, after dialysis')
        self.assertEqual(self.v['myeloma']['auc24_gm'], 2020)
        self.assertIn('Not modelled', 'Not modelled. ' + self.v['modelling'])
        self.assertFalse(self.v['clinical_prediction_validated'])

    def test_changed_source_is_refused(self):
        path, sha, title = de.SOURCES['esrd']
        try:
            de.SOURCES['esrd'] = (path, '0' * 64, title)
            with self.assertRaises(de.DialysisEvidenceError):
                de.build()
        finally:
            de.SOURCES['esrd'] = (path, sha, title)


class Page(unittest.TestCase):
    def test_lenalidomide_page(self):
        app = Flask(__name__)
        app.config.update(TESTING=True)
        app.add_url_rule('/', 'home', lambda: 'Home')
        from landscape_ui import register_landscape
        register_landscape(app)
        client = app.test_client()
        html = client.get('/landscape/drugs/lenalidomide/special-populations').get_data(as_text=True)
        for text in ('Dialysis: what is known', 'Same six people', '11,121 (2,133)', '0.61', '146 mL/min', 'Not modelled'):
            self.assertIn(text, html)
        self.assertNotIn('sp-dialysis', client.get('/landscape/drugs/ixazomib/special-populations').get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
