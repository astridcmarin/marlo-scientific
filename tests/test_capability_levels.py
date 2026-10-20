import unittest

from flask import Flask

from intelligence_store import capability_levels as cl
from intelligence_store.drug_capabilities import capability_inventory
from intelligence_store.model_scorecards import all_scorecards
from landscape_ui import register_landscape


class LevelRules(unittest.TestCase):
    def test_levels_are_ordered_and_label_based_is_assigned_only_after_its_checks(self):
        self.assertEqual([l['rank'] for l in cl.LEVELS], list(range(len(cl.LEVELS))))
        inventory = capability_inventory()
        self.assertEqual(inventory['capability_level_counts']['label_based_exposure'], 1)
        self.assertEqual(sum(inventory['capability_level_counts'].values()), inventory['counts']['drug_entities'])

    def test_level_follows_the_scorecards(self):
        cards = all_scorecards()
        for drug in {c['drug'] for c in cards['cards']}:
            level = cl.drug_level(drug, True, cards)
            models = [c for c in cards['cards'] if c['drug'] == drug]
            self.assertEqual({m['model_id'] for m in level['models']}, {c['model_id'] for c in models})
            checked = any(c['layers'][-1]['status'] in cl.CHECKED for c in models)
            self.assertEqual(level['id'], 'published_model_checked' if checked else 'published_model')
            self.assertIsNone(level['label_exposure_drug'])
            self.assertEqual(level['outside_data_disagreements'], sum(len(c['outside_data_disagreements']) for c in models))

    def test_drugs_without_models_are_knowledge_or_identity_only(self):
        self.assertEqual(cl.drug_level('Not a registered drug', True)['id'], 'knowledge_only')
        self.assertEqual(cl.drug_level('Not a registered drug', False)['id'], 'identity_only')
        self.assertEqual(cl.drug_level('Not a registered drug', True)['models'], [])

    def test_current_inventory(self):
        levels = {e['label']: e['capability_level'] for e in capability_inventory()['entries']}
        self.assertEqual(levels['Lenalidomide']['id'], 'published_model_checked')
        self.assertEqual(levels['Bortezomib']['id'], 'published_model_checked')
        self.assertEqual(levels['Bortezomib']['outside_data_disagreements'], 3)
        self.assertIn('disagreement', levels['Lenalidomide']['note'])
        self.assertEqual(levels['Pomalidomide']['id'], 'label_based_exposure')
        self.assertEqual(levels['Pomalidomide']['label_exposure_drug'], 'pomalidomide')
        self.assertTrue(all(levels[d]['id'] == 'knowledge_only' for d in levels if d not in ('Lenalidomide', 'Bortezomib', 'Pomalidomide')))


class LevelPages(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.add_url_rule('/', 'home', lambda: 'Home')
        register_landscape(app)
        self.client = app.test_client()

    def test_library_shows_a_level_and_the_legend_for_every_drug(self):
        page = self.client.get('/landscape/patient-lab/model-library').get_data(as_text=True)
        inventory = capability_inventory()
        self.assertEqual(page.count('class="cap-level cap-level-'), len(inventory['entries']))
        self.assertIn('What the capability levels mean', page)
        for level in cl.LEVELS:
            self.assertIn(level['label'], page)
        self.assertIn('outside data disagree', page)
        self.assertIn('/landscape/patient-lab/label-exposure/pomalidomide', page)
        # Without the main app's scorecard pages, model names are shown without links.
        self.assertNotIn('/models/', page)


if __name__ == '__main__':
    unittest.main()
