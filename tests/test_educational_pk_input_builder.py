"""Revision lineage, retries and integrity preserve prior synthetic inputs."""
import json
import unittest
from sqlalchemy import select, delete, inspect
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






class EducationalPKInputBuilderTests(unittest.TestCase):
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

    def builder_form(self, **changes):
        form=self.form()
        form={key:form[key] for key in ('form_token','disease')}
        form.update(action='build',ffm='55',crcl='90',horizon='72',events='0,5\n24,5\n48,5',
                    source_ref='Invented educational example, not patient measurements or prescribed treatment.')
        form.update(changes)
        return form

    def test_build_preserves_declared_inputs_and_never_calculates_or_writes(self):
        import html,re
        from intelligence_store.educational_pk_runs import EducationalPKRun
        self.baseline()
        before=export_revision(self.revision.id)
        with patch('landscape_ui.educational_pk_pages.calculate_educational_pk',side_effect=AssertionError('No calculation')),             patch('landscape_ui.educational_pk_pages.save_pk_run',side_effect=AssertionError('No save')):
            response=self.client.post(self.page(),data=self.builder_form(disease='UNKNOWN'))
        self.assertEqual(response.status_code,200)
        text=response.get_data(as_text=True)
        self.assertIn('JSON prepared below',text)
        self.assertIn('value="UNKNOWN" selected',text)
        inputs=json.loads(html.unescape(re.search(r'<textarea id="inputs"[^>]*>(.*?)</textarea>',text,re.S).group(1)))
        treatment=json.loads(html.unescape(re.search(r'<textarea id="treatment"[^>]*>(.*?)</textarea>',text,re.S).group(1)))
        self.assertEqual(inputs['fields']['fat_free_mass']['value'],55)
        self.assertEqual(inputs['fields']['creatinine_clearance']['method'],'direct_synthetic_covariate')
        self.assertEqual([e['time']['value'] for e in treatment['events']],[0,24,48])
        self.assertEqual(treatment['source_ref'],inputs['fields']['fat_free_mass']['source_ref'])
        self.assertEqual(export_revision(self.revision.id),before)
        self.assertEqual(db.session.query(EducationalPKRun).count(),0)
        form=self.form();form.update(inputs=json.dumps(inputs),treatment=json.dumps(treatment))
        result=self.client.post(self.page(),data=form)
        self.assertIn('Educational calculation completed',result.get_data(as_text=True))
        self.assertEqual(db.session.query(EducationalPKRun).count(),0)

    def test_builder_rejects_invalid_numbers_schedule_and_provenance(self):
        self.baseline()
        from landscape_ui.educational_pk_input_builder import build_synthetic_inputs, BUILDER_FIELDS
        values={k:v for k,v in self.builder_form().items() if k in BUILDER_FIELDS}
        for key,value in [('ffm',''),('ffm','NaN'),('ffm','1e2'),('ffm','0'),('crcl','-1'),
                ('source_ref',' '),('horizon','72.01'),('horizon','73'),('events','0,5\n8,5'),
                ('events','0,5\n24,5\n24,5'),('events','0,0'),('events','0,5,9'),
                ('events','0,5\n24,5\n48,5\n72,5\n96,5'),('events','0,5\n24,5')]:
            with self.subTest(key=key,value=value):
                item=dict(values);item[key]=value
                if value=='0,5\n24,5':item['horizon']='12'
                with self.assertRaises(ValueError):build_synthetic_inputs(item)

    def test_different_explicit_amounts_and_boundary_event_survive(self):
        self.baseline()
        from landscape_ui.educational_pk_input_builder import build_synthetic_inputs, BUILDER_FIELDS
        values={k:v for k,v in self.builder_form(events='0,5\n24,7.5',horizon='24').items() if k in BUILDER_FIELDS}
        inputs,treatment=build_synthetic_inputs(values)
        self.assertEqual([e['amount']['value'] for e in treatment['events']],[5,7.5])
        self.assertEqual(treatment['events'][-1]['time']['value'],treatment['horizon']['value'])
        values['ffm']='31' # Coverage review, rather than input syntax, rejects this later.
        self.assertEqual(build_synthetic_inputs(values)[0]['fields']['fat_free_mass']['value'],31)

    def test_form_security_and_errors_retain_values_without_execution(self):
        from werkzeug.datastructures import MultiDict
        self.baseline()
        form=self.builder_form()
        with patch('landscape_ui.educational_pk_pages.calculate_educational_pk',side_effect=AssertionError('No calculation')):
            self.assertEqual(self.client.post(self.page(),data=dict(form,form_token='bad')).status_code,403)
            self.assertEqual(self.client.post(self.page(),data=dict(form,extra='x')).status_code,400)
            self.assertEqual(self.client.post(self.page(),data=dict(form,action='calculate')).status_code,400)
            duplicate=MultiDict(form);duplicate.add('ffm','56')
            self.assertEqual(self.client.post(self.page(),data=duplicate).status_code,400)
            result=self.client.post(self.page(),data=dict(form,ffm='NaN',source_ref='<b>invented</b>'))
            self.assertEqual(result.status_code,400)
            text=result.get_data(as_text=True)
            self.assertIn('value="NaN"',text);self.assertIn('&lt;b&gt;invented&lt;/b&gt;',text)
            self.assertNotIn('JSON prepared below',text)

    def test_get_has_blank_builder_and_no_inferred_disease(self):
        self.baseline()
        text=self.client.get(self.page()).get_data(as_text=True)
        self.assertIn('name="ffm" inputmode="decimal" maxlength="40" required value=""',text)
        self.assertIn('Unknown — declare context before calculating',text)
        self.assertNotIn('JSON prepared below',text)


if __name__=='__main__':unittest.main()
