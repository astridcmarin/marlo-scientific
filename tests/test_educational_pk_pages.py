"""Revision lineage, retries and integrity preserve prior synthetic inputs."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from sqlalchemy import select, update, delete, inspect
from sqlalchemy.exc import IntegrityError
from flask import Flask, current_app
from datetime import datetime
from intelligence_store.models import AnalysisCohort, CohortTrial, TrialSnapshot
from intelligence_store.patient_scenarios import load_scenario_presets
from intelligence_store.saved_scenarios import analyze_for_save, save_scenario
from intelligence_store.extensions import db
from intelligence_store.patient_state import example_state, digest, state_from_scenario
from intelligence_store.patient_state_revisions import (PatientStateRevision, save_revision,
    read_revision, export_revision, register_patient_state_revision_commands)
from intelligence_store.validation import validate_platform


from unittest.mock import patch
from intelligence_store.pk_model_inputs import model_input_example
from intelligence_store.patient_model_binding import review_model_binding, register_patient_model_binding_commands


from intelligence_store.treatment_requests import (treatment_request_example,validate_treatment_request,
    treatment_request_preview,review_patient_treatment,register_treatment_request_commands)


from intelligence_store.model_coverage import (review_model_coverage,load_coverage_contract,register_model_coverage_commands)


from intelligence_store.educational_pk import (calculate_educational_pk,load_execution_contract,register_educational_pk_commands)
import math


class EducationalPKPageTests(unittest.TestCase):
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

    def page(self):
        return f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{self.revision.id}/educational-pk'

    def form(self,action='calculate',disease='MM'):
        import re
        response=self.client.get(self.page())
        token=re.search(r'name="form_token" value="([^"]+)"',response.get_data(as_text=True)).group(1)
        return {'form_token':token,'action':action,'disease':disease,
                'inputs':json.dumps(model_input_example()),'treatment':json.dumps(treatment_request_example())}

    def test_get_and_example_do_not_execute_and_never_infer_disease(self):
        self.baseline()
        with patch('landscape_ui.educational_pk_pages.calculate_educational_pk',side_effect=AssertionError('Unexpected run')):
            r=self.client.get(self.page());self.assertEqual(r.status_code,200)
            self.assertIn('Clinical prediction is unvalidated',r.get_data(as_text=True))
            self.assertIn('name="inputs" rows="16" style="width:100%;box-sizing:border-box"></textarea>',r.get_data(as_text=True))
            r=self.client.post(self.page(),data=self.form('example','UNKNOWN'))
            self.assertEqual(r.status_code,200);self.assertIn('hughes-model-inputs-v1',r.get_data(as_text=True))
            self.assertNotIn('Educational calculation completed',r.get_data(as_text=True))
            self.assertIn('value="UNKNOWN" selected',r.get_data(as_text=True))

    def test_html_json_and_dynamic_axis_match_backend_without_database_changes(self):
        self.baseline()
        before=export_revision(self.revision.id)
        from landscape_ui.educational_pk_pages import _charts
        expected=calculate_educational_pk(self.revision.id,model_input_example(),treatment_request_example(),'MM')
        chart=_charts(expected)[0]
        self.assertEqual([t['label'] for t in chart['time_ticks']],['0','18','36','54','72'])
        with patch('socket.socket.connect',side_effect=AssertionError('No network')):
            response=self.client.post(self.page(),data=self.form())
            self.assertEqual(response.status_code,200)
            text=response.get_data(as_text=True)
            self.assertIn('Educational calculation completed',text);self.assertIn('1242.861',text)
            self.assertEqual(text.count('<svg '),2)
            response=self.client.post(self.page(),data=self.form('download'))
            self.assertEqual(response.get_json(),expected)
            self.assertEqual(response.headers['Cache-Control'],'no-store')
            self.assertIn('attachment;',response.headers['Content-Disposition'])
        self.assertEqual(export_revision(self.revision.id),before)
        self.assertEqual(len(list(db.session.scalars(select(PatientStateRevision)))),1)
        detail=self.client.get(f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{self.revision.id}')
        self.assertIn('Open educational PK calculation',detail.get_data(as_text=True))

    def test_blocked_scope_has_no_curve_and_preserves_declared_context(self):
        self.baseline()
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('Blocked solver')):
            response=self.client.post(self.page(),data=self.form(disease='UNKNOWN'))
            self.assertEqual(response.status_code,200)
            self.assertIn('Calculation blocked',response.get_data(as_text=True))
            self.assertNotIn('<svg ',response.get_data(as_text=True))
            response=self.client.post(self.page(),data=self.form('download','UNKNOWN'))
            self.assertEqual(response.get_json()['simulation_status'],'not_run')

    def test_invalid_json_duplicate_keys_and_escaping(self):
        self.baseline()
        for bad in ['{','{"a":1,"a":2}','NaN','x'*65537]:
            form=self.form();form['inputs']=bad
            with patch('landscape_ui.educational_pk_pages.calculate_educational_pk',side_effect=AssertionError('Invalid input ran')):
                r=self.client.post(self.page(),data=form);self.assertEqual(r.status_code,400)
        form=self.form();form['inputs']='<script>alert(1)</script>'
        r=self.client.post(self.page(),data=form)
        self.assertNotIn('<script>alert(1)</script>',r.get_data(as_text=True))
        self.assertIn('&lt;script&gt;',r.get_data(as_text=True))

    def test_csrf_context_and_strict_forms(self):
        self.baseline()
        r=self.client.post(self.page(),data={**self.form(),'form_token':'bad'})
        self.assertEqual(r.status_code,403)
        self.assertEqual(self.client.post(self.page(),data=self.form(),headers={'Origin':'https://foreign.test'}).status_code,403)
        self.assertEqual(self.client.get(self.page()+'?format=json').status_code,400)
        self.assertEqual(self.client.post(self.page(),data={**self.form(),'extra':'x'}).status_code,400)
        self.assertEqual(self.client.post(self.page(),data={**self.form(),'action':'unknown'}).status_code,400)
        self.assertEqual(self.client.get(self.page().replace('/scenarios/1/','/scenarios/99/')).status_code,404)
        self.assertEqual(self.client.post(self.page(),data='x'*160001,content_type='application/x-www-form-urlencoded').status_code,413)
