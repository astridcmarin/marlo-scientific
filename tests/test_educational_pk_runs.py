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
from intelligence_store.patient_state import digest, state_from_scenario
from intelligence_store.patient_state_revisions import PatientStateRevision, save_revision, export_revision
from intelligence_store.validation import validate_platform


from unittest.mock import patch
from intelligence_store.pk_model_inputs import model_input_example


from intelligence_store.treatment_requests import treatment_request_example






from intelligence_store.educational_pk_runs import (EducationalPKRun,save_pk_run,read_pk_run,export_pk_run,register_educational_pk_run_commands)

class EducationalPKRunTests(unittest.TestCase):
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

    def test_full_snapshot_roundtrip_without_solver_or_current_contracts(self):
        self.baseline();original=export_revision(self.revision.id);row=self.save()
        with patch('intelligence_store.educational_pk_runs.calculate_educational_pk',side_effect=AssertionError('No rerun')), \
             patch('intelligence_store.educational_pk.load_execution_contract',side_effect=ValueError('New incompatible catalog')):
            saved=export_pk_run(row.id)
        payload=saved['payload'];self.assertEqual(digest(payload),saved['payload_sha256'])
        report=payload['report'];review=report['preflight_review']
        self.assertEqual(review['captured_state'],self.revision.payload['state'])
        self.assertEqual(len(report['points']),721);self.assertFalse(report['clinical_prediction_validated'])
        self.assertFalse(report['ready_for_patient_simulation'])
        self.assertEqual(review['binding']['revision_payload_sha256'],self.revision.payload_sha256)
        self.assertEqual(export_revision(self.revision.id),original)
        saved['payload']['title']='external change'
        self.assertEqual(read_pk_run(row.id).title,'Educational run')

    def test_idempotent_retries_and_distinct_inputs_or_titles(self):
        self.baseline();first=self.save();again=self.save();self.assertEqual(first.id,again.id)
        titled=self.save('Separate label');self.assertNotEqual(first.id,titled.id)
        request=treatment_request_example()
        for e in request['events']:e['amount']['value']=15
        different=save_pk_run(self.revision.id,model_input_example(),request,'MM',title='Educational run')
        self.assertNotEqual(first.id,different.id);self.assertNotEqual(first.report_sha256,different.report_sha256)
        self.assertEqual(len(list(db.session.scalars(select(EducationalPKRun)))),3)

    def test_blocked_invalid_and_missing_inputs_never_save(self):
        self.baseline()
        with self.assertRaisesRegex(ValueError,'Calculation blocked'):
            save_pk_run(self.revision.id,model_input_example(),treatment_request_example(),'UNKNOWN')
        for title in ('','x'*161,'bad\ntitle'):
            with self.assertRaises(ValueError):self.save(title)
        for bad in (0,True,'1'):
            with self.assertRaises(ValueError):read_pk_run(bad)
        self.assertIsNone(read_pk_run(999))
        self.assertEqual(len(list(db.session.scalars(select(EducationalPKRun)))),0)

    def test_orm_guards_and_payload_tampering_detection(self):
        self.baseline();row=self.save();row.title='Changed'
        with self.assertRaisesRegex(ValueError,'cannot be updated'):db.session.commit()
        db.session.rollback();row=read_pk_run(row.id);db.session.delete(row)
        with self.assertRaisesRegex(ValueError,'cannot be updated'):db.session.commit()
        db.session.rollback();row=read_pk_run(row.id)
        payload=copy.deepcopy(row.payload);payload['report']['points'][10]['concentration_ng_ml']+=1
        db.session.execute(update(EducationalPKRun).where(EducationalPKRun.id==row.id).values(payload=payload));db.session.commit();db.session.expire_all()
        with self.assertRaisesRegex(ValueError,'checksum'):read_pk_run(row.id)
        report=validate_platform(1)
        check=next(c for c in report['checks'] if c['key']=='educational_pk_runs')
        self.assertEqual(check['status'],'failed')

    def test_revision_anchor_failure_is_not_hidden_by_valid_run_checksum(self):
        self.baseline();row=self.save()
        db.session.execute(update(PatientStateRevision).where(PatientStateRevision.id==self.revision.id).values(title='Tampered'))
        db.session.commit();db.session.expire_all()
        with self.assertRaisesRegex(ValueError,'integrity'):read_pk_run(row.id)

    def test_missing_storage_is_actionable(self):
        self.baseline();EducationalPKRun.__table__.drop(db.engine)
        try:
            with self.assertRaisesRegex(ValueError,'Step 45 migration'):self.save()
        finally:EducationalPKRun.__table__.create(db.engine)

    def test_cli_save_list_export_and_never_overwrite(self):
        self.baseline();register_educational_pk_run_commands(self.app);runner=self.app.test_cli_runner()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);inputs=root/'inputs.json';request=root/'request.json';output=root/'result.json'
            inputs.write_text(json.dumps(model_input_example()));request.write_text(json.dumps(treatment_request_example()))
            args=['patient-pk-save','--revision-id',str(self.revision.id),'--inputs-file',str(inputs),'--treatment-file',str(request),'--disease-code','MM']
            with patch('socket.socket.connect',side_effect=AssertionError('No network')):
                result=runner.invoke(args=args);self.assertEqual(result.exit_code,0,result.output)
                again=runner.invoke(args=args);self.assertEqual(again.exit_code,0,again.output)
                row=db.session.scalar(select(EducationalPKRun));self.assertIn(f'run ID: {row.id}',again.output)
                result=runner.invoke(args=['patient-pk-list','--revision-id',str(self.revision.id)])
                self.assertEqual(result.exit_code,0,result.output);self.assertIn('1 saved educational runs',result.output)
                with patch('intelligence_store.educational_pk_runs.calculate_educational_pk',side_effect=AssertionError('No export solver')):
                    result=runner.invoke(args=['patient-pk-export','--id',str(row.id),'--output',str(output)])
                    self.assertEqual(result.exit_code,0,result.output)
                    self.assertEqual(json.loads(output.read_text()),export_pk_run(row.id))
                    before=output.read_bytes()
                    result=runner.invoke(args=['patient-pk-export','--id',str(row.id),'--output',str(output)])
                    self.assertNotEqual(result.exit_code,0);self.assertEqual(output.read_bytes(),before)
