"""Reviewer's checklist R1-R2: kidney-function classifications and each model's measure, from pinned sources."""
import hashlib
import json
import unittest
from pathlib import Path

from flask import Flask

from intelligence_store import kidney_function_classifications as kfc
from intelligence_store.body_map import explorer_map
from intelligence_store.body_map_context import body_map_context

ROOT = Path(__file__).resolve().parents[1]


class GuidanceExtract(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads((ROOT / kfc.SOURCES['fda_2024'][0]).read_text())

    def test_table_1_categories_as_printed(self):
        cats = self.doc['table_1']['categories']
        self.assertEqual([c['printed'] for c in cats], ['≥ 90', '60 < 90', '30 < 60', '< 30'])
        self.assertEqual([(c['range_ml_min']['lower_inclusive'], c['range_ml_min']['upper_exclusive']) for c in cats],
                         [(90, None), (60, 90), (30, 60), (None, 30)])
        self.assertIn('not intended to be used for the purposes of classifying kidney disease', self.doc['table_1']['footnotes']['c'])
        self.assertEqual(self.doc['source']['date'], 'March 2024')

    def test_categories_tile_the_line_without_gaps(self):
        rows = kfc.schemes()['fda_2024']['rows']
        for x in (0.5, 29.99, 30, 59.99, 60, 89.99, 90, 150):
            self.assertEqual(sum(kfc.contains(r['interval'], x) for r in rows), 1, x)

    def test_marked_unreviewed(self):
        self.assertIn('Not yet reviewed by the platform owner', self.doc['source']['extraction'])


class Comparison(unittest.TestCase):
    def setUp(self):
        self.view = kfc.build()
        self.mapping = {m['fda']: m for m in self.view['mapping']}

    def test_every_measure_value_is_read_from_its_source(self):
        for m in self.view['measures']:
            for f in m['facts']:
                doc = json.loads((ROOT / f['file']).read_text())
                self.assertEqual(kfc._resolve(doc, f['pointer']), f['value'])

    def test_measures_named_for_each_model(self):
        values = {m['id']: [f['value'] for f in m['facts']] for m in self.view['measures']}
        self.assertIn('measured creatinine clearance (CLcr)', values['cc5013'])
        self.assertIn('mL/min/1.73m2', values['kim'])
        self.assertIn('unresolved', values['hughes'])
        self.assertIn('ideal_body_weight_devine', values['hughes'])
        self.assertTrue(any('Cockcroft-Gault' in v for v in values['label']))
        self.assertTrue(any('Cockcroft-Gault' in v for v in values['bridoux']))

    def test_mapping_by_overlap(self):
        labels = lambda key, side: [(g['label'], g['overlap']) for g in self.mapping[key][side]]
        self.assertEqual(labels('control', 'cc5013'), [('Normal', 'range')])
        self.assertEqual(labels('mild', 'cc5013'), [('Normal', 'range'), ('Mild', 'range')])
        self.assertEqual(labels('moderate', 'cc5013'), [('Mild', 'range'), ('Moderate', 'range')])
        self.assertEqual(labels('severe', 'cc5013'), [('Severe, not on dialysis', 'range')])
        self.assertEqual(self.mapping['control']['label'], [])
        self.assertEqual(labels('moderate', 'label'), [('Row 1', 'range')])
        self.assertEqual(labels('severe', 'label'), [('Row 2', 'range'), ('Row 3, requiring dialysis', 'range')])

    def test_single_boundary_value_is_marked(self):
        row = self.mapping['mild']['label'][0]
        self.assertEqual((row['overlap'], row['note']), ('point', 'shares only the value 60 mL/min'))

    def test_classify(self):
        for x, fda, study, label in ((95, 'control', 'Normal', None), (85, 'mild', 'Normal', None), (65, 'mild', 'Mild', None),
                                     (55, 'moderate', 'Mild', 'Row 1'), (40, 'moderate', 'Moderate', 'Row 1'),
                                     (20, 'severe', 'Severe, not on dialysis', 'Row 2')):
            c = kfc.classify(x)
            fda_label = next(r['label'] for r in kfc.schemes()['fda_2024']['rows'] if r['id'] == fda)
            self.assertEqual(c['fda_2024']['row']['label'], fda_label, x)
            self.assertEqual(c['cc5013']['row']['label'], study, x)
            self.assertEqual((c['label']['row'] or {}).get('label'), label, x)

    def test_no_dose_wording_and_flag_false(self):
        self.assertIn('proposes a dose', self.view['notes']['scope'])
        self.assertFalse(self.view['clinical_prediction_validated'])
        self.assertEqual(self.view['view_sha256'], kfc.build()['view_sha256'])

    def test_changed_source_is_refused(self):
        path, sha, title = kfc.SOURCES['fda_2024']
        try:
            kfc.SOURCES['fda_2024'] = (path, '0' * 64, title)
            with self.assertRaises(kfc.ClassificationError):
                kfc.build()
        finally:
            kfc.SOURCES['fda_2024'] = (path, sha, title)

    def test_pins_match_the_owning_modules(self):
        from intelligence_store.lenalidomide_label import EXTRACT_SHA256
        from intelligence_store.lenalidomide_renal_pathways import EVIDENCE_SHA256
        self.assertEqual(kfc.SOURCES['label_2023'][1], EXTRACT_SHA256)
        self.assertEqual(kfc.SOURCES['ema_2008'][1], EVIDENCE_SHA256)
        for path, sha, _ in kfc.SOURCES.values():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), sha, path)


class BodyMapContext(unittest.TestCase):
    def test_context_places_the_value_in_each_scheme(self):
        ctx = body_map_context(explorer_map(55))
        by = ctx['classifications']['by_scheme']
        self.assertEqual(by['fda_2024']['row']['label'], 'Moderate impairment')
        self.assertEqual(by['cc5013']['row']['label'], 'Mild')
        self.assertIn('measured creatinine clearance', ctx['classifications']['value_measure'])


class Pages(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(TESTING=True)
        app.add_url_rule('/', 'home', lambda: 'Home')
        from landscape_ui import register_landscape
        register_landscape(app)
        self.client = app.test_client()

    def test_special_populations_page_shows_the_comparison(self):
        html = self.client.get('/landscape/drugs/lenalidomide/special-populations').get_data(as_text=True)
        for text in ('Kidney-function classifications and measures, compared', 'FDA 2024 guidance, Table 1',
                     '60 to &lt; 90 mL/min', 'shares only the value 60 mL/min', 'mL/min/1.73m2', 'Platform note',
                     'have not yet been reviewed by the platform owner', 'eGFR expressed as mL/minute'):
            self.assertIn(text, html)

    def test_other_drugs_do_not_get_it(self):
        html = self.client.get('/landscape/drugs/ixazomib/special-populations').get_data(as_text=True)
        self.assertNotIn('sp-kidney-classifications', html)

    def test_body_map_shows_where_the_value_falls(self):
        html = self.client.get('/landscape/patient-lab/body-map?crcl=55').get_data(as_text=True)
        self.assertIn('Where 55 mL/min falls in each classification', html)
        self.assertIn('sp-kidney-classifications', html)


if __name__ == '__main__':
    unittest.main()
