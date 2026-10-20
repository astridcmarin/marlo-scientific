import hashlib
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_tmp = tempfile.TemporaryDirectory()
_previous = os.environ.get('DATABASE_URL')
os.environ['DATABASE_URL'] = f"sqlite:///{os.path.join(_tmp.name, 'scorecards.db')}"
try:
    from app.app import app
finally:
    if _previous is None:
        os.environ.pop('DATABASE_URL', None)
    else:
        os.environ['DATABASE_URL'] = _previous

from intelligence_store import model_scorecards as ms
from intelligence_store.run_record import LAYER_ORDER, load_evidence_status

ROOT = Path(__file__).resolve().parent.parent


class ScorecardData(unittest.TestCase):
    def test_every_registered_model_has_a_card_copied_from_the_evidence_file(self):
        evidence = load_evidence_status()
        data = ms.all_scorecards()
        self.assertEqual({c['model_id'] for c in data['cards']}, set(evidence['models']))
        for card in data['cards']:
            source = evidence['models'][card['model_id']]
            self.assertEqual(card['name'], source['name'])
            self.assertEqual(card['citation'], source['citation'])
            self.assertIs(card['clinical_prediction_validated'], False)
            self.assertEqual([l['id'] for l in card['layers']], list(LAYER_ORDER))
            for layer in card['layers']:
                self.assertEqual(layer['status'], source['layers'][layer['id']]['status'])
                self.assertEqual(layer['status_label'], ms.STATUS_LABELS[layer['status']][0])
                self.assertEqual(layer['summary'], source['layers'][layer['id']]['summary'])
            self.assertEqual(sum(card['counts'].values()), 4)
            self.assertIn(card['model_id'], ms.PROFILES, 'every registered model needs its drug and pages described')

    def test_every_status_and_outcome_in_use_has_a_plain_label(self):
        evidence = load_evidence_status()
        layers = [l for m in evidence['models'].values() for l in m['layers'].values()]
        self.assertLessEqual({l['status'] for l in layers}, set(ms.STATUS_LABELS))
        outcomes = {o for l in layers for key in ms.RESULT_KEYS for o in (l.get(key) or {}).values()}
        outcomes |= {o for l in layers for x in l.get('further_reports', []) for o in (x.get('results') or {}).values()}
        self.assertLessEqual(outcomes, set(ms.OUTCOME_LABELS))
        items = {i for l in layers for key in ms.RESULT_KEYS for i in (l.get(key) or {})}
        items |= {i for l in layers for x in l.get('further_reports', []) for i in (x.get('results') or {})}
        self.assertLessEqual(items, set(ms.RESULT_ITEMS))

    def test_recorded_disagreements_are_surfaced(self):
        cards = {c['model_id']: c for c in ms.all_scorecards()['cards']}
        self.assertEqual({r['item'] for r in cards['lenalidomide_hughes_2019']['outside_data_disagreements']},
                         {'Moderate kidney impairment', 'Severe kidney impairment'})
        self.assertEqual(len(cards['bortezomib_pk_lignet_2022']['outside_data_disagreements']), 3)
        platelet = cards['bortezomib_platelets_lignet_2022']
        self.assertEqual(platelet['outside_data_disagreements'], [])
        self.assertEqual(platelet['depends_on'][0]['model_id'], 'bortezomib_pk_lignet_2022')
        self.assertEqual(platelet['depends_on'][0]['disagreements'], 3)

    def test_cited_reports_are_found_and_intact(self):
        reports = [r for c in ms.all_scorecards()['cards'] for l in c['layers'] for r in l['reports']]
        self.assertEqual(len(reports), 8)
        self.assertTrue(all(r['intact'] for r in reports))

    def test_a_changed_or_uncited_report_is_not_served(self):
        name = 'lenalidomide_renal_pathways_check_v1.json'
        self.assertIsNotNone(ms.cited_report(name))
        with patch.object(ms, '_matches', return_value=False):
            self.assertIsNone(ms.cited_report(name))
        self.assertIsNone(ms.cited_report('../../CLAUDE.md'))
        self.assertIsNone(ms.cited_report('not_cited.json'))


class ScorecardPages(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_index_lists_every_model_with_its_four_checks(self):
        page = self.client.get('/models').get_data(as_text=True)
        cards = ms.all_scorecards()['cards']
        for card in cards:
            self.assertIn(f'href="/models/{card["model_id"]}"', page)
        self.assertIn(ms.NOT_ESTABLISHED, page)
        self.assertNotIn('clinical_prediction_validated', page)
        # four checks plus the outside-data column per model
        self.assertEqual(page.count('class="status status-'), 5 * len(cards))
        self.assertIn('Not done', page)

    def test_detail_page_shows_findings_failures_and_report_links(self):
        page = self.client.get('/models/bortezomib_pk_lignet_2022').get_data(as_text=True)
        self.assertIn('Bortezomib three-compartment PK', page)
        self.assertIn('doi:10.1002/psp4.12743', page)
        self.assertIn('bortezomib_pk_ogawa_check_v1.json', page)
        self.assertIn('checksum verified', page)
        self.assertIn('Where outside data disagree', page)
        self.assertIn('Model too high', page)
        evidence = load_evidence_status()['models']['bortezomib_pk_lignet_2022']
        self.assertIn(evidence['layers']['external_consistency']['summary'].split('.')[0], page)
        links = re.findall(r'href="(/models/reports/[^"]+)"', page)
        self.assertTrue(links)
        for link in links:
            response = self.client.get(link)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, 'application/json')
            name = link.rsplit('/', 1)[1]
            self.assertEqual(response.data, (ROOT / 'docs' / 'verification' / name).read_bytes())
            response.close()

    def test_dependent_model_inherits_the_warning(self):
        page = self.client.get('/models/bortezomib_platelets_lignet_2022').get_data(as_text=True)
        self.assertIn('Its errors carry through to this model', page)
        self.assertIn('href="/models/bortezomib_pk_lignet_2022"', page)

    def test_drug_library_links_each_level_to_its_scorecards(self):
        page = self.client.get('/landscape/patient-lab/model-library').get_data(as_text=True)
        for card in ms.all_scorecards()['cards']:
            self.assertIn(f'href="/models/{card["model_id"]}"', page)

    def test_unknown_model_and_report_are_404(self):
        self.assertEqual(self.client.get('/models/not_a_model').status_code, 404)
        self.assertEqual(self.client.get('/models/reports/not_cited.json').status_code, 404)

    def test_scorecards_are_linked_from_landing_footer_and_run_records(self):
        landing = self.client.get('/').get_data(as_text=True)
        self.assertIn('href="/models"', landing)
        self.assertIn("See every model's scorecard", landing)
        for path in ('/intended-use', '/models'):
            self.assertIn('>Model scorecards</a>', self.client.get(path).get_data(as_text=True))
        macros = (ROOT / 'landscape_ui' / 'templates' / 'run_record_macros.html').read_text(encoding='utf-8')
        self.assertIn("{{ site_models_url }}/{{ record.model.model_id }}", macros)


if __name__ == '__main__':
    unittest.main()
