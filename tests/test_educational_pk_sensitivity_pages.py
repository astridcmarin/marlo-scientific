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


class EducationalPKSensitivityPageTests(unittest.TestCase):
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

    def source_run(self):
        self.baseline()
        from intelligence_store.educational_pk_runs import save_pk_run
        self.run=save_pk_run(self.revision.id,model_input_example(),treatment_request_example(),'MM',title='Sensitivity page source')
        return self.run

    def sensitivity_path(self):
        return f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{self.revision.id}/pk-runs/{self.run.id}/sensitivity'

    def sensitivity_form(self,action='calculate',**changes):
        import re
        page=self.client.get(self.sensitivity_path())
        token=re.search(r'name="form_token" value="([^\"]+)"',page.get_data(as_text=True)).group(1)
        data=dict(form_token=token,action=action,clearance_factor='0.8',assumption_note='Invented web sensitivity, no physiology inferred.')
        data.update(changes)
        return data

    def hashes(self):
        return {t.name:digest(json.loads(json.dumps([dict(row) for row in db.session.execute(select(t)).mappings()],default=str))) for t in db.metadata.sorted_tables}

    def test_get_is_blank_and_never_calculates(self):
        self.source_run();before=self.hashes()
        with patch('landscape_ui.educational_pk_sensitivity_pages.clearance_sensitivity',side_effect=AssertionError('No automatic sensitivity')):
            page=self.client.get(self.sensitivity_path())
        self.assertEqual(page.status_code,200)
        text=page.get_data(as_text=True)
        self.assertIn('name="clearance_factor" inputmode="decimal" maxlength="40" required value=""',text)
        self.assertNotIn('<svg ',text)
        self.assertEqual(text.count('class="nav-item active"'),1)
        self.assertEqual(page.headers['Cache-Control'],'no-store')
        self.assertEqual(self.hashes(),before)

    def test_overlay_and_download_match_backend_without_writes_or_ode(self):
        self.source_run();before=self.hashes()
        from intelligence_store.educational_pk_sensitivity import clearance_sensitivity
        expected=clearance_sensitivity(self.run.id,0.8,'Invented web sensitivity, no physiology inferred.')
        from landscape_ui.educational_pk_sensitivity_pages import sensitivity_charts
        charts=sensitivity_charts(expected)
        self.assertEqual([t['label'] for t in charts[0]['time_ticks']],['0','18','36','54','72'])
        self.assertEqual(len(charts[0]['series']),2)
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No ODE')),             patch('socket.socket.connect',side_effect=AssertionError('No network')):
            page=self.client.post(self.sensitivity_path(),data=self.sensitivity_form())
            self.assertEqual(page.status_code,200)
            text=page.get_data(as_text=True)
            self.assertEqual(text.count('<svg '),2)
            self.assertIn('Sensitivity calculated',text)
            self.assertIn('stroke-dasharray="6 3"',text)
            self.assertIn('1.25',text)
            downloaded=self.client.post(self.sensitivity_path(),data=self.sensitivity_form('download'))
        self.assertEqual(downloaded.get_json(),expected)
        self.assertEqual(downloaded.headers['Cache-Control'],'no-store')
        self.assertEqual(downloaded.headers['X-Content-Type-Options'],'nosniff')
        self.assertIn('attachment;',downloaded.headers['Content-Disposition'])
        self.assertEqual(self.hashes(),before)
        archived=self.client.get(self.sensitivity_path().removesuffix('/sensitivity'))
        self.assertIn('Explore invented clearance sensitivity',archived.get_data(as_text=True))

    def test_invalid_inputs_preserve_text_and_escape_notes(self):
        self.source_run()
        for factor in ('NaN','inf','','0.49','2.01','1e0'):
            response=self.client.post(self.sensitivity_path(),data=self.sensitivity_form(clearance_factor=factor))
            self.assertEqual(response.status_code,400)
            self.assertNotIn('<svg ',response.get_data(as_text=True))
        response=self.client.post(self.sensitivity_path(),data=self.sensitivity_form(assumption_note=' '))
        self.assertEqual(response.status_code,400)
        response=self.client.post(self.sensitivity_path(),data=self.sensitivity_form(assumption_note='<script>invented</script>'))
        text=response.get_data(as_text=True)
        self.assertEqual(response.status_code,200)
        self.assertIn('&lt;script&gt;invented&lt;/script&gt;',text)
        self.assertNotIn('<script>invented</script>',text)

    def test_context_queries_csrf_and_form_shape(self):
        from werkzeug.datastructures import MultiDict
        self.source_run();path=self.sensitivity_path()
        self.assertEqual(self.client.get(path+'?format=json').status_code,400)
        self.assertEqual(self.client.get(path.replace(f'/pk-runs/{self.run.id}/','/pk-runs/999/')).status_code,404)
        other=save_revision(self.scenario.id,self.base,parent_revision_id=self.revision.id,title='Other record')
        self.assertEqual(self.client.get(path.replace(f'/revisions/{self.revision.id}/',f'/revisions/{other.id}/')).status_code,404)
        data=self.sensitivity_form()
        self.assertEqual(self.client.post(path,data=dict(data,form_token='bad')).status_code,403)
        self.assertEqual(self.client.post(path,data=data,headers={'Origin':'https://example.invalid'}).status_code,403)
        self.assertEqual(self.client.post(path,data=dict(data,extra='x')).status_code,400)
        self.assertEqual(self.client.post(path,data=dict(data,action='save')).status_code,400)
        self.assertEqual(self.client.post(path,data=dict(data,assumption_note='x'*21000)).status_code,413)
        duplicate=MultiDict(data);duplicate.add('clearance_factor','1')
        self.assertEqual(self.client.post(path,data=duplicate).status_code,400)

    def test_failed_audit_has_no_overlay_and_can_export_withheld_report(self):
        self.source_run()
        with patch('intelligence_store.educational_pk_sensitivity.audit_pk_run',return_value={
            'method_version':'test','report_sha256':'f'*64,'status':'mathematical_check_failed'}):
            response=self.client.post(self.sensitivity_path(),data=self.sensitivity_form())
            self.assertEqual(response.status_code,200)
            text=response.get_data(as_text=True)
            self.assertIn('Sensitivity withheld',text);self.assertNotIn('<svg ',text)
            response=self.client.post(self.sensitivity_path(),data=self.sensitivity_form('download'))
            self.assertEqual(response.get_json()['status'],'sensitivity_withheld')
            self.assertIsNone(response.get_json()['points'])


if __name__=='__main__':unittest.main()
