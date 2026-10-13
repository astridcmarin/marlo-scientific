"""Revision lineage, retries and integrity preserve prior synthetic inputs."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from sqlalchemy import select, update, delete, inspect
from flask import Flask
from datetime import datetime
from intelligence_store.models import AnalysisCohort, CohortTrial, TrialSnapshot
from intelligence_store.patient_scenarios import load_scenario_presets
from intelligence_store.saved_scenarios import analyze_for_save, save_scenario
from intelligence_store.extensions import db
from intelligence_store.patient_state import example_state, digest, state_from_scenario
from intelligence_store.patient_state_revisions import PatientStateRevision, save_revision


class PatientModelReviewTests(unittest.TestCase):
    def setUp(self):
            app = Flask(__name__)
            app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite://', INTELLIGENCE_WORKSPACE_SECRET='web-test-secret-33')
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

    def review(self):
        from intelligence_store.patient_model_review import review_patient_model
        return review_patient_model(self.revision.id)

    def test_baseline_missing_inputs_and_model_blockers_are_separate(self):
        self.baseline();report=self.review()
        self.assertEqual(report['status'],'blocked_model_review')
        self.assertIn('creatinine_clearance',report['unknown_fields'])
        self.assertIn('egfr_indexed',report['recorded_fields'])
        self.assertFalse(report['ready_for_personalized_simulation'])
        self.assertEqual(report['simulation_status'],'not_run')
        self.assertEqual(len(report['blockers']),6)
        self.assertIsNone(report['selected_model'])
        self.assertIsNone(report['predicted_outputs'])
        self.assertIsNone(report['patient_parameter_adjustments'])
        self.assertEqual(len(report['fields']),11)

    def test_complete_state_cannot_unlock_unvalidated_model(self):
        state=example_state()
        for name,field in state['fields'].items():
            field.update(value='FEMALE' if name=='biological_sex' else 1,origin='synthetic_input',source_ref=None)
        self.baseline(state);report=self.review()
        self.assertEqual(len(report['recorded_fields']),11)
        self.assertEqual(report['unknown_fields'],[])
        self.assertFalse(report['ready_for_personalized_simulation'])
        self.assertEqual(report['status'],'blocked_model_review')
        self.assertEqual(len(report['blockers']),6)

    def test_zero_renal_measure_is_recorded_without_substitution(self):
        state=example_state();state['fields']['egfr_indexed']['value']=0
        self.baseline(state);report=self.review();fields={r['field']:r for r in report['fields']}
        self.assertEqual(fields['egfr_indexed']['availability'],'recorded')
        self.assertEqual(fields['egfr_indexed']['input']['value'],0)
        self.assertIsNone(fields['creatinine_clearance']['input']['value'])
        self.assertEqual(fields['egfr_indexed']['input']['unit'],'mL/min/1.73m2')
        self.assertEqual(fields['creatinine_clearance']['input']['unit'],'mL/min')

    def test_unsupported_drug_gets_no_candidate_substitution(self):
        self.profile=copy.deepcopy(self.profile);self.profile['selected_drug']='dexamethasone'
        self.analysis=analyze_for_save(1,self.profile)
        self.profile=self.analysis['report']['profile'];self.baseline();report=self.review()
        self.assertEqual(report['status'],'unsupported_drug')
        self.assertEqual(report['candidate_models'],[])
        self.assertIsNone(report['label_context'])
        self.assertEqual([r['code'] for r in report['blockers']],['unsupported_drug'])

    def test_determinism_digests_and_captured_provenance(self):
        self.baseline();report=self.review();copy_report=copy.deepcopy(report)
        self.assertEqual(copy_report.pop('report_sha256'),digest(copy_report))
        self.assertEqual(report,self.review())
        self.assertEqual(report['state_sha256'],self.revision.state_sha256)
        self.assertEqual(report['revision_payload_sha256'],self.revision.payload_sha256)
        self.assertEqual(report['scenario_payload_sha256'],self.scenario.payload_sha256)
        report['captured_scenario_inputs']['age_years']=99
        report['fields'][0]['input']['value']=99
        self.assertEqual(self.revision.payload['state'],self.base)
        self.assertNotEqual(report,self.review())

    def test_missing_corrupt_records_and_contract_fail_closed(self):
        from intelligence_store.patient_model_review import review_patient_model,load_model_contract
        self.baseline()
        for value in (0,True,999):
            with self.assertRaises(ValueError):review_patient_model(value)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'contract.json'
            with self.assertRaises(ValueError):load_model_contract(path)
            path.write_text('{}')
            with self.assertRaises(ValueError):load_model_contract(path)
        db.session.execute(update(PatientStateRevision).where(PatientStateRevision.id==self.revision.id).values(title='Tampered'));db.session.commit();db.session.expire_all()
        with self.assertRaises(ValueError):self.review()

    def test_read_only_no_network_catalog_or_pk(self):
        from unittest.mock import patch
        self.baseline();before=copy.deepcopy(self.scenario.payload);captured=copy.deepcopy(self.revision.payload)
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No network')):
            with patch('intelligence_store.pharmacokinetics.simulate_pk',side_effect=AssertionError('No PK')):
                with patch('intelligence_store.patient_scenarios.load_scenario_presets',side_effect=AssertionError('No catalog reanalysis')):
                    self.assertEqual(self.review()['simulation_status'],'not_run')
        self.assertEqual(self.scenario.payload,before);self.assertEqual(self.revision.payload,captured)
        self.assertEqual(db.session.query(PatientStateRevision).count(),1)

    def test_cli_text_json_export_and_no_overwrite(self):
        from intelligence_store.patient_model_review import register_patient_model_review_commands
        self.baseline();register_patient_model_review_commands(self.app);runner=self.app.test_cli_runner()
        args=['patient-model-review','--revision-id',str(self.revision.id)]
        result=runner.invoke(args=args);self.assertEqual(result.exit_code,0,result.output)
        self.assertIn('[BLOCKED]',result.output)
        exported=runner.invoke(args=args+['--json']);self.assertEqual(exported.exit_code,0,exported.output)
        self.assertEqual(json.loads(exported.output),self.review())
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'review.json';result=runner.invoke(args=args+['--output',str(path)])
            self.assertEqual(result.exit_code,0,result.output);before=path.read_bytes()
            self.assertNotEqual(runner.invoke(args=args+['--output',str(path)]).exit_code,0)
            self.assertEqual(path.read_bytes(),before)
        self.assertNotEqual(runner.invoke(args=['patient-model-review','--revision-id','0']).exit_code,0)

if __name__=='__main__':unittest.main()
