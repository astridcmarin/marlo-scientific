"""Reviewer's checklist H2: hepatic classifications (FDA September 2026 draft guidance) beside the label's definitions."""
import json
import unittest
from pathlib import Path

from flask import Flask

from intelligence_store import hepatic_classifications as hc
from intelligence_store.lenalidomide_label import EXTRACT_SHA256

ROOT = Path(__file__).resolve().parents[1]


class Extract(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads((ROOT / hc.SOURCES['fda_2026'][0]).read_text())

    def test_draft_status_and_docket(self):
        self.assertIn('draft', self.doc['source']['status'])
        self.assertEqual(self.doc['source']['docket'], 'FDA-2026-D-8693')
        self.assertIn('Not yet reviewed by the platform owner', self.doc['source']['extraction'])

    def test_groups(self):
        self.assertEqual([g['score'] for g in self.doc['child_pugh_table_1']['groups']], [[5, 6], [7, 9], [10, 15]])
        self.assertEqual([g['id'] for g in self.doc['nci_odwg_table_2']['groups']], ['A', 'B1', 'B2', 'C', 'D'])
        self.assertIn('5-6 (CP group A)', self.doc['recommendations']['cp_groups']['quote'])
        self.assertIn('assumed', self.doc['child_pugh_table_1']['reading'])


class View(unittest.TestCase):
    def setUp(self):
        self.v = hc.build()

    def test_label_mild_definition_is_nci_group_b(self):
        mild = next(l for l in self.v['label'] if l['statement'] == 'mild')
        self.assertIn('total bilirubin > 1 to 1.5 times upper limit normal', mild['quote'])
        self.assertIn('aspartate transaminase greater than ULN', mild['quote'])
        self.assertEqual([g['id'] for g in mild['nci_groups']], ['B1', 'B2'])
        severe = next(l for l in self.v['label'] if l['statement'] == 'moderate_severe')
        self.assertEqual([g['id'] for g in severe['nci_groups']], ['C', 'D'])

    def test_pins_and_flags(self):
        self.assertEqual(hc.SOURCES['label_2023'][1], EXTRACT_SHA256)
        self.assertIn('proposes a dose', self.v['notes']['scope'])
        self.assertFalse(self.v['clinical_prediction_validated'])
        path, sha, title = hc.SOURCES['fda_2026']
        try:
            hc.SOURCES['fda_2026'] = (path, '0' * 64, title)
            with self.assertRaises(hc.HepaticClassificationError):
                hc.build()
        finally:
            hc.SOURCES['fda_2026'] = (path, sha, title)


class Page(unittest.TestCase):
    def test_lenalidomide_page(self):
        app = Flask(__name__)
        app.config.update(TESTING=True)
        app.add_url_rule('/', 'home', lambda: 'Home')
        from landscape_ui import register_landscape
        register_landscape(app)
        client = app.test_client()
        html = client.get('/landscape/drugs/lenalidomide/special-populations').get_data(as_text=True)
        for text in ('Liver-function classifications compared', 'NCI Organ Dysfunction Working Group', 'Child–Pugh',
                     'did not influence the disposition of lenalidomide', 'No pharmacokinetic data', 'have not been reviewed yet'):
            self.assertIn(text, html)
        self.assertNotIn('sp-hepatic-classifications', client.get('/landscape/drugs/ixazomib/special-populations').get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
