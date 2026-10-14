import unittest
from unittest.mock import patch
from flask import Flask
from intelligence_store import drug_research_tools as registry
from intelligence_store.drug_capabilities import capability_inventory
from landscape_ui import register_landscape

class ResearchToolTests(unittest.TestCase):
    def setUp(self):
        app=Flask(__name__);app.config['TESTING']=True;app.add_url_rule('/','home',lambda:'Home');register_landscape(app)
        self.app=app;self.client=app.test_client();self.path='/landscape/patient-lab/model-library'
    def test_inventory_has_research_tools_without_efficacy_promotion(self):
        r=capability_inventory()
        self.assertEqual(r['counts']['efficacy_models'],0);self.assertEqual(r['counts']['toxicity_models'],0)
        self.assertEqual(r['counts']['educational_exposure_models'],1)
        self.assertEqual(r['research_tool_counts'],{'target_activity':1,'research_timecourse':1,'assumption_experiment':1,'evidence_review':2})
        b=next(x for x in r['entries'] if x['entity_id']=='bortezomib')
        self.assertEqual(len(b['research_tools']),6);self.assertIsNone(b['exposure_model'])
        for t in b['research_tools']:
            self.assertFalse(t['clinical_prediction_validated']);self.assertFalse(t['ready_for_patient_simulation'])
            self.assertEqual(t['scientific_status'],'review_required')
    def test_inventory_does_not_execute_calculations_or_network(self):
        with patch('intelligence_store.bortezomib_timecourse.build_timecourse',side_effect=AssertionError('solver called')), \
             patch('intelligence_store.bortezomib_proteasome.calculate_proteasome_activity',side_effect=AssertionError('PD called')), \
             patch('intelligence_store.bortezomib_assumption_sensitivity.build_assumption_sensitivity',side_effect=AssertionError('sensitivity called')), \
             patch('requests.get',side_effect=AssertionError('network')):
            self.assertEqual(self.client.get(self.path).status_code,200)
            self.assertEqual(self.client.get('/landscape/simulation-lab').status_code,200)
    def test_filters_search_and_export(self):
        for kind in ['target_activity','research_timecourse','assumption_experiment']:
            data=self.client.get(self.path,query_string={'q':'bortezomib','capability':kind,'format':'json'}).json
            self.assertEqual(data['selection']['entity_ids'],['bortezomib'])
            self.assertEqual(len(data['inventory']['entries']),9)
            self.assertEqual(self.client.get(self.path,query_string={'q':'lenalidomide','capability':kind,'format':'json'}).json['selection']['entity_ids'],[])
    def test_pk_failure_withholds_only_dependent_tools(self):
        with patch.object(registry,'load_pk',side_effect=ValueError('changed')):
            tools=registry.research_tool_registry()['bortezomib']
            self.assertEqual([t['availability'] for t in tools],['available','unavailable','unavailable','available','available','available'])
            self.assertEqual(self.client.get(self.path+'?capability=research_timecourse&format=json').json['selection']['entity_ids'],[])
            body=self.client.get(self.path+'?q=bortezomib').get_data(as_text=True)
            self.assertIn('tool link withheld',body)
            self.assertNotIn('href="/landscape/simulation-lab/bortezomib-timecourse"',body)
    def test_pd_failure_does_not_hide_lenalidomide_or_drug_references(self):
        with patch.object(registry,'load_pd',side_effect=ValueError('changed')):
            r=capability_inventory()
            self.assertTrue(all(n==0 for n in r['research_tool_counts'].values()))
            self.assertEqual(r['counts']['educational_exposure_models'],1)
            self.assertEqual(len(r['entries']),9)
    def test_evidence_failure_not_reported_as_missing_model(self):
        with patch.object(registry,'_pinned',return_value=False):
            tools=registry.research_tool_registry()['bortezomib']
            self.assertEqual([t['availability'] for t in tools],['available','available','available','unavailable','unavailable','unavailable'])
    def test_links_resolve_and_simulation_directory_lists_all(self):
        endpoints={r.endpoint for r in self.app.url_map.iter_rules()}
        body=self.client.get('/landscape/simulation-lab').get_data(as_text=True)
        with self.app.test_request_context():
            from flask import url_for
            for t in registry.research_tool_registry()['bortezomib']:
                self.assertIn(t['endpoint'],endpoints);self.assertIn(url_for(t['endpoint']),body)
        self.assertEqual(body.count('class="nav-item active"'),1)
        self.assertEqual(self.client.get(self.path+'?capability=prescribing').status_code,400)
if __name__=='__main__':unittest.main()
