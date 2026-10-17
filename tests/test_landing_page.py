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
        _tmp.cleanup()

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
        for path in ('/trials', '/landscape/', '/landscape/patient-lab/workspace', '/landscape/simulation-lab',
                     '/landscape/drugs', '/landscape/regulatory', '/static/landing.css', '/static/images/favicon.png'):
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
        self.assertIn('Marlo Scientific home', page)
        self.assertIn('action="/trials"', page)
        self.assertNotIn('action="/"', page)


if __name__ == '__main__':
    unittest.main()
