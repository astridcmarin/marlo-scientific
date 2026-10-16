"""Revision lineage, retries and integrity preserve prior synthetic inputs."""
import copy
import math
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






from intelligence_store.educational_pk_runs import EducationalPKRun, save_pk_run, export_pk_run

from intelligence_store.educational_pk_audit import audit_pk_run,analytic_state,register_educational_pk_audit_commands

class EducationalPKAuditTests(unittest.TestCase):
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

    def rewrite_report(self,row,change):
        payload=copy.deepcopy(row.payload);report=payload['report'];change(report)
        body=dict(report);body.pop('report_sha256');report['report_sha256']=digest(body)
        payload['identity']['report_sha256']=report['report_sha256']
        db.session.execute(update(EducationalPKRun).where(EducationalPKRun.id==row.id).values(payload=payload,payload_sha256=digest(payload),report_sha256=report['report_sha256'],save_key=digest(payload['identity'])))
        db.session.commit();db.session.expire_all()

    def test_reference_agreement_and_unchanged_archive_without_ode_solver(self):
        self.baseline();row=self.save();before=export_pk_run(row.id)
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No ODE')),patch('socket.socket.connect',side_effect=AssertionError('No network')):
            audit=audit_pk_run(row.id)
        self.assertEqual(audit['status'],'mathematical_checks_passed')
        self.assertTrue(all(c['status']=='passed' for c in audit['checks']))
        self.assertTrue(audit['analytic_reference_evaluated']);self.assertFalse(audit['clinical_prediction_validated'])
        body=dict(audit);sha=body.pop('report_sha256');self.assertEqual(digest(body),sha)
        self.assertEqual(export_pk_run(row.id),before)

    def test_analytic_equal_rate_limit_and_amount_conservation(self):
        events=treatment_request_example()['events'][:1]
        # Independent equal-rate central expression for eight precentral stages.
        for t in (0,.1,1,4):
            s=analytic_state(t,events,10,10,1)
            expected=5*math.exp(-t)*t**8/math.factorial(8)
            self.assertAlmostEqual(s['central_amount_mg'],expected,delta=1e-14)
            self.assertAlmostEqual(sum(s['precentral_amounts_mg'])+s['central_amount_mg']+s['eliminated_amount_mg'],5,delta=1e-14)
        with self.assertRaises(ValueError):analytic_state(1,events,20,10,1)

    def test_alternate_covariate_and_boundary_event_pass(self):
        self.baseline();inputs=model_input_example();inputs['fields']['creatinine_clearance']['value']=45
        request=treatment_request_example();request['horizon']['value']=48
        row=save_pk_run(self.revision.id,inputs,request,'MM')
        audit=audit_pk_run(row.id);self.assertEqual(audit['status'],'mathematical_checks_passed')

    def test_numeric_change_with_valid_payload_hash_fails_mathematical_check(self):
        self.baseline();row=self.save()
        self.rewrite_report(row,lambda r:r['points'][10].update(concentration_ng_ml=r['points'][10]['concentration_ng_ml']+1))
        audit=audit_pk_run(row.id);self.assertEqual(audit['status'],'mathematical_check_failed')
        self.assertEqual(next(c for c in audit['checks'] if c['code']=='analytic_concentration')['status'],'failed')

    def test_unsupported_model_withholds_and_corrupted_hash_rejects(self):
        self.baseline();row=self.save();self.rewrite_report(row,lambda r:r.update(method_version='future-model'))
        self.assertEqual(audit_pk_run(row.id)['status'],'analytic_audit_withheld')
        db.session.execute(update(EducationalPKRun).where(EducationalPKRun.id==row.id).values(title='corrupt'));db.session.commit();db.session.expire_all()
        with self.assertRaises(ValueError):audit_pk_run(row.id)

    def test_page_cli_json_and_safe_exports(self):
        self.baseline();row=self.save();expected=audit_pk_run(row.id);register_educational_pk_audit_commands(self.app)
        path=f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{self.revision.id}/pk-runs/{row.id}/audit'
        response=self.client.get(path);self.assertEqual(response.status_code,200)
        text=response.get_data(as_text=True);self.assertIn('mathematical_checks_passed',text)
        self.assertIn('What remains unestablished',text);self.assertEqual(text.count('class="nav-item active"'),1)
        self.assertEqual(self.client.get(path+'?format=json').get_json(),expected)
        for query in ('?format=xml','?format=json&format=html','?extra=x'):
            self.assertEqual(self.client.get(path+query).status_code,400)
        self.assertEqual(self.client.get(path.replace('/revisions/1/','/revisions/999/')).status_code,404)
        runner=self.app.test_cli_runner();args=['patient-pk-audit','--id',str(row.id)]
        result=runner.invoke(args=args+['--json']);self.assertEqual(result.exit_code,0,result.output)
        self.assertEqual(json.loads(result.stdout),expected)
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'audit.json';result=runner.invoke(args=args+['--output',str(output)])
            self.assertEqual(result.exit_code,0,result.output);before=output.read_bytes()
            self.assertNotEqual(runner.invoke(args=args+['--output',str(output)]).exit_code,0)
            self.assertEqual(output.read_bytes(),before)
        self.rewrite_report(row,lambda r:r.update(method_version='future-model'))
        self.assertEqual(runner.invoke(args=args+['--json']).exit_code,1)
