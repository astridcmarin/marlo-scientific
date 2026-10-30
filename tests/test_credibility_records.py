"""Phase 6.1: model credibility records (ICH M15 structure)."""
import json
import unittest

from intelligence_store import credibility_records as cr
from intelligence_store.run_record import load_evidence_status


class Records(unittest.TestCase):
    def test_every_registered_model_and_label_curve_has_a_record(self):
        ids = cr.model_ids()
        for model_id in load_evidence_status()['models']:
            self.assertIn(model_id, ids)
        self.assertIn('pomalidomide_label_exposure', ids)
        self.assertIn('dexamethasone_label_exposure', ids)

    def test_structure_and_safety_flags(self):
        for rec in cr.all_records():
            a = rec['assessment']
            for key in ('question_of_interest', 'context_of_use', 'model_influence', 'consequence_of_wrong_decision', 'model_risk', 'model_impact'):
                self.assertIn(key, a)
            self.assertTrue(a['context_of_use']['excluded_uses'])
            self.assertFalse(rec['clinical_prediction_validated'])
            self.assertEqual(len(rec['evaluation']['verification_and_validation']), 4)
            for plan in rec['model_analysis_plans']:
                self.assertTrue(plan['pinned_in_code'], plan['file'])
            for e in rec['source_extracts']:
                self.assertTrue(e['pinned_in_code'], e['file'])

    def test_record_checksum_is_reproducible(self):
        a, b = cr.record('bortezomib_pk_lignet_2022'), cr.record('bortezomib_pk_lignet_2022')
        self.assertEqual(a['record_sha256'], b['record_sha256'])
        self.assertEqual([x['name'] for x in a['alternatives_considered_and_rejected']][-1], 'Iwasaki 2020 target-binding PBPK')

    def test_evidence_is_copied_not_rewritten(self):
        evidence = load_evidence_status()
        rec = cr.record('lenalidomide_hughes_2019')
        layer = rec['evaluation']['verification_and_validation'][3]
        self.assertEqual(layer['summary'], evidence['models']['lenalidomide_hughes_2019']['layers']['external_consistency']['summary'])

    def test_unknown_model(self):
        with self.assertRaises(KeyError):
            cr.record('nope')


class Pages(unittest.TestCase):
    def setUp(self):
        from app.app import app
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_pages(self):
        self.assertIn('Credibility records', self.client.get('/models/credibility').get_data(as_text=True))
        page = self.client.get('/models/bortezomib_pk_lignet_2022/credibility').get_data(as_text=True)
        for text in ('Question of interest', 'Model risk', 'Alternatives considered and rejected', 'Not established'):
            self.assertIn(text, page)
        j = self.client.get('/models/dexamethasone_label_exposure/credibility.json')
        self.assertIn('attachment', j.headers['Content-Disposition'])
        self.assertEqual(json.loads(j.get_data())['schema_version'], 'model-credibility-record-v1')
        self.assertEqual(self.client.get('/models/nope/credibility').status_code, 404)
        self.assertIn('Credibility record', self.client.get('/models/lenalidomide_kim_2026').get_data(as_text=True))
