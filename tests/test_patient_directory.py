"""Integration checks for the unified, read-only Patient Lab workspace."""
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


class PatientDirectoryTests(unittest.TestCase):
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

    path='/landscape/patient-lab/workspace'

    def test_empty_directory_and_strict_queries(self):
        page=self.client.get(self.path)
        self.assertEqual(page.status_code,200)
        self.assertIn('No saved synthetic scenarios yet',page.get_data(as_text=True))
        for query in ['page=0','page=abc','q=a&q=b','dose=25','cohort_id=-1']:
            self.assertEqual(self.client.get(self.path+'?'+query).status_code,400)
        self.assertEqual(self.client.get(self.path+'?page=2').status_code,404)
        self.assertEqual(self.client.post(self.path).status_code,405)

    def test_baseline_and_saved_workspace_actions_are_bound_and_read_only(self):
        from intelligence_store.educational_pk_runs import save_pk_run
        self.baseline()
        run=save_pk_run(self.revision.id,model_input_example(),treatment_request_example(),'MM',title='<script>Archive title</script>')
        before=self.table_hashes()
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No solver')), \
             patch('requests.get',side_effect=AssertionError('No retrieval')):
            page=self.client.get(self.path)
        text=page.get_data(as_text=True)
        self.assertIn(self.overview()+f'?run_id={run.id}',text)
        self.assertIn('&lt;script&gt;Archive title&lt;/script&gt;',text)
        self.assertNotIn('<script>Archive title</script>',text)
        self.assertIn('Compare states and exposure',text)
        self.assertEqual(self.table_hashes(),before)
        self.assertEqual(page.headers['Cache-Control'],'no-store')
        self.assertEqual(page.headers['X-Content-Type-Options'],'nosniff')
        self.assertEqual(text.count('class="nav-item active"'),1)

    def test_latest_state_does_not_borrow_older_exposure(self):
        from intelligence_store.educational_pk_runs import save_pk_run
        self.baseline()
        old=save_pk_run(self.revision.id,model_input_example(),treatment_request_example(),'MM',title='Old state exposure')
        new=save_revision(self.scenario.id,self.base,title='Latest state without run',parent_revision_id=self.revision.id)
        text=self.client.get(self.path).get_data(as_text=True)
        self.assertIn('Latest state without run',text)
        self.assertIn('No educational run is saved for the latest revision',text)
        self.assertNotIn('Old state exposure',text)
        self.assertIn(f'/revisions/{new.id}/patient-lab-overview',text)

    def test_missing_state_guidance_and_corrupt_entry_isolation(self):
        good=self.save_scenario()
        text=self.client.get(self.path).get_data(as_text=True)
        self.assertIn('Create baseline patient state',text)
        bad=self.save_scenario('b')
        from intelligence_store.saved_scenarios import SavedPatientScenario
        db.session.execute(update(SavedPatientScenario).where(SavedPatientScenario.id==bad.id).values(title='Corrupt title'))
        db.session.commit();db.session.expire_all()
        page=self.client.get(self.path);text=page.get_data(as_text=True)
        self.assertEqual(page.status_code,200)
        self.assertIn(f'Scenario #{bad.id} · Details unavailable',text)
        self.assertIn(f'/scenarios/{good.id}',text)
        self.assertNotIn('Corrupt title',text)

    def test_title_search_is_literal_and_pagination_is_bounded(self):
        from intelligence_store.saved_scenarios import SavedPatientScenario
        from intelligence_store.saved_scenarios import save_scenario
        for i in range(11):
            save_scenario('Patient '+str(i),1,self.profile,digest(self.analysis),format(i+1,'064x'))
        page=self.client.get(self.path)
        self.assertEqual(page.get_data(as_text=True).count('class="panel patient-directory-card"'),10)
        nextpage=self.client.get(self.path+'?page=2')
        self.assertEqual(nextpage.get_data(as_text=True).count('class="panel patient-directory-card"'),1)
        self.assertIn('11 saved scenario rows',page.get_data(as_text=True))
        search=self.client.get(self.path,query_string={'q':'Patient 10'})
        self.assertIn('1 saved scenario rows',search.get_data(as_text=True))
        literal=self.client.get(self.path,query_string={'q':'%'})
        self.assertIn('No matching saved scenarios',literal.get_data(as_text=True))

    def test_sidebar_opens_directory_and_keeps_scenario_creation_link(self):
        self.baseline()
        text=self.client.get(self.overview()).get_data(as_text=True)
        self.assertIn('href="/landscape/patient-lab/workspace?cohort_id=1"',text)
        text=self.client.get(self.path+'?cohort_id=1').get_data(as_text=True)
        self.assertIn('href="/landscape/patient-lab?cohort_id=1"',text)


if __name__=="__main__":unittest.main()
