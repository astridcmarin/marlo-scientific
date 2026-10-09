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


class PatientLabWorkspaceTests(unittest.TestCase):
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

    def test_empty_overview_is_read_only_and_unknown_stays_unknown(self):
        self.baseline()
        before=self.table_hashes()
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No solver')),             patch('intelligence_store.educational_pk_audit.audit_pk_run',side_effect=AssertionError('No audit')):
            response=self.client.get(self.overview())
        self.assertEqual(response.status_code,200)
        text=response.get_data(as_text=True)
        self.assertIn('No educational runs have been saved',text)
        self.assertIn('Creatinine clearance',text)
        self.assertIn('Patient simulation ready:',text)
        self.assertEqual(text.count('class="nav-item active"'),1)
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertEqual(response.headers['X-Content-Type-Options'],'nosniff')
        self.assertEqual(self.table_hashes(),before)
        from intelligence_store.patient_state_revisions import export_revision
        self.assertIsNone(export_revision(self.revision.id)['payload']['state']['fields']['creatinine_clearance']['value'])

    def test_saved_run_links_and_titles_are_context_bound_and_escaped(self):
        self.baseline()
        from intelligence_store.educational_pk_runs import save_pk_run
        row=save_pk_run(self.revision.id,model_input_example(),treatment_request_example(),'MM',title='<script>invented</script>')
        before=self.table_hashes()
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No solver')):
            response=self.client.get(self.overview())
        self.assertEqual(response.status_code,200)
        text=response.get_data(as_text=True)
        self.assertIn('1 saved run rows',text)
        self.assertIn('&lt;script&gt;invented&lt;/script&gt;',text)
        self.assertNotIn('<script>invented</script>',text)
        self.assertIn(f'/pk-runs/{row.id}/audit',text)
        self.assertIn(f'/pk-runs/{row.id}/metrics',text)
        self.assertEqual(self.table_hashes(),before)
        for path in [self.page(),f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{self.revision.id}',f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{self.revision.id}/pk-runs']:
            self.assertIn('Patient Lab overview for this record',self.client.get(path).get_data(as_text=True))

    def test_context_query_and_corrupt_archive_fail_closed(self):
        self.baseline()
        self.assertEqual(self.client.get(self.overview(scenario_id=999)).status_code,404)
        self.assertEqual(self.client.get(self.overview(revision_id=999)).status_code,404)
        self.assertEqual(self.client.get(self.overview()+'?format=json').status_code,400)
        self.assertEqual(self.client.post(self.overview()).status_code,405)
        from intelligence_store.educational_pk_runs import save_pk_run,EducationalPKRun
        row=save_pk_run(self.revision.id,model_input_example(),treatment_request_example(),'MM',title='Original')
        db.session.execute(update(EducationalPKRun).where(EducationalPKRun.id==row.id).values(title='Tampered'));db.session.commit();db.session.expire_all()
        self.assertEqual(self.client.get(self.overview()).status_code,409)

    def test_recent_list_is_bounded_and_specific_to_revision(self):
        self.baseline()
        from intelligence_store.educational_pk_runs import save_pk_run
        rows=[save_pk_run(self.revision.id,model_input_example(),treatment_request_example(),'MM',title=f'Invented run {i}') for i in range(6)]
        other=save_revision(self.scenario.id,self.base,title='Separate record',parent_revision_id=self.revision.id)
        # Only archives for the requested revision are shown.
        text=self.client.get(self.overview()).get_data(as_text=True)
        self.assertIn('6 saved run rows · Showing the latest 5',text)
        self.assertNotIn(f'Run #{rows[0].id} ·',text)
        text=self.client.get(self.overview(revision_id=other.id)).get_data(as_text=True)
        self.assertIn('No educational runs have been saved',text)

    def test_selected_archive_uses_its_own_values_without_solver_or_writes(self):
        self.baseline()
        from intelligence_store.educational_pk_runs import save_pk_run
        first=save_pk_run(self.revision.id,model_input_example(),treatment_request_example(),'MM',title='First explicit request')
        treatment=treatment_request_example()
        for event in treatment['events']:event['amount']['value']=15
        latest=save_pk_run(self.revision.id,model_input_example(),treatment,'MM',title='Second explicit request')
        before=self.table_hashes()
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No solver')), \
             patch('intelligence_store.educational_pk.load_execution_contract',side_effect=AssertionError('No current model catalog')), \
             patch('requests.get',side_effect=AssertionError('No network')):
            response=self.client.get(self.overview()+f'?run_id={first.id}')
            text=response.get_data(as_text=True)
            automatic=self.client.get(self.overview()).get_data(as_text=True)
        self.assertEqual(response.status_code,200)
        self.assertIn(f'Viewing run #{first.id} · First explicit request',text)
        self.assertIn(f'Viewing run #{latest.id} · Second explicit request',automatic)
        self.assertIn('data-pk-points',text)
        self.assertIn('data-pk-archive-chart',text)
        self.assertIn(first.report_sha256,text)
        self.assertIn('Mechanism evidence',text)
        self.assertIn('not calculated from the PK curve',text)
        self.assertIn('Lenalidomide-associated cereblon',text)
        self.assertEqual(self.table_hashes(),before)

    def test_cross_revision_run_and_invalid_query_are_rejected(self):
        self.baseline()
        from intelligence_store.educational_pk_runs import save_pk_run
        other=save_revision(self.scenario.id,self.base,title='Other revision',parent_revision_id=self.revision.id)
        run=save_pk_run(other.id,model_input_example(),treatment_request_example(),'MM')
        self.assertEqual(self.client.get(self.overview()+f'?run_id={run.id}').status_code,404)
        self.assertEqual(self.client.get(self.overview()+'?run_id=999').status_code,404)
        for query in ['run_id=0','run_id=-1','run_id=abc','run_id=1&run_id=1','dose=25','run_id=']:
            with self.subTest(query=query):self.assertEqual(self.client.get(self.overview()+'?'+query).status_code,400)

    def test_frozen_references_survive_current_catalog_failure_and_mechanism_gap(self):
        self.baseline()
        with patch('intelligence_store.drug_aliases.load_alias_catalog',side_effect=ValueError('Catalog unavailable')), \
             patch('landscape_ui.patient_lab_overview_pages.build_mechanism_map',side_effect=ValueError('Packet unavailable')):
            response=self.client.get(self.overview())
        self.assertEqual(response.status_code,200)
        text=response.get_data(as_text=True)
        self.assertIn('Frozen scenario references',text)
        self.assertIn('Patient state and archived PK remain available',text)
        self.assertIn('Lenalidomide knowledge',text)
        self.assertIn(self.scenario.payload_sha256,text)

    def test_zero_unknown_and_provenance_navigation_are_preserved(self):
        state=example_state()
        state['fields']['egfr_indexed']['value']=0
        self.baseline(state)
        text=self.client.get(self.overview()).get_data(as_text=True)
        self.assertIn('0.0 <span class="lab-unit">mL/min/1.73m2',text)
        self.assertIn('<span class="lab-unknown">Unknown</span>',text)
        scenario=self.client.get(f'/landscape/workspace/scenarios/{self.scenario.id}').get_data(as_text=True)
        self.assertIn('Open Patient Lab workspace',scenario)
        self.assertIn(self.overview(),scenario)

    def test_other_drug_does_not_inherit_lenalidomide_map(self):
        self.profile=copy.deepcopy(self.profile)
        self.profile['selected_drug']='dexamethasone'
        self.analysis=analyze_for_save(1,self.profile)
        self.baseline()
        with patch('landscape_ui.patient_lab_overview_pages.build_mechanism_map',side_effect=AssertionError('Wrong drug')):
            text=self.client.get(self.overview()).get_data(as_text=True)
        self.assertIn('No mechanism map is integrated for this selected drug',text)
        self.assertNotIn('Lenalidomide-associated cereblon',text)


if __name__=='__main__':unittest.main()
