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






class PKValidationGapTests(unittest.TestCase):
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
        self.run=save_pk_run(self.revision.id,model_input_example(),treatment_request_example(),'MM',title='Validation-gap source')
        return self.run

    def hashes(self):
        return {t.name:digest(json.loads(json.dumps([dict(row) for row in db.session.execute(select(t)).mappings()],default=str))) for t in db.metadata.sorted_tables}

    def test_report_separates_math_from_clinical_validation_and_is_read_only(self):
        from intelligence_store.pk_validation_gap import validation_gap_report
        self.source_run();before=self.hashes()
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No ODE')),             patch('socket.socket.connect',side_effect=AssertionError('No network')):
            report=validation_gap_report(self.run.id)
        self.assertEqual(report['status'],'clinical_validation_not_established')
        statuses={g['code']:g['status'] for g in report['gates']}
        self.assertEqual(statuses['source_traceability'],'passed')
        self.assertEqual(statuses['numerical_verification'],'passed')
        self.assertEqual(statuses['equation_transcription'],'incomplete')
        for code in ('source_model_reproduction','internal_predictive_performance','external_validation','uncertainty_and_variability','individual_applicability','clinical_endpoint_link'):
            self.assertEqual(statuses[code],'blocked')
        self.assertEqual(report['counts'],{'passed':2,'incomplete':2,'blocked':6,'failed':0})
        self.assertFalse(report['clinical_prediction_validated']);self.assertIsNone(report['validation_approval'])
        self.assertEqual(self.hashes(),before)
        self.assertEqual(digest({k:v for k,v in report.items() if k!='report_sha256'}),report['report_sha256'])

    def test_each_gate_has_evidence_and_prespecified_requirements(self):
        from intelligence_store.pk_validation_gap import validation_gap_report
        self.source_run();report=validation_gap_report(self.run.id)
        self.assertEqual(len(report['gates']),10)
        self.assertEqual(len({g['code'] for g in report['gates']}),10)
        for gate in report['gates']:
            self.assertTrue(gate['current_evidence']);self.assertTrue(gate['evidence_required_to_pass'])
            self.assertIn(gate['status'],('passed','incomplete','blocked','failed'))
        self.assertEqual(len(report['minimum_sequence']),7)
        self.assertEqual(report['source_reference']['doi'],'10.1111/bcp.13873')
        self.assertTrue(all(report['contract_matches'].values()))

    def test_failed_math_and_contract_mismatch_are_visible_without_false_approval(self):
        from intelligence_store.pk_validation_gap import validation_gap_report
        self.source_run()
        with patch('intelligence_store.pk_validation_gap.audit_pk_run',return_value={
            'status':'mathematical_check_failed','method_version':'test-audit','report_sha256':'a'*64}),             patch('intelligence_store.pk_validation_gap.summarize_pk_run',return_value={
            'status':'metrics_withheld','method_version':'test-metrics','report_sha256':'b'*64}):
            report=validation_gap_report(self.run.id)
        gates={g['code']:g for g in report['gates']}
        self.assertEqual(gates['numerical_verification']['status'],'failed')
        self.assertEqual(report['counts']['failed'],1)
        self.assertEqual(report['status'],'clinical_validation_not_established')
        with patch('intelligence_store.pk_validation_gap.CONTRACT_SHA256','0'*64):
            report=validation_gap_report(self.run.id)
        self.assertEqual(report['gates'][0]['status'],'failed')
        self.assertFalse(report['contract_matches']['structure_contract_matches_archive'])

    def test_corrupt_archive_fails_before_planning(self):
        from intelligence_store.pk_validation_gap import validation_gap_report
        from intelligence_store.educational_pk_runs import EducationalPKRun
        self.source_run()
        db.session.execute(update(EducationalPKRun).where(EducationalPKRun.id==self.run.id).values(title='Tampered'));db.session.commit();db.session.expire_all()
        with self.assertRaises(ValueError):validation_gap_report(self.run.id)
        with self.assertRaises(ValueError):validation_gap_report(999)

    def test_cli_json_and_export_match_and_never_overwrite(self):
        from intelligence_store.pk_validation_gap import validation_gap_report,register_pk_validation_gap_commands
        self.source_run();register_pk_validation_gap_commands(self.app)
        runner=self.app.test_cli_runner();args=['patient-pk-validation-gap','--id',str(self.run.id)]
        result=runner.invoke(args=args+['--json']);self.assertEqual(result.exit_code,0,result.output)
        expected=validation_gap_report(self.run.id);self.assertEqual(json.loads(result.output),expected)
        summary=runner.invoke(args=args);self.assertEqual(summary.exit_code,0,summary.output)
        self.assertIn('[PASSED] Numerical implementation verification',summary.output)
        self.assertIn('[BLOCKED] External predictive validation',summary.output)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'gap.json'
            self.assertEqual(runner.invoke(args=args+['--output',str(path)]).exit_code,0)
            original=path.read_bytes();self.assertEqual(json.loads(original),expected)
            self.assertNotEqual(runner.invoke(args=args+['--output',str(path)]).exit_code,0)
            self.assertEqual(path.read_bytes(),original)
        self.assertNotEqual(runner.invoke(args=['patient-pk-validation-gap']).exit_code,0)


if __name__=='__main__':unittest.main()
