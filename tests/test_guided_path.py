"""Phase 4.4: lenalidomide guided path."""
import json
import unittest

from intelligence_store.guided_path import MODELS, lenalidomide_path


class Path_(unittest.TestCase):
    def test_steps_read_from_pinned_sources(self):
        p = lenalidomide_path()
        self.assertEqual([s['id'] for s in p['steps']], ['trials', 'knowledge', 'special_populations', 'exposure', 'dose', 'credibility'])
        self.assertFalse(p['clinical_prediction_validated'])
        steps = {s['id']: s for s in p['steps']}
        self.assertIn('380 of 3450', steps['trials']['found'])
        self.assertIn('25 mg', steps['knowledge']['found'])
        self.assertIn('54 patients, 26 events', steps['dose']['missing'])
        self.assertEqual(p['review'], {'values': 78, 'reviewed': 0})
        self.assertIn('0 of 78', steps['credibility']['checked'])
        for s in p['steps']:
            for key in ('found', 'checked', 'missing'):
                self.assertTrue(s[key].strip(), (s['id'], key))

    def test_model_outcomes_follow_evidence_status(self):
        from intelligence_store.run_record import load_evidence_status
        ev = load_evidence_status()['models']
        p = lenalidomide_path()
        self.assertEqual([m['model_id'] for m in p['models']], list(MODELS))
        hughes = p['models'][0]
        self.assertEqual({r['group'] for r in hughes['outside_results']},
                         set(ev['lenalidomide_hughes_2019']['layers']['external_consistency']['result_by_group']))
        self.assertIn('moderate: model under-predicts', '; '.join(f"{r['group']}: {r['outcome']}" for r in hughes['outside_results']))


class Page(unittest.TestCase):
    def setUp(self):
        from app.app import app
        self.client = app.test_client()

    def test_page(self):
        url = '/landscape/drugs/lenalidomide/guide'
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        for text in (b'1. Clinical trials', b'6. Credibility and review', b'Missing:', b'/models/extraction-review'):
            self.assertIn(text, r.data)
        self.assertEqual(json.loads(self.client.get(url + '?format=json').data)['schema_version'], 'guided-path-v1')
        self.assertEqual(self.client.get(url + '?x=1').status_code, 400)
        self.assertIn(url.encode(), self.client.get('/').data)
        self.assertIn(url.encode(), self.client.get('/landscape/drugs/lenalidomide/dose-optimisation').data)


if __name__ == '__main__':
    unittest.main()
