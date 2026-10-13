"""Integration checks for the unified, read-only Patient Lab workspace."""
import copy
import json
import unittest
from sqlalchemy import select, update, delete, inspect
from flask import Flask
from datetime import datetime
from intelligence_store.models import AnalysisCohort, CohortTrial, TrialSnapshot
from intelligence_store.patient_scenarios import load_scenario_presets
from intelligence_store.saved_scenarios import analyze_for_save, save_scenario
from intelligence_store.extensions import db
from intelligence_store.patient_state import digest, state_from_scenario
from intelligence_store.patient_state_revisions import PatientStateRevision, save_revision


from unittest.mock import patch
from intelligence_store.pk_model_inputs import model_input_example


from intelligence_store.treatment_requests import treatment_request_example






class TwoScenarioPatientCompareTests(unittest.TestCase):
    def setUp(self):
            app = Flask(__name__)
            app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite://', INTELLIGENCE_WORKSPACE_SECRET='web-test-secret-40')
            app.add_url_rule('/', 'home', lambda: 'Home')
            from landscape_ui import register_landscape
            register_landscape(app)
            self.app=app
            self.client=app.test_client()
            db.init_app(app)
            self.context = app.app_context()
            self.context.push()
            db.create_all()
            db.session.add(AnalysisCohort(id=1, condition='Synthetic example',
                api_url='https://clinicaltrials.gov/api/v2/studies', query_params={'query.cond': 'Example'},
                query_version='qa-v1', normalization_version='qa-v1', scope='all-studies',
                max_pages=1, status='COMPLETE', expected_count=1, retrieved_count=1,
                pages_fetched=1, page_log=[], finished_at_utc=datetime(2026, 10, 7)))
            raw = {'protocolSection': {
                'identificationModule': {'nctId': 'NCT00000001', 'briefTitle': 'Frozen title'},
                'statusModule': {'overallStatus': 'RECRUITING'},
                'designModule': {'studyType': 'INTERVENTIONAL'},
                'armsInterventionsModule': {'interventions': [{'type': 'DRUG', 'name': 'Lenalidomide'}]},
                'eligibilityModule': {'minimumAge': '18 Years', 'maximumAge': '80 Years', 'sex': 'ALL'}}}
            snap = TrialSnapshot(nct_id='NCT00000001', source_url='https://clinicaltrials.gov/study/NCT00000001', raw_study=raw)
            db.session.add(snap)
            db.session.flush()
            self.snapshot_id = snap.id
            db.session.add(CohortTrial(cohort_id=1, nct_id=snap.nct_id, snapshot_id=snap.id))
            db.session.commit()
            self.profile = load_scenario_presets()['index']['interaction-reference']['profile']
            self.analysis = analyze_for_save(1, self.profile)
            self.profile = self.analysis['report']['profile']

    def save_scenario(self, key='a'):
            return save_scenario('Invented profile', 1, self.profile, digest(self.analysis), key*64)

    def tearDown(self):
        # Explicit test-only cleanup, descendants first. SQLite DROP TABLE
        # otherwise conflicts with the intentional self-FK RESTRICT links.
        db.session.rollback()
        from intelligence_store.educational_pk_runs import EducationalPKRun
        db.session.execute(delete(EducationalPKRun));db.session.commit()
        if inspect(db.engine).has_table(PatientStateRevision.__tablename__):
            ids=list(db.session.scalars(select(PatientStateRevision.id)
                        .order_by(PatientStateRevision.revision_number.desc())))
            for item in ids:
                db.session.execute(delete(PatientStateRevision).where(PatientStateRevision.id==item))
            db.session.commit()
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def baseline(self,state=None):
        self.scenario=self.save_scenario()
        self.base=state or state_from_scenario(self.scenario.payload['analysis']['report']['profile'])
        self.revision=save_revision(self.scenario.id,self.base,title='Review baseline')
        return self.revision

    def page(self):
        return f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{self.revision.id}/educational-pk'

    def form(self,action='calculate',disease='MM'):
        import re
        response=self.client.get(self.page())
        token=re.search(r'name="form_token" value="([^"]+)"',response.get_data(as_text=True)).group(1)
        return {'form_token':token,'action':action,'disease':disease,
                'inputs':json.dumps(model_input_example()),'treatment':json.dumps(treatment_request_example())}

    def overview(self,scenario_id=None,revision_id=None):
        return f'/landscape/workspace/scenarios/{scenario_id or self.scenario.id}/patient-state/revisions/{revision_id or self.revision.id}/patient-lab-overview'

    def table_hashes(self):
        return {table.name:digest(json.loads(json.dumps([dict(row) for row in db.session.execute(select(table)).mappings()],default=str)))
            for table in db.metadata.sorted_tables}

    def compare_path(self):
        return f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/exposure-compare'

    def pair(self, change_inputs=True, change_treatment=False, short=False):
        from intelligence_store.educational_pk_runs import save_pk_run
        self.baseline()
        state=copy.deepcopy(self.base)
        state['fields']['weight']={'value':80.0,'unit':'kg','origin':'synthetic_input','source_ref':None,'observed_at':None}
        self.other=save_revision(self.scenario.id,state,title='<script>Comparison state</script>',parent_revision_id=self.revision.id)
        self.left=save_pk_run(self.revision.id,model_input_example(),treatment_request_example(),'MM',title='Left archive')
        inputs=model_input_example()
        if change_inputs:inputs['fields']['creatinine_clearance']['value']=45
        treatment=treatment_request_example()
        if change_treatment:
            for event in treatment['events']:event['amount']['value']=15
        if short:treatment['horizon']['value']=48
        self.right=save_pk_run(self.other.id,inputs,treatment,'MM',title='Right archive')
        return {'left_revision':self.revision.id,'right_revision':self.other.id,'left_run':self.left.id,'right_run':self.right.id}

    def test_cross_revision_curve_export_deltas_hashes_and_no_writes_or_solver(self):
        ids=self.pair();before=self.table_hashes()
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No solver')), \
             patch('intelligence_store.educational_pk.load_execution_contract',side_effect=AssertionError('No current contract')), \
             patch('requests.get',side_effect=AssertionError('No network')):
            page=self.client.get(self.compare_path(),query_string=ids)
            data=self.client.get(self.compare_path(),query_string={**ids,'format':'json'}).json
        self.assertEqual(page.status_code,200)
        self.assertEqual(data['state_comparison']['right']['revision_id'],self.other.id)
        exposure=data['exposure_comparison']
        self.assertEqual(exposure['status'],'compatible_educational_comparison')
        self.assertEqual(exposure['left_revision_id'],self.revision.id)
        self.assertEqual(exposure['right_revision_id'],self.other.id)
        self.assertAlmostEqual(exposure['exposure_difference']['auc_right_minus_left_ng_h_ml'],
            self.right.payload['report']['auc_0_horizon_ng_h_ml']-self.left.payload['report']['auc_0_horizon_ng_h_ml'])
        saved=copy.deepcopy(data);sha=saved.pop('report_sha256');self.assertEqual(sha,digest(saved))
        self.assertFalse(data['model_rerun']);self.assertFalse(data['clinical_prediction_validated'])
        self.assertEqual(self.table_hashes(),before)
        text=page.get_data(as_text=True)
        self.assertIn('stroke-dasharray="6 3"',text)
        self.assertIn('&lt;script&gt;Comparison state&lt;/script&gt;',text)
        self.assertNotIn('<script>Comparison state</script>',text)
        self.assertEqual(text.count('class="nav-item active"'),1)
        self.assertEqual(page.headers['Cache-Control'],'no-store')
        self.assertEqual(page.headers['X-Content-Type-Options'],'nosniff')

    def test_state_changes_do_not_silently_change_model_inputs(self):
        ids=self.pair(change_inputs=False)
        response=self.client.get(self.compare_path(),query_string={**ids,'format':'json'})
        data=response.json
        self.assertIn('Patient-state changes alone',data['context'])
        self.assertEqual(data['exposure_comparison']['exposure_difference']['auc_right_minus_left_ng_h_ml'],0)
        self.assertIn('weight',[r['field'] for r in data['state_comparison']['fields'] if r['category']=='value_changed'])

    def test_changed_treatment_is_not_attributed_to_patient_state(self):
        ids=self.pair(change_treatment=True)
        data=self.client.get(self.compare_path(),query_string={**ids,'format':'json'}).json
        self.assertTrue(data['treatment_values_changed'])
        self.assertIn('covariate effect is not isolated',data['context'])

    def test_different_time_grid_withholds_overlay_and_numeric_differences(self):
        ids=self.pair(short=True)
        page=self.client.get(self.compare_path(),query_string=ids)
        data=self.client.get(self.compare_path(),query_string={**ids,'format':'json'}).json
        self.assertEqual(data['exposure_comparison']['status'],'comparison_withheld')
        self.assertIsNone(data['exposure_comparison']['points'])
        self.assertIsNone(data['exposure_comparison']['exposure_difference'])
        self.assertIn('Exposure comparison withheld',page.get_data(as_text=True))
        self.assertNotIn('<polyline',page.get_data(as_text=True))

    def test_wrong_run_ownership_and_corrupt_payload_are_rejected(self):
        ids=self.pair()
        bad={**ids,'left_run':self.right.id}
        self.assertEqual(self.client.get(self.compare_path(),query_string=bad).status_code,404)
        from intelligence_store.educational_pk_runs import EducationalPKRun
        db.session.execute(update(EducationalPKRun).where(EducationalPKRun.id==self.right.id).values(title='Tampered'))
        db.session.commit();db.session.expire_all()
        self.assertEqual(self.client.get(self.compare_path(),query_string=ids).status_code,409)

    def test_one_revision_and_missing_run_have_actionable_empty_states(self):
        self.baseline()
        page=self.client.get(self.compare_path())
        self.assertEqual(page.status_code,200)
        self.assertIn('Two saved patient revisions are needed',page.get_data(as_text=True))
        save_revision(self.scenario.id,self.base,title='Other',parent_revision_id=self.revision.id)
        text=self.client.get(self.compare_path()).get_data(as_text=True)
        self.assertIn('Create and save an educational run',text)
        self.assertNotIn('<polyline',text)
        self.assertEqual(self.client.get(self.compare_path()+'?format=json').status_code,400)

    def test_invalid_queries_foreign_revision_and_post_are_rejected(self):
        self.baseline()
        for query in ['left_revision=-1','left_run=abc','left_run=1&left_run=1','dose=25','format=csv']:
            self.assertEqual(self.client.get(self.compare_path()+'?'+query).status_code,400)
        self.assertEqual(self.client.get(self.compare_path()+'?left_revision=999').status_code,404)
        self.assertEqual(self.client.post(self.compare_path()).status_code,405)
        foreign=self.save_scenario('b')
        revision=save_revision(foreign.id,self.base,title='Foreign')
        self.assertEqual(self.client.get(self.compare_path(),query_string={'left_revision':revision.id}).status_code,404)

    def test_defaults_workspace_link_and_existing_same_revision_contract(self):
        self.pair()
        page=self.client.get(self.compare_path())
        self.assertEqual(page.status_code,200)
        self.assertIn(f'Left: record #{self.revision.id}, run #{self.left.id}',page.get_data(as_text=True))
        text=self.client.get(self.overview()).get_data(as_text=True)
        self.assertIn('Compare patient states and exposure',text)
        from intelligence_store.educational_pk_comparison import compare_pk_runs
        same=compare_pk_runs(self.left.id,self.left.id,revision_id=self.revision.id)
        self.assertEqual(same['schema_version'],'educational-pk-comparison-v1')
        self.assertEqual(same['exposure_difference']['auc_right_minus_left_ng_h_ml'],0)
        with self.assertRaises(ValueError):compare_pk_runs(self.left.id,self.right.id,revision_id=self.revision.id)

    def two_scenarios(self):
        from intelligence_store.educational_pk_runs import save_pk_run
        self.baseline()
        self.second=self.save_scenario('b')
        state=copy.deepcopy(self.base)
        state['fields']['age_years']['value']=75.0
        self.other=save_revision(self.second.id,state,title='Separate synthetic patient')
        self.left=save_pk_run(self.revision.id,model_input_example(),treatment_request_example(),'MM',title='Scenario one')
        inputs=model_input_example();inputs['fields']['creatinine_clearance']['value']=45
        self.right=save_pk_run(self.other.id,inputs,treatment_request_example(),'MM',title='Scenario two')
        return {'right_scenario':self.second.id,'left_revision':self.revision.id,'right_revision':self.other.id,'left_run':self.left.id,'right_run':self.right.id}

    def test_distinct_scenarios_preserve_both_sources_and_correct_navigation(self):
        ids=self.two_scenarios();before=self.table_hashes()
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No solver')):
            response=self.client.get(self.compare_path(),query_string=ids)
            data=self.client.get(self.compare_path(),query_string={**ids,'format':'json'}).json
        self.assertEqual(response.status_code,200)
        self.assertEqual(data['scenario_sources']['left']['scenario_id'],self.scenario.id)
        self.assertEqual(data['scenario_sources']['right']['scenario_id'],self.second.id)
        self.assertEqual(data['scenario_sources']['left']['payload_sha256'],self.scenario.payload_sha256)
        self.assertEqual(data['scenario_sources']['right']['payload_sha256'],self.second.payload_sha256)
        self.assertEqual(data['state_comparison']['right_scenario_payload_sha256'],self.second.payload_sha256)
        self.assertEqual(data['exposure_comparison']['status'],'compatible_educational_comparison')
        text=response.get_data(as_text=True)
        self.assertIn(f'/scenarios/{self.second.id}/patient-state/revisions/{self.other.id}/pk-runs/{self.right.id}',text)
        self.assertIn('right_scenario=',text)
        self.assertIn('study counts are not pooled',text)
        self.assertEqual(self.table_hashes(),before)

    def test_new_scenario_selection_resets_to_its_own_latest_state_and_run(self):
        ids=self.two_scenarios()
        data=self.client.get(self.compare_path(),query_string={'right_scenario':self.second.id,'format':'json'}).json
        self.assertEqual(data['state_comparison']['right']['revision_id'],self.other.id)
        self.assertEqual(data['exposure_comparison']['right']['run_id'],self.right.id)
        stale={**ids,'right_revision':self.revision.id}
        self.assertEqual(self.client.get(self.compare_path(),query_string=stale).status_code,404)
        self.assertEqual(self.client.get(self.compare_path()+'?right_scenario=999').status_code,404)
        self.assertEqual(self.client.get(self.compare_path()+'?right_scenario=-1').status_code,400)

    def test_scenario_without_state_and_corrupt_selected_scenario(self):
        self.baseline();self.second=self.save_scenario('b')
        response=self.client.get(self.compare_path(),query_string={'right_scenario':self.second.id})
        self.assertEqual(response.status_code,200)
        self.assertIn('Create its baseline patient state',response.get_data(as_text=True))
        from intelligence_store.saved_scenarios import SavedPatientScenario
        db.session.execute(update(SavedPatientScenario).where(SavedPatientScenario.id==self.second.id).values(title='Tampered scenario'))
        db.session.commit();db.session.expire_all()
        self.assertEqual(self.client.get(self.compare_path(),query_string={'right_scenario':self.second.id}).status_code,409)

    def test_original_state_comparison_keeps_same_scenario_scope_and_hash(self):
        self.two_scenarios()
        from intelligence_store.patient_state_comparison import compare_revisions
        with self.assertRaises(ValueError):compare_revisions(self.revision.id,self.other.id)
        state=compare_revisions(self.revision.id,self.revision.id,scenario_id=self.scenario.id)
        self.assertEqual(state['schema_version'],'patient-state-comparison-v1')
        self.assertEqual(state['scenario_payload_sha256'],self.scenario.payload_sha256)
        sha=state.pop('report_sha256');self.assertEqual(digest(state),sha)
        self.assertEqual(state['counts']['unchanged'],state['field_count'])


if __name__=='__main__':unittest.main()
