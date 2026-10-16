"""Revision lineage, retries and integrity preserve prior synthetic inputs."""
import json
from pathlib import Path
import tempfile
import unittest
from sqlalchemy import select, delete, inspect
from flask import Flask
from datetime import datetime
from intelligence_store.models import AnalysisCohort, CohortTrial, TrialSnapshot
from intelligence_store.patient_scenarios import load_scenario_presets
from intelligence_store.saved_scenarios import analyze_for_save, save_scenario
from intelligence_store.extensions import db
from intelligence_store.patient_state import example_state, digest, state_from_scenario
from intelligence_store.patient_state_revisions import PatientStateRevision, save_revision


from unittest.mock import patch
from intelligence_store.pk_model_inputs import model_input_example


from intelligence_store.treatment_requests import treatment_request_example


from intelligence_store.model_coverage import (review_model_coverage,load_coverage_contract,register_model_coverage_commands)


class ModelCoverageTests(unittest.TestCase):
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

    def complete_state(self):
        state=example_state();state['fields']['serum_creatinine'].update(value=80,origin='synthetic_input')
        return state

    def test_known_ranges_and_group_count_do_not_enable_simulation(self):
        self.baseline(self.complete_state())
        r=review_model_coverage(self.revision.id,model_input_example(),treatment_request_example(),'MM')
        self.assertEqual(r['status'],'coverage_review_only')
        self.assertEqual(r['source_subject_count'],125)
        self.assertEqual(r['declared_disease_context']['source_group_subject_count'],20)
        self.assertEqual(sum(load_coverage_contract()['disease_counts'].values()),125)
        self.assertTrue(all(c['status']=='within_reported_range' for c in r['coverage_checks']))
        self.assertFalse(r['ready_for_patient_simulation']);self.assertEqual(r['simulation_status'],'not_run')
        self.assertIn('joint_and_regimen_coverage_not_established',[b['code'] for b in r['blockers']])

    def test_unknown_context_and_disease_are_not_inferred_or_filled(self):
        self.baseline();r=review_model_coverage(self.revision.id,model_input_example(),treatment_request_example())
        self.assertEqual(r['status'],'source_coverage_gaps')
        self.assertEqual(r['declared_disease_context']['code'],'UNKNOWN')
        self.assertIn('serum_creatinine',r['unknown_context_fields'])
        self.assertIsNone(r['captured_state']['fields']['serum_creatinine']['value'])
        self.assertEqual(r['captured_state'],self.revision.payload['state'])

    def test_age_and_disease_extrapolation_preserve_values(self):
        state=self.complete_state();state['fields']['age_years']['value']=80;self.baseline(state)
        r=review_model_coverage(self.revision.id,model_input_example(),treatment_request_example(),'OTHER')
        self.assertEqual(r['status'],'source_extrapolation_flagged')
        self.assertIn('age_years',r['outside_reported_ranges'])
        self.assertEqual(r['captured_state']['fields']['age_years']['value'],80)
        self.assertEqual(r['declared_disease_context']['status'],'not_a_reported_group')
        with self.assertRaises(ValueError):review_model_coverage(self.revision.id,model_input_example(),treatment_request_example(),'MYELOMA')

    def test_listed_amounts_differ_from_unlisted_and_outside_range(self):
        self.baseline(self.complete_state());request=treatment_request_example()
        request['events'][0]['amount']['value']=10
        r=review_model_coverage(self.revision.id,model_input_example(),request,'MM')
        self.assertEqual(r['treatment_amount_checks'][0]['status'],'within_range_but_not_listed_amount')
        self.assertEqual(r['status'],'source_coverage_gaps')
        request['events'][0]['amount']['value']=1
        r=review_model_coverage(self.revision.id,model_input_example(),request,'MM')
        self.assertEqual(r['treatment_amount_checks'][0]['status'],'outside_reported_amount_range')
        self.assertEqual(r['status'],'source_extrapolation_flagged')
        self.assertEqual(r['treatment_request_preview']['request']['events'][0]['amount']['value'],1)

    def test_report_and_context_identity_contract_integrity(self):
        self.baseline();a=review_model_coverage(self.revision.id,model_input_example(),treatment_request_example(),'MM')
        b=review_model_coverage(self.revision.id,model_input_example(),treatment_request_example(),'CLL')
        self.assertNotEqual(a['binding_sha256'],b['binding_sha256'])
        body=dict(a);sha=body.pop('report_sha256');self.assertEqual(digest(body),sha)
        self.assertEqual(digest(a['binding']),a['binding_sha256'])
        self.assertEqual(a,review_model_coverage(self.revision.id,model_input_example(),treatment_request_example(),'MM'))
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'contract.json'
            with self.assertRaises(ValueError):load_coverage_contract(p)
            p.write_text('{}')
            with self.assertRaises(ValueError):load_coverage_contract(p)

    def test_no_database_write_network_solver_or_unsupported_drug_fallback(self):
        self.profile={**self.profile,'selected_drug':'bortezomib'}
        self.analysis=analyze_for_save(1,self.profile);self.profile=self.analysis['report']['profile'];self.baseline()
        def snapshot():
            return json.dumps({t.name:[dict(r) for r in db.session.execute(select(t)).mappings()]
                for t in db.metadata.sorted_tables},sort_keys=True,default=str)
        before=snapshot()
        with patch('requests.sessions.Session.request',side_effect=AssertionError('Network')), \
             patch('intelligence_store.transit_kernel.solve_transit',side_effect=AssertionError('Solver')):
            r=review_model_coverage(self.revision.id,model_input_example(),treatment_request_example(),'MM')
        self.assertEqual(r['status'],'unsupported_drug');self.assertIsNone(r['standalone_input_preview'])
        self.assertEqual(before,snapshot());self.assertEqual(list(db.session.dirty),[])

    def test_cli_json_and_non_overwriting_export(self):
        self.baseline();register_model_coverage_commands(self.app);runner=self.app.test_cli_runner()
        with tempfile.TemporaryDirectory() as tmp:
            cov=Path(tmp)/'inputs.json';req=Path(tmp)/'request.json';out=Path(tmp)/'coverage.json'
            cov.write_text(json.dumps(model_input_example()));req.write_text(json.dumps(treatment_request_example()))
            args=['patient-model-coverage','--revision-id',str(self.revision.id),'--inputs-file',str(cov),'--treatment-file',str(req),'--disease-code','MM']
            r=runner.invoke(args=args+['--json']);self.assertEqual(r.exit_code,0,r.output)
            self.assertEqual(json.loads(r.stdout),review_model_coverage(self.revision.id,model_input_example(),treatment_request_example(),'MM'))
            self.assertEqual(runner.invoke(args=args+['--output',str(out)]).exit_code,0)
            saved=out.read_bytes();self.assertNotEqual(runner.invoke(args=args+['--output',str(out)]).exit_code,0)
            self.assertEqual(saved,out.read_bytes())


if __name__=='__main__':unittest.main()
