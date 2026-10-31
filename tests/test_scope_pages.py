"""Phase 2.5c: scope registry, daratumumab scope and the public scope pages."""
import hashlib
import json
import unittest
from pathlib import Path

from intelligence_store import model_scope as ms
from intelligence_store import scope_registry as reg
from intelligence_store.patient_state import example_state

ROOT = Path(__file__).resolve().parent.parent


class Registry(unittest.TestCase):
    def test_every_scope_loads_and_its_evidence_matches(self):
        for entry in reg.all_scopes():
            scope = entry['scope']
            self.assertEqual(scope['model_id'], entry['model_id'])
            self.assertFalse(scope['clinical_prediction_validated'])
            for ref in scope['evidence'].values():
                self.assertEqual(hashlib.sha256((ROOT / ref['file']).read_bytes()).hexdigest(), ref['sha256'], ref['file'])

    def test_daratumumab_tiers_follow_both_checks(self):
        v1 = json.loads((ROOT / 'docs/verification/daratumumab_pk_luo_check_v1.json').read_text())
        v2 = json.loads((ROOT / 'docs/verification/daratumumab_pk_luo_check_v2.json').read_text())
        tiers = {o['id']: o['tier'] for o in reg.scope_for('daratumumab_pk_luo_2021')['scope']['outputs']['supported']}
        for eid in ('sirius_8.cmax', 'gen501_16.cmax'):
            self.assertEqual(v1['classification_by_endpoint'][eid]['across_scenarios'], ['consistent'])
            self.assertEqual(v2['classification_by_endpoint'][eid]['across_scenarios'], ['consistent'])
        self.assertEqual(tiers['typical_peak_first_iv_infusion'], 'externally_checked')
        self.assertNotEqual(v2['classification_by_endpoint']['sirius_8.auc_inf']['across_scenarios'], ['consistent'])
        self.assertEqual(tiers['typical_auc_infinity_first_iv_8_mg_kg'], 'inside_model_data')
        for r in (v1, v2):
            self.assertEqual(r['classification_by_endpoint']['gen501_16.auc_0_7d']['across_scenarios'], ['model_over_predicts'])
        self.assertEqual(tiers['typical_auc_first_week_16_mg_kg'], 'external_check_disagrees')
        self.assertEqual(reg.REGISTRY['daratumumab_pk_luo_2021']['runtime'], None)

    def test_route_tier_by_value(self):
        scope = reg.scope_for('daratumumab_pk_luo_2021')['scope']
        s = example_state()
        s['fields']['albumin'].update(value=38.0, origin='synthetic_input')
        iv = ms.evaluate(scope, s, {'disease_code': 'MM', 'route': 'IV'})
        sc = ms.evaluate(scope, s, {'disease_code': 'MM', 'route': 'SC'})
        route = lambda r: next(x for x in r['rules'] if x['id'] == 'route')
        self.assertEqual(route(iv)['tier'], 'externally_checked')
        self.assertEqual(route(sc)['tier'], 'inside_model_data')
        self.assertEqual(ms.evaluate(scope, s, {'disease_code': 'MM', 'route': 'oral'})['status'], 'out_of_scope')


class Pages(unittest.TestCase):
    def setUp(self):
        from app.app import app
        self.client = app.test_client()

    def test_scope_pages(self):
        for model_id, entry in reg.REGISTRY.items():
            r = self.client.get(f'/models/{model_id}/scope')
            self.assertEqual(r.status_code, 200, model_id)
            self.assertIn(entry['label'].encode(), r.data)
            j = self.client.get(f'/models/{model_id}/scope.json')
            self.assertEqual(json.loads(j.data)['model_id'], model_id)
        self.assertIn(b'Nowhere yet', self.client.get('/models/daratumumab_pk_luo_2021/scope').data)
        self.assertEqual(self.client.get('/models/unknown_model/scope').status_code, 404)

    def test_links_from_index_scorecard_and_record(self):
        index = self.client.get('/models').data
        for model_id in reg.REGISTRY:
            self.assertIn(f'/models/{model_id}/scope'.encode(), index)
        self.assertIn(b'/models/lenalidomide_kim_2026/scope', self.client.get('/models/lenalidomide_kim_2026').data)
        self.assertIn(b'/models/lenalidomide_hughes_2019/scope', self.client.get('/models/lenalidomide_hughes_2019/credibility').data)
        self.assertNotIn(b'/scope"', self.client.get('/models/bortezomib_pk_lignet_2022').data)


if __name__ == '__main__':
    unittest.main()
