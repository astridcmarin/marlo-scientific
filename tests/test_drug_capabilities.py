import unittest
from unittest.mock import patch
from flask import Flask
from landscape_ui import register_landscape
from intelligence_store import drug_capabilities as capabilities


class DrugCapabilitiesTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.add_url_rule('/', 'home', lambda:'Home')
        register_landscape(app)
        self.client = app.test_client()
        self.path = '/landscape/patient-lab/model-library'

    def test_inventory_tracks_installed_entities_without_promoting_references(self):
        report = capabilities.capability_inventory()
        self.assertEqual(report['counts'], {'drug_entities':9,'educational_exposure_models':1,
                                           'efficacy_models':0,'toxicity_models':0})
        for row in report['entries']:
            self.assertEqual(row['capabilities']['efficacy']['status'],'not_registered')
            self.assertEqual(row['capabilities']['toxicity']['status'],'not_registered')
            if row['entity_id'] != 'lenalidomide':
                self.assertIsNone(row['exposure_model'])
        lena = next(r for r in report['entries'] if r['entity_id']=='lenalidomide')
        self.assertEqual(sum(c['subject_count'] for c in lena['exposure_model']['source_populations']),125)
        self.assertEqual(set(lena['exposure_model']['covariates']),{'creatinine_clearance','fat_free_mass'})
        self.assertFalse(report['clinical_prediction_validated'])
        self.assertEqual(report,capabilities.capability_inventory())

    def test_render_search_export_do_not_access_network_or_calculate(self):
        with patch('requests.get',side_effect=AssertionError('no network')), \
             patch('intelligence_store.educational_pk.calculate_educational_pk',side_effect=AssertionError('no calculation')):
            response = self.client.get(self.path+'?q=revlimid')
            data = self.client.get(self.path+'?q=revlimid&format=json').json
        self.assertEqual(response.status_code,200)
        body = response.get_data(as_text=True)
        self.assertIn('Lenalidomide educational PK',body)
        self.assertNotIn('<h2>Bortezomib</h2>',body)
        self.assertEqual(body.count('class="nav-item active"'),1)
        self.assertEqual(data['selection']['entity_ids'],['lenalidomide'])
        self.assertEqual(len(data['inventory']['entries']),9)
        self.assertEqual(response.headers['Cache-Control'],'no-store')

    def test_unavailable_reference_is_not_reported_as_absent(self):
        with patch.object(capabilities,'load_safety_catalog',side_effect=ValueError('invalid')):
            report = capabilities.capability_inventory()
        self.assertTrue(all(r['capabilities']['safety']['status']=='unavailable' for r in report['entries']))
        self.assertEqual(report['warnings'][0]['area'],'safety')
        self.assertEqual(report['counts']['educational_exposure_models'],1)

    def test_invalid_model_contract_withholds_model_only(self):
        with patch.object(capabilities,'load_execution_contract',side_effect=ValueError('invalid')):
            data = self.client.get(self.path+'?format=json').json['inventory']
        self.assertEqual(data['counts']['educational_exposure_models'],0)
        lena = next(r for r in data['entries'] if r['entity_id']=='lenalidomide')
        self.assertEqual(lena['capabilities']['exposure']['status'],'unavailable')
        self.assertIsNone(lena['exposure_model'])
        self.assertEqual(lena['capabilities']['safety']['status'],'curated_reference')

    def test_identity_failure_withholds_inventory(self):
        with patch.object(capabilities,'load_alias_catalog',side_effect=ValueError('invalid')):
            self.assertEqual(self.client.get(self.path).status_code,503)

    def test_capability_filters_and_empty_results_are_explicit(self):
        for value in ('efficacy','toxicity'):
            body = self.client.get(self.path+'?capability='+value).get_data(as_text=True)
            self.assertIn('No matching installed capability',body)
            self.assertIn('Generic Simulation Lab experiments do not fill this gap.',body)
        data = self.client.get(self.path+'?capability=exposure&format=json').json
        self.assertEqual(data['selection']['entity_ids'],['lenalidomide'])

    def test_invalid_inputs_mutation_and_unescaped_search_are_rejected(self):
        for query in ('q='+('x'*121),'format=pdf','capability=clinical','q=a&q=b','patient_id=1','cohort_id=4'):
            self.assertEqual(self.client.get(self.path+'?'+query).status_code,400)
        self.assertEqual(self.client.post(self.path).status_code,405)
        body = self.client.get(self.path,query_string={'q':'<script>x</script>'}).get_data(as_text=True)
        self.assertNotIn('<script>x</script>',body)
        self.assertIn('&lt;script&gt;x&lt;/script&gt;',body)


if __name__=='__main__': unittest.main()
