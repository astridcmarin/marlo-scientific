"""Revision lineage, retries and integrity preserve prior synthetic inputs."""
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
from intelligence_store.patient_state_revisions import PatientStateRevision, save_revision, export_revision


from unittest.mock import patch
from intelligence_store.pk_model_inputs import model_input_example


from intelligence_store.treatment_requests import treatment_request_example






from intelligence_store.educational_pk_runs import EducationalPKRun, save_pk_run, export_pk_run

class EducationalPKRunPageTests(unittest.TestCase):
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
        db.session.execute(delete(EducationalPKRun));db.session.commit()
        if inspect(db.engine).has_table(PatientStateRevision.__tablename__):
            ids=list(db.session.scalars(select(PatientStateRevision.id)
                        .order_by(PatientStateRevision.revision_number.desc())))
            for item in ids:
                db.session.execute(delete(PatientStateRevision).where(PatientStateRevision.id==item))
            db.session.commit()
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def baseline(self,state=None):
        self.scenario=self.save_scenario()
        self.base=state or state_from_scenario(self.scenario.payload['analysis']['report']['profile'])
        self.revision=save_revision(self.scenario.id,self.base,title='Review baseline')
        return self.revision

    def save(self,title='Educational run'):
        return save_pk_run(self.revision.id,model_input_example(),treatment_request_example(),'MM',title=title)

    def path(self,suffix=''):
        return f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{self.revision.id}/pk-runs'+suffix

    def form(self,action='save'):
        import re
        page=self.path().replace('/pk-runs','/educational-pk')
        response=self.client.get(page)
        token=re.search(r'name="form_token" value="([^"]+)"',response.get_data(as_text=True)).group(1)
        return page,{'form_token':token,'action':action,'disease':'MM','title':'UI educational run',
                     'inputs':json.dumps(model_input_example()),'treatment':json.dumps(treatment_request_example())}

    def test_explicit_save_redirect_retry_and_transient_actions(self):
        self.baseline();before=export_revision(self.revision.id)
        for action in ('example','calculate','download'):
            path,data=self.form(action);response=self.client.post(path,data=data)
            self.assertEqual(response.status_code,200)
            self.assertEqual(len(list(db.session.scalars(select(EducationalPKRun)))),0)
        path,data=self.form();response=self.client.post(path,data=data)
        self.assertEqual(response.status_code,303)
        row=db.session.scalar(select(EducationalPKRun));self.assertIn(f'/pk-runs/{row.id}',response.headers['Location'])
        self.assertEqual(self.client.post(path,data=data).headers['Location'],response.headers['Location'])
        self.assertEqual(len(list(db.session.scalars(select(EducationalPKRun)))),1)
        self.assertEqual(export_revision(self.revision.id),before)
        detail=self.client.get(response.headers['Location']).get_data(as_text=True)
        self.assertIn('Archived educational calculation',detail)
        self.assertIn('UI educational run',detail);self.assertIn('1242.861',detail)

    def test_archived_html_json_match_and_never_rerun(self):
        self.baseline();row=self.save('<script>archived</script>');before=export_pk_run(row.id)
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No solver')), \
             patch('intelligence_store.educational_pk_runs.calculate_educational_pk',side_effect=AssertionError('No recalculation')), \
             patch('intelligence_store.educational_pk.load_execution_contract',side_effect=ValueError('Changed model')), \
             patch('socket.socket.connect',side_effect=AssertionError('No network')):
            response=self.client.get(self.path('/'+str(row.id)));self.assertEqual(response.status_code,200)
            text=response.get_data(as_text=True)
            self.assertNotIn('<script>archived</script>',text);self.assertIn('&lt;script&gt;archived&lt;/script&gt;',text)
            self.assertIn('No rerun performed',text);self.assertEqual(text.count('<svg '),2)
            self.assertEqual(text.count('class="nav-item active"'),1)
            response=self.client.get(self.path('/'+str(row.id))+'?format=json')
            self.assertEqual(response.get_json(),before)
            self.assertEqual(response.headers['Cache-Control'],'no-store')
            self.assertEqual(response.headers['X-Content-Type-Options'],'nosniff')
            self.assertIn('attachment;',response.headers['Content-Disposition'])
        self.assertEqual(export_pk_run(row.id),before)

    def test_history_empty_paging_and_strict_ownership(self):
        self.baseline();response=self.client.get(self.path())
        self.assertIn('No saved runs',response.get_data(as_text=True))
        first=self.save('Run 0');report=copy.deepcopy(first.payload['report'])
        with patch('intelligence_store.educational_pk_runs.calculate_educational_pk',return_value=report):
            for i in range(1,26):self.save(f'Run {i}')
        text=self.client.get(self.path()).get_data(as_text=True)
        self.assertIn('26 saved runs',text);self.assertIn('Page 1 of 2',text)
        self.assertEqual(text.count('<tr><td><a href='),25)
        text=self.client.get(self.path()+'?page=2').get_data(as_text=True)
        self.assertEqual(text.count('<tr><td><a href='),1)
        self.assertEqual(self.client.get(self.path()+'?page=3').status_code,404)
        for query in ('?page=0','?page=1&page=2','?extra=x','?page=01'):
            self.assertEqual(self.client.get(self.path()+query).status_code,400)
        for query in ('?format=xml','?format=json&format=html','?extra=x'):
            self.assertEqual(self.client.get(self.path('/'+str(first.id))+query).status_code,400)
        self.assertEqual(self.client.get(self.path('/999')).status_code,404)
        self.assertEqual(self.client.get(self.path('/'+str(first.id)).replace('/revisions/1/','/revisions/999/')).status_code,404)
        self.assertEqual(self.client.post(self.path('/'+str(first.id))).status_code,405)

    def test_blocked_save_invalid_title_and_csrf_do_not_append(self):
        self.baseline();path,data=self.form();data['disease']='UNKNOWN'
        response=self.client.post(path,data=data);self.assertEqual(response.status_code,400)
        self.assertIn('Calculation blocked',response.get_data(as_text=True))
        path,data=self.form();data['title']=''
        self.assertEqual(self.client.post(path,data=data).status_code,400)
        path,data=self.form();data['form_token']='bad'
        self.assertEqual(self.client.post(path,data=data).status_code,403)
        path,data=self.form()
        self.assertEqual(self.client.post(path,data=data,headers={'Origin':'https://foreign.test'}).status_code,403)
        self.assertEqual(len(list(db.session.scalars(select(EducationalPKRun)))),0)

    def test_corrupt_saved_content_fails_html_json_and_history(self):
        self.baseline();row=self.save();payload=copy.deepcopy(row.payload)
        payload['report']['points'][1]['concentration_ng_ml']+=1
        db.session.execute(update(EducationalPKRun).where(EducationalPKRun.id==row.id).values(payload=payload));db.session.commit();db.session.expire_all()
        for path in (self.path(),self.path('/'+str(row.id)),self.path('/'+str(row.id))+'?format=json'):
            response=self.client.get(path);self.assertEqual(response.status_code,409)
            self.assertNotIn('1242.861',response.get_data(as_text=True))
