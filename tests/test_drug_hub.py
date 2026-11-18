"""Drug hub links (layout step 2): built from what the platform records, checked without a database."""
import unittest

from flask import Flask

from landscape_ui import register_landscape
from landscape_ui.drug_hub import GROUPS, hub_links


class DrugHubTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.add_url_rule('/', 'home', lambda: 'Home')
        self.app.add_url_rule('/models/<model_id>', 'model_scorecard', lambda model_id: '')
        register_landscape(self.app)

    def hub(self, entity_id, label):
        with self.app.test_request_context():
            return {g['id']: g for g in hub_links(entity_id, label)}

    def titles(self, hub, group):
        return [link['title'] for link in hub[group]['links']]

    def test_lenalidomide_gathers_guide_label_models_evidence_and_patient_tools(self):
        hub = self.hub('lenalidomide', 'Lenalidomide')
        self.assertEqual(self.titles(hub, 'guide'), ['Guided path', 'Dose view'])
        self.assertEqual(self.titles(hub, 'label'), ['Special populations'])
        self.assertEqual(len(hub['models']['links']), 4)
        self.assertTrue(all(link['url'].startswith('/models/lenalidomide_') for link in hub['models']['links']))
        self.assertIn('Published renal PK evidence', self.titles(hub, 'evidence'))
        self.assertIn('Body map (3D)', hub['patients']['links'][0]['note'])
        explorer = [link for link in hub['tools']['links'] if link['title'] == 'Body map explorer']
        self.assertEqual([link['url'] for link in explorer], ['/landscape/patient-lab/body-map'])

    def test_bortezomib_lists_its_research_tools_and_both_models(self):
        hub = self.hub('bortezomib', 'Bortezomib')
        self.assertIn('Platelet time course (Lignet 2022)', self.titles(hub, 'tools'))
        self.assertEqual(len(hub['models']['links']), 2)
        self.assertTrue(any('disagreement' in link['note'] for link in hub['models']['links']))

    def test_label_based_exposure_for_pomalidomide(self):
        hub = self.hub('pomalidomide', 'Pomalidomide')
        self.assertEqual(self.titles(hub, 'tools'), ['Label-based exposure'])
        self.assertNotIn('models', hub)

    def test_drug_without_platform_tools_gets_no_hub(self):
        self.assertEqual(self.hub('melphalan', 'Melphalan'), {})

    def test_groups_keep_their_order(self):
        hub = self.hub('lenalidomide', 'Lenalidomide')
        order = [key for key, _ in GROUPS]
        self.assertEqual(list(hub), [key for key in order if key in hub])

    def test_missing_main_app_pages_are_left_out(self):
        app = Flask(__name__)
        app.add_url_rule('/', 'home', lambda: 'Home')
        register_landscape(app)
        with app.test_request_context():
            hub = {g['id']: g for g in hub_links('lenalidomide', 'Lenalidomide')}
        self.assertNotIn('models', hub)
        self.assertIn('guide', hub)


class HubFindings(unittest.TestCase):
    """Evidence-first plan item 4 (18 November 2026): each drug's checks, linked to their rows on the findings page."""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.add_url_rule('/', 'home', lambda: 'Home')
        self.app.add_url_rule('/models/<model_id>', 'model_scorecard', lambda model_id: '')
        self.app.add_url_rule('/models/findings', 'check_findings', lambda: '')
        register_landscape(self.app)

    def hub(self, entity_id, label):
        with self.app.test_request_context():
            return {g['id']: g for g in hub_links(entity_id, label)}

    def test_bortezomib_lists_all_eight_checks_with_anchors_and_outcomes(self):
        links = self.hub('bortezomib', 'Bortezomib')['findings']['links']
        self.assertEqual(len(links), 8)
        self.assertTrue(all(link['url'].startswith('/models/findings#') for link in links))
        self.assertIn('/models/findings#kuan', [link['url'] for link in links])
        self.assertTrue(all(link['note'].endswith('.') for link in links))

    def test_findings_follow_models_in_the_hub(self):
        order = list(self.hub('ixazomib', 'Ixazomib'))
        self.assertLess(order.index('models'), order.index('findings'))

    def test_a_drug_whose_only_record_is_a_failed_check_now_shows_it(self):
        hub = self.hub('melphalan', 'Melphalan')
        self.assertEqual(list(hub), ['findings'])
        self.assertEqual([link['url'] for link in hub['findings']['links']], ['/models/findings#melphalan_label'])

if __name__ == '__main__':
    unittest.main()
