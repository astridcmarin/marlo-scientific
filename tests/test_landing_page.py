import os
import tempfile
import unittest

_tmp = tempfile.TemporaryDirectory()
_previous = os.environ.get('DATABASE_URL')
os.environ['DATABASE_URL'] = f"sqlite:///{os.path.join(_tmp.name, 'landing.db')}"
try:
    from app.app import app
finally:
    if _previous is None:
        os.environ.pop('DATABASE_URL', None)
    else:
        os.environ['DATABASE_URL'] = _previous


class LandingPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from intelligence_store.extensions import db
        with app.app_context():
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        from intelligence_store.extensions import db
        with app.app_context():
            db.engine.dispose()
        # The temporary folder is removed at interpreter exit: other test modules share this app instance.

    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_root_is_the_landing_page_with_working_links(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        for text in ('Advancing Drug Research Through Intelligent Science', 'Not a clinical prediction',
                     'Simulated results are not clinical predictions', 'Patient records are synthetic',
                     'href="/trials"', 'href="/landscape/"', 'href="/landscape/patient-lab/workspace"',
                     'https://github.com/astridcmarin/marlo-scientific', 'landing.css'):
            self.assertIn(text, page)
        import re
        links = sorted(set(re.findall(r'href="(/[^"#]*)"', page)))
        self.assertGreaterEqual(len(links), 12)
        for path in links:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            response.close()

    def test_old_search_links_redirect_to_the_explorer(self):
        response = self.client.get('/?condition=myeloma&phase=PHASE3')
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response.headers['Location'].startswith('/trials?'))
        self.assertIn('condition=myeloma', response.headers['Location'])
        self.assertIn('phase=PHASE3', response.headers['Location'])

    def test_explorer_links_back_and_searches_in_place(self):
        page = self.client.get('/trials').get_data(as_text=True)
        self.assertIn('class="ms-brand" href="/"', page)
        self.assertIn('href="/trials" aria-current="page">Clinical trials</a>', page)
        self.assertIn('brand.css', page)
        self.assertIn('action="/trials"', page)
        self.assertNotIn('action="/"', page)


    def test_one_brand_and_navigation_across_landing_explorer_and_workspace(self):
        sections = ('>Clinical trials</a>', '>Drugs &amp; regulatory</a>', '>Patient Lab</a>', '>Simulation Lab</a>')
        landing = self.client.get('/').get_data(as_text=True)
        explorer = self.client.get('/trials').get_data(as_text=True)
        for page in (landing, explorer):
            for text in sections + ('Marlo Scientific', 'images/marlo-mark.png'):
                self.assertIn(text, page)
        workspace = self.client.get('/landscape/simulation-lab').get_data(as_text=True)
        for text in ('Marlo Scientific', 'images/marlo-mark.png', 'Clinical &amp; Pharmaceutical Intelligence',
                     '<p class="nav-label">Clinical trials</p>', '<p class="nav-label">Drugs &amp; regulatory</p>',
                     '<p class="nav-label">Pharmacology lab</p>', '<p class="nav-label">Your work</p>',
                     'class="brand" href="/"', 'Marlo Scientific · Pharmacology lab'):
            self.assertIn(text, workspace)
        self.assertNotIn('Clinical Intelligence<span', workspace)
        self.assertNotIn('v2 ·', workspace)

    def test_about_the_developer(self):
        page = self.client.get('/').get_data(as_text=True)
        for text in ('Built by Astrid Marin', 'MSc in Pharmaceutical Sciences (Pharmaceutical Affairs)',
                     'ICH-GCP', 'https://www.linkedin.com/in/astridcmarin/', 'https://github.com/astridcmarin',
                     'accelerate drug research and development with AI', 'images/astrid-marin.jpg', 'alt="Astrid Marin"',
                     'href="/#about">About</a>'):
            self.assertIn(text, page)
        self.assertNotIn('mailto:', page)
        self.assertNotIn('amarinmassini', page)
        self.assertLess(page.index('id="about"'), page.index('class="site-footer"'))

    def test_intended_use_page_is_linked_everywhere(self):
        page = self.client.get('/intended-use')
        self.assertEqual(page.status_code, 200)
        text = page.get_data(as_text=True)
        for phrase in ('not a medical device', 'Not intended for', 'Do not enter information about real people',
                       'No model on the platform is validated for clinical prediction', 'without warranty',
                       'class="ms-header"', 'class="site-footer"'):
            self.assertIn(phrase, text)
        for path in ('/', '/trials', '/landscape/simulation-lab', '/intended-use'):
            self.assertIn('href="/intended-use"', self.client.get(path).get_data(as_text=True), path)

    def test_charts_come_from_platform_code(self):
        from landscape_ui.landing_examples import curve_example, kidney_example
        from intelligence_store.lenalidomide_renal_pathways import calibrate, load_evidence, pathways
        page = self.client.get('/').get_data(as_text=True)
        curve = curve_example()
        self.assertIn(curve['polyline'], page)
        self.assertIn('Not a dosing illustration', page)
        cal = calibrate(load_evidence(), 110.0, 0.77)
        for row in kidney_example()['rows']:
            p = pathways(cal, row['crcl'], 'A_intact_nephron')
            self.assertEqual(row['shares'][0]['pct'], round(100 * p['filtration_ml_min'] / p['total_ml_min']))
            self.assertIn(f"Filtration {row['shares'][0]['pct']}%", page)

    def test_example_curve_file_matches_a_fresh_calculation(self):
        import json, sys
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(root / 'scripts'))
        try:
            import landing_example_curve as generator
        finally:
            sys.path.remove(str(root / 'scripts'))
        stored = json.loads(generator.OUT.read_text(encoding='utf-8'))
        fresh = generator.build()
        self.assertEqual(fresh, stored)
        self.assertEqual(stored['request']['single_dose_mg'], 25.0)


class WithoutLandingPage(unittest.TestCase):
    def test_workspace_brand_falls_back_when_the_app_has_no_landing_page(self):
        from flask import Flask
        from landscape_ui import register_landscape
        test_app = Flask(__name__)
        test_app.add_url_rule('/', 'home', lambda: 'Home')
        register_landscape(test_app)
        with test_app.test_request_context('/'):
            from landscape_ui import _site_context
            context = _site_context()
        self.assertEqual(context['site_home_url'], '/landscape/')
        self.assertEqual([key for key, _, _ in context['site_sections']], ['trials', 'drugs', 'patient', 'simulation'])


if __name__ == '__main__':
    unittest.main()
