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






class PatientComparisonReportTests(unittest.TestCase):
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

    def report_response(self,ids):
        return self.client.get(self.compare_path(),query_string={**ids,'format':'report'})

    def payload_from_html(self,text):
        from html.parser import HTMLParser
        class Payload(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=True);self.inside=False;self.parts=[]
            def handle_starttag(self,tag,attrs):
                if tag=='pre' and dict(attrs).get('id')=='comparison-payload':self.inside=True
            def handle_endtag(self,tag):
                if tag=='pre':self.inside=False
            def handle_data(self,data):
                if self.inside:self.parts.append(data)
        parser=Payload();parser.feed(text)
        return json.loads(''.join(parser.parts))

    def test_portable_report_retains_exact_payload_and_both_sources_without_writes_or_rerun(self):
        ids=self.two_scenarios();before=self.table_hashes()
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No solver')), \
             patch('intelligence_store.educational_pk.load_execution_contract',side_effect=AssertionError('No current contract')), \
             patch('requests.get',side_effect=AssertionError('No network')):
            response=self.report_response(ids)
            data=self.client.get(self.compare_path(),query_string={**ids,'format':'json'}).json
        self.assertEqual(response.status_code,200)
        text=response.get_data(as_text=True)
        self.assertEqual(self.payload_from_html(text),data)
        saved=copy.deepcopy(data);sha=saved.pop('report_sha256');self.assertEqual(sha,digest(saved))
        self.assertIn('<svg',text);self.assertIn('stroke-dasharray="6 3"',text)
        self.assertIn(f'Scenario #{self.second.id}',text)
        self.assertIn('Clinical prediction validated: <strong>false</strong>',text)
        self.assertEqual(self.table_hashes(),before)
        self.assertEqual(response.mimetype,'text/html')
        self.assertIn('attachment;',response.headers['Content-Disposition'])
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertIn("default-src 'none'",response.headers['Content-Security-Policy'])
        self.assertNotIn('<script',text);self.assertNotIn('<link',text)
        self.assertNotIn('<form',text);self.assertNotIn('src=',text)
        self.assertIn('format=report',self.client.get(self.compare_path(),query_string=ids).get_data(as_text=True))

    def test_incompatible_report_keeps_decisions_and_withholds_curve_and_deltas(self):
        ids=self.pair(short=True)
        response=self.report_response(ids);text=response.get_data(as_text=True)
        self.assertEqual(response.status_code,200)
        data=self.payload_from_html(text)
        self.assertEqual(data['exposure_comparison']['status'],'comparison_withheld')
        self.assertIsNone(data['exposure_comparison']['points'])
        self.assertIsNone(data['exposure_comparison']['exposure_difference'])
        self.assertNotIn('<svg',text);self.assertNotIn('<polyline',text)
        self.assertIn('Exposure comparison withheld',text)
        self.assertTrue(any(not check['matches'] for check in data['exposure_comparison']['compatibility_checks']))

    def test_untrusted_titles_are_text_and_unknowns_remain_unknown(self):
        ids=self.pair(change_treatment=True)
        text=self.report_response(ids).get_data(as_text=True)
        self.assertIn('&lt;script&gt;Comparison state&lt;/script&gt;',text)
        self.assertNotIn('<script>',text)
        self.assertIn('covariate effect is not isolated',text)
        data=self.payload_from_html(text)
        self.assertTrue(data['treatment_values_changed'])
        unknown=[r for r in data['state_comparison']['fields'] if r['left']['value'] is None]
        self.assertTrue(unknown);self.assertIn('Unknown',text)
        self.assertEqual(data['state_comparison']['right']['title'],'<script>Comparison state</script>')

    def test_missing_foreign_and_corrupt_records_never_export(self):
        self.baseline()
        self.assertEqual(self.client.get(self.compare_path()+'?format=report').status_code,400)
        ids=self.pair()
        self.assertEqual(self.report_response({**ids,'left_run':self.right.id}).status_code,404)
        from intelligence_store.educational_pk_runs import EducationalPKRun
        db.session.execute(update(EducationalPKRun).where(EducationalPKRun.id==self.right.id).values(title='Tampered'))
        db.session.commit();db.session.expire_all()
        self.assertEqual(self.report_response(ids).status_code,409)

if __name__=='__main__':unittest.main()
