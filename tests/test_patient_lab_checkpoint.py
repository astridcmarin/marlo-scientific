"""Revision lineage, retries and integrity preserve prior synthetic inputs."""
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
from intelligence_store.patient_state import digest, state_from_scenario
from intelligence_store.patient_state_revisions import PatientStateRevision, save_revision


from unittest.mock import patch
from intelligence_store.pk_model_inputs import model_input_example


from intelligence_store.treatment_requests import treatment_request_example






class PatientLabCheckpointTests(unittest.TestCase):
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
        self.run=save_pk_run(self.revision.id,model_input_example(),treatment_request_example(),'MM',title='Checkpoint source')
        return self.run

    def checkpoint(self,**kwargs):
        from intelligence_store.patient_lab_checkpoint import patient_lab_checkpoint
        return patient_lab_checkpoint(1,self.scenario.id,self.revision.id,self.run.id,**kwargs)

    def hashes(self):
        return {t.name:digest(json.loads(json.dumps([dict(row) for row in db.session.execute(select(t)).mappings()],default=str))) for t in db.metadata.sorted_tables}

    def test_chosen_workflow_is_read_only_without_default_sensitivity(self):
        self.source_run();before=self.hashes()
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No ODE')),             patch('socket.socket.connect',side_effect=AssertionError('No network')):
            report=self.checkpoint()
        self.assertEqual(report['status'],'software_checkpoint_passed_with_warnings')
        self.assertEqual(report['audit']['status'],'mathematical_checks_passed')
        self.assertEqual(report['metrics']['status'],'sampled_metrics_available')
        self.assertIsNone(report['sensitivity']);self.assertFalse(report['sensitivity_requested'])
        self.assertIsNone(report['migration_heads'])
        self.assertEqual(report['source_hashes']['run_payload_sha256'],self.run.payload_sha256)
        self.assertEqual(self.hashes(),before)
        self.assertEqual(digest({k:v for k,v in report.items() if k!='report_sha256'}),report['report_sha256'])
        self.assertFalse(report['clinical_prediction_validated'])

    def test_recorded_heads_and_optional_explicit_sensitivity(self):
        from sqlalchemy import text
        self.source_run()
        db.session.execute(text('CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)'))
        db.session.execute(text("INSERT INTO alembic_version VALUES ('3949e70874a5')"));db.session.commit()
        report=self.checkpoint(clearance_factor=0.8,assumption_note='Invented checkpoint sensitivity')
        self.assertEqual(report['migration_heads'],['3949e70874a5'])
        self.assertEqual(report['status'],'software_checkpoint_passed')
        self.assertEqual(report['sensitivity']['status'],'sensitivity_available')
        self.assertEqual(report['sensitivity']['source_payload_sha256'],report['source_hashes']['run_payload_sha256'])
        self.assertIn('not validated',report['migration_check_scope'])

    def test_wrong_context_and_tamper_fail_without_substitution(self):
        from intelligence_store.patient_lab_checkpoint import patient_lab_checkpoint
        from intelligence_store.educational_pk_runs import EducationalPKRun
        self.source_run()
        for values in [(999,self.scenario.id,self.revision.id,self.run.id),(1,999,self.revision.id,self.run.id),(1,self.scenario.id,999,self.run.id),(1,self.scenario.id,self.revision.id,999)]:
            report=patient_lab_checkpoint(*values)
            self.assertEqual(report['status'],'software_checkpoint_failed')
            self.assertIsNone(report['source_hashes']);self.assertIsNone(report['audit'])
        other=save_revision(self.scenario.id,self.base,parent_revision_id=self.revision.id,title='Other record')
        report=patient_lab_checkpoint(1,self.scenario.id,other.id,self.run.id)
        self.assertEqual(report['status'],'software_checkpoint_failed')
        db.session.execute(update(EducationalPKRun).where(EducationalPKRun.id==self.run.id).values(title='Tampered'));db.session.commit();db.session.expire_all()
        report=self.checkpoint()
        self.assertEqual(report['status'],'software_checkpoint_failed');self.assertIsNone(report['audit'])

    def test_missing_column_and_failed_audit_do_not_pass(self):
        from sqlalchemy import text
        self.source_run()
        with patch('intelligence_store.patient_lab_checkpoint.audit_pk_run',return_value={
            'status':'mathematical_check_failed','method_version':'test','report_sha256':'f'*64}):
            report=self.checkpoint()
        self.assertEqual(report['status'],'software_checkpoint_failed')
        from intelligence_store.patient_lab_checkpoint import patient_lab_checkpoint
        ids=(1,self.scenario.id,self.revision.id,self.run.id)
        db.session.execute(text('ALTER TABLE educational_pk_run DROP COLUMN title'));db.session.commit()
        report=patient_lab_checkpoint(*ids)
        self.assertEqual(report['status'],'software_checkpoint_failed')
        self.assertEqual(report['checks'][0]['detail']['missing_columns'],{'educational_pk_run':['title']})
        self.assertIsNone(report['platform'])

    def test_cli_matches_report_exports_never_overwrite_and_arguments_are_explicit(self):
        from intelligence_store.patient_lab_checkpoint import register_patient_lab_checkpoint_commands,patient_lab_checkpoint
        self.source_run();register_patient_lab_checkpoint_commands(self.app)
        runner=self.app.test_cli_runner()
        args=['patient-lab-checkpoint','--cohort-id','1','--scenario-id',str(self.scenario.id),'--revision-id',str(self.revision.id),'--run-id',str(self.run.id)]
        result=runner.invoke(args=args+['--json']);self.assertEqual(result.exit_code,0,result.output)
        self.assertEqual(json.loads(result.output),self.checkpoint())
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'checkpoint.json'
            self.assertEqual(runner.invoke(args=args+['--output',str(path)]).exit_code,0)
            before=path.read_bytes()
            self.assertNotEqual(runner.invoke(args=args+['--output',str(path)]).exit_code,0)
            self.assertEqual(before,path.read_bytes())
        self.assertNotEqual(runner.invoke(args=args+['--clearance-factor','0.8']).exit_code,0)
        for bad in (True,0,'1'):
            with self.assertRaises(ValueError):patient_lab_checkpoint(bad,1,1,1)
        self.assertNotEqual(runner.invoke(args=['patient-lab-checkpoint']).exit_code,0)
        failed=runner.invoke(args=['patient-lab-checkpoint','--cohort-id','999','--scenario-id',str(self.scenario.id),'--revision-id',str(self.revision.id),'--run-id',str(self.run.id),'--json'])
        self.assertEqual(failed.exit_code,1);self.assertEqual(json.loads(failed.output)['status'],'software_checkpoint_failed')


if __name__=='__main__':unittest.main()
