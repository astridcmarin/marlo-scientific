"""Sidebar navigation by research workflow (3 November 2026), checked without a database."""
import re
import unittest

from flask import Flask

from landscape_ui import SITE_SECTIONS, register_landscape

SECTIONS = ['Diseases and trials', 'Drugs &amp; regulatory', 'Models and evidence', 'Patient Lab', 'Experiments', 'Your work']


class NavigationTests(unittest.TestCase):
    def app(self, with_model_pages):
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.add_url_rule('/', 'home', lambda: 'Home')
        if with_model_pages:
            for rule, endpoint in (('/models', 'model_scorecards'), ('/models/credibility', 'credibility_records'),
                                   ('/models/extraction-review', 'extraction_review')):
                app.add_url_rule(rule, endpoint, lambda: '')
        register_landscape(app)
        return app.test_client()

    def page(self, path, with_model_pages=False):
        response = self.app(with_model_pages).get(path)
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def active(self, html):
        items = re.findall(r'class="nav-item active"[^>]*><span aria-hidden="true">[^<]*</span> ([^<]+)</a>', html)
        self.assertEqual(len(items), 1, items)
        return items[0]

    def test_sections_in_workflow_order(self):
        html = self.page('/landscape/simulation-lab')
        labels = re.findall(r'<p class="nav-label">([^<]+)</p>', html)
        self.assertEqual(labels, SECTIONS)
        self.assertIn('Clinical, regulatory &amp; pharmacology research', html)

    def test_pages_that_were_missing_from_the_menu_are_reachable(self):
        html = self.page('/landscape/simulation-lab', with_model_pages=True)
        for href in ('/landscape/benchmarking', '/landscape/drugs/lenalidomide/guide',
                     '/landscape/drugs/lenalidomide/dose-optimisation', '/models', '/models/credibility',
                     '/models/extraction-review', '/landscape/patient-lab/model-library',
                     '/landscape/patient-lab/published-renal-pk', '/landscape/validation', '/landscape/workspace/watchlists'):
            self.assertIn(f'href="{href}"', html)

    def test_model_pages_from_another_app_are_left_out_when_absent(self):
        html = self.page('/landscape/simulation-lab', with_model_pages=False)
        self.assertNotIn('Model scorecards', html)
        self.assertNotIn('Extraction review', html)
        self.assertIn('<p class="nav-label">Models and evidence</p>', html)

    def test_one_active_item_and_matching_top_bar(self):
        cases = {
            '/landscape/simulation-lab': ('Simulation Lab', 'Experiments'),
            '/landscape/patient-lab/transit-demo': ('Simulation Lab', 'Experiments'),
            '/landscape/patient-lab/model-library': ('Drug and model library', 'Models and evidence'),
            '/landscape/patient-lab/published-renal-pk': ('Published renal PK evidence', 'Models and evidence'),
        }
        for path, (item, section) in cases.items():
            with self.subTest(path=path):
                html = self.page(path)
                self.assertEqual(self.active(html), item)
                self.assertIn(f'<span>Marlo Scientific · {section}</span><span class="version-tag">{item}</span>', html)

    def test_shared_header_lists_models_and_evidence(self):
        self.assertIn(('models', 'Models and evidence', 'model_scorecards'), SITE_SECTIONS)


if __name__ == '__main__':
    unittest.main()
