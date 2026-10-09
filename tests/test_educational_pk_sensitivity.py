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


class EducationalPKSensitivityTests(unittest.TestCase):
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

    def archived(self):
        self.baseline()
        from intelligence_store.educational_pk_runs import save_pk_run
        return save_pk_run(self.revision.id,model_input_example(),treatment_request_example(),'MM',title='Sensitivity source')

    def test_unit_factor_reproduces_source_math_without_solver_or_changes(self):
        from intelligence_store.educational_pk_sensitivity import clearance_sensitivity
        from intelligence_store.educational_pk_runs import export_pk_run
        row=self.archived();before=export_pk_run(row.id)
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No ODE')),             patch('socket.socket.connect',side_effect=AssertionError('No network')):
            report=clearance_sensitivity(row.id,1,'Invented identity check')
        self.assertEqual(report['status'],'sensitivity_available')
        self.assertEqual(report['parameters']['archived'],report['parameters']['perturbed'])
        self.assertEqual(report['summaries']['window_auc_ratio'],1)
        self.assertEqual(report['summaries']['infinity_auc_ratio'],1)
        for point in report['points']:
            self.assertEqual(point['analytic_baseline_concentration_ng_ml'],point['perturbed_concentration_ng_ml'])
            self.assertAlmostEqual(point['archived_concentration_ng_ml'],point['analytic_baseline_concentration_ng_ml'],delta=5e-7)
        self.assertEqual(export_pk_run(row.id),before)
        self.assertFalse(report['clinical_prediction_validated'])
        self.assertFalse(report['uncertainty_interval_estimated'])
        self.assertFalse(report['patient_covariates_changed'])
        self.assertEqual(digest({k:v for k,v in report.items() if k!='report_sha256'}),report['report_sha256'])

    def test_clearance_factors_have_reciprocal_infinity_auc_with_fixed_inputs(self):
        from intelligence_store.educational_pk_sensitivity import clearance_sensitivity
        row=self.archived()
        for factor in (0.5,0.8,1.25,2):
            report=clearance_sensitivity(row.id,factor,'Invented mathematical factor')
            s=report['summaries'];p=report['parameters']
            self.assertAlmostEqual(s['infinity_auc_ratio'],1/factor)
            self.assertEqual(p['archived']['apparent_volume_l'],p['perturbed']['apparent_volume_l'])
            self.assertEqual(p['archived']['transit_rate_h'],p['perturbed']['transit_rate_h'])
            self.assertEqual(p['perturbed']['elimination_rate_h'],p['perturbed']['apparent_clearance_l_h']/p['perturbed']['apparent_volume_l'])
            # The finite-window ratio need not equal the infinity ratio.
            self.assertNotEqual(s['window_auc_ratio'],s['infinity_auc_ratio'])
            if factor<1:self.assertGreater(s['window_auc_ratio'],1)
            else:self.assertLess(s['window_auc_ratio'],1)

        # Independent numerical RK4 check at a changed clearance, including repeated-event superposition.
        from intelligence_store.transit_kernel import solve_transit
        report=clearance_sensitivity(row.id,0.5,'Invented independent numerical check')
        p=report['parameters']['perturbed']
        unit=solve_transit(dose_mg=1,volume_l=p['apparent_volume_l'],clearance_l_h=p['apparent_clearance_l_h'],
            transit_rate_h=p['transit_rate_h'],stages=8,horizon_h=72,display_step_h=0.1,max_step_h=0.001)
        events=report['request']['events']
        for index in (1,10,240,241,480,491,720):
            point=report['points'][index]
            concentration=0;auc=0
            for event in events:
                lag=index-round(event['time']['value']*10)
                if lag>=0:
                    concentration+=event['amount']['value']*unit['points'][lag]['concentration_ng_ml']
                    auc+=event['amount']['value']*unit['points'][lag]['auc_0_t_ng_h_ml']
            self.assertAlmostEqual(point['perturbed_concentration_ng_ml'],concentration,delta=5e-7)
            self.assertAlmostEqual(point['perturbed_auc_0_t_ng_h_ml'],auc,delta=5e-5)

    def test_explicit_factors_notes_and_software_bounds(self):
        from intelligence_store.educational_pk_sensitivity import clearance_sensitivity
        for factor in (True,'1',None,float('nan'),float('inf'),0,0.49,2.01,10**1000):
            with self.subTest(factor=str(factor)[:20]):
                with self.assertRaises(ValueError):clearance_sensitivity(1,factor,'Invented')
        for note in ('',' ',None,'x'*1001):
            with self.assertRaises(ValueError):clearance_sensitivity(1,1,note)

    def test_failed_audit_withholds_and_bad_source_is_not_bypassed(self):
        from intelligence_store.educational_pk_sensitivity import clearance_sensitivity
        from intelligence_store.educational_pk_runs import EducationalPKRun
        row=self.archived()
        with patch('intelligence_store.educational_pk_sensitivity.audit_pk_run',return_value={
            'method_version':'test','report_sha256':'f'*64,'status':'mathematical_check_failed'}):
            r=clearance_sensitivity(row.id,0.8,'Invented factor')
        self.assertEqual(r['status'],'sensitivity_withheld');self.assertIsNone(r['points']);self.assertIsNone(r['parameters'])
        db.session.execute(update(EducationalPKRun).where(EducationalPKRun.id==row.id).values(title='Tampered'));db.session.commit();db.session.expire_all()
        with self.assertRaises(ValueError):clearance_sensitivity(row.id,0.8,'Invented factor')

    def test_cli_json_exports_are_deterministic_and_never_overwrite(self):
        from intelligence_store.educational_pk_sensitivity import clearance_sensitivity,register_educational_pk_sensitivity_commands
        row=self.archived();register_educational_pk_sensitivity_commands(self.app)
        args=['patient-pk-sensitivity','--id',str(row.id),'--clearance-factor','0.8','--assumption-note','Invented CLI example']
        runner=self.app.test_cli_runner()
        result=runner.invoke(args=args+['--json']);self.assertEqual(result.exit_code,0,result.output)
        expected=clearance_sensitivity(row.id,0.8,'Invented CLI example')
        self.assertEqual(json.loads(result.output),expected)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'sensitivity.json'
            first=runner.invoke(args=args+['--output',str(path)]);self.assertEqual(first.exit_code,0,first.output)
            original=path.read_bytes()
            second=runner.invoke(args=args+['--output',str(path)]);self.assertNotEqual(second.exit_code,0)
            self.assertEqual(path.read_bytes(),original)
            self.assertEqual(json.loads(original),expected)
        self.assertNotEqual(runner.invoke(args=['patient-pk-sensitivity','--id',str(row.id),'--clearance-factor','0.8']).exit_code,0)


if __name__=='__main__':unittest.main()
