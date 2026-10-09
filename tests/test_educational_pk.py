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


class EducationalPKTests(unittest.TestCase):
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

    def run_example(self,request=None,inputs=None,disease='MM'):
        return calculate_educational_pk(self.revision.id,inputs or model_input_example(),
                                       request or treatment_request_example(),disease)

    def test_completed_calculation_retains_unknown_context_and_clinical_blockers(self):
        self.baseline();r=self.run_example()
        self.assertEqual(r['status'],'completed_educational_calculation')
        self.assertFalse(r['clinical_prediction_validated']);self.assertFalse(r['ready_for_patient_simulation'])
        self.assertEqual(len(r['points']),721)
        self.assertIn('serum_creatinine',r['preflight_review']['unknown_context_fields'])
        self.assertIn('applicability_not_established',[b['code'] for b in r['clinical_review_blockers']])
        self.assertEqual(r['preflight_review']['captured_state'],self.revision.payload['state'])
        body=dict(r);sha=body.pop('report_sha256');self.assertEqual(digest(body),sha)

    def test_concentrations_match_independent_analytic_eight_stage_superposition(self):
        self.baseline();r=self.run_example()
        def single(t):
            if t<=0:return 0.0
            k=13.5;ke=12/68.8;x=(k-ke)*t
            if x<10:
                term=x**8/math.factorial(8);total=term
                for j in range(9,200):
                    term*=x/j;total+=term
                    if term<1e-17*total:break
                tail=math.exp(-x)*total
            else:tail=1-math.exp(-x)*sum(x**j/math.factorial(j) for j in range(8))
            return 1000/68.8*(k/(k-ke))**8*math.exp(-ke*t)*tail
        for p in r['points']:
            expected=5*sum(single(p['time_h']-t) for t in (0,24,48))
            self.assertAlmostEqual(p['concentration_ng_ml'],expected,delta=5e-8)

    def test_mass_and_event_continuity_and_auc_limit(self):
        self.baseline();r=self.run_example()
        states=r['points']+[e[k] for e in r['event_boundaries'] for k in ('before','after')]
        for s in states:
            self.assertAlmostEqual(math.fsum(s['precentral_amounts_mg']+[s['central_amount_mg'],s['eliminated_amount_mg']]),
                                   s['cumulative_requested_amount_mg'],delta=1e-11)
        for event in r['event_boundaries']:
            before,after=event['before'],event['after']
            self.assertAlmostEqual(after['precentral_amounts_mg'][0]-before['precentral_amounts_mg'][0],5)
            self.assertEqual(before['concentration_ng_ml'],after['concentration_ng_ml'])
            self.assertEqual(before['auc_0_t_ng_h_ml'],after['auc_0_t_ng_h_ml'])
        self.assertEqual(r['analytic_auc_0_infinity_ng_h_ml'],1250)
        self.assertLess(r['auc_0_horizon_ng_h_ml'],1250)
        self.assertGreater(r['auc_0_horizon_ng_h_ml'],1200)

    def test_linearity_for_listed_amounts(self):
        self.baseline();a=self.run_example();request=treatment_request_example()
        for e in request['events']:e['amount']['value']=15
        b=self.run_example(request)
        self.assertAlmostEqual(b['auc_0_horizon_ng_h_ml'],3*a['auc_0_horizon_ng_h_ml'],delta=1e-9)
        for p,q in zip(a['points'],b['points']):
            self.assertAlmostEqual(q['concentration_ng_ml'],3*p['concentration_ng_ml'],delta=1e-10)

    def test_scope_rejections_never_run_solver(self):
        self.baseline()
        for change,code in ((lambda r:r['events'][0]['time'].update(value=.1),'initial_event_time'),
                            (lambda r:r['events'][1]['time'].update(value=25),'interval_outside_execution_scope'),
                            (lambda r:r['horizon'].update(value=73),'execution_budget'),
                            (lambda r:r['horizon'].update(value=71.05),'unsupported_time_grid'),
                            (lambda r:r['events'][0]['amount'].update(value=10),'amount_outside_execution_scope')):
            request=treatment_request_example();change(request)
            with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('Blocked solver')):
                r=self.run_example(request)
            self.assertEqual(r['status'],'blocked_educational_calculation');self.assertIsNone(r['points'])
            self.assertIn(code,[b['code'] for b in r['execution_blockers']])
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('Blocked solver')):
            r=self.run_example(disease='UNKNOWN')
        self.assertEqual(r['simulation_status'],'not_run')

    def test_age_and_covariate_missing_or_conflict_block_execution(self):
        state=example_state();state['fields']['age_years'].update(value=None,origin='unknown')
        self.baseline(state)
        r=self.run_example();self.assertIn('age_context_missing',[b['code'] for b in r['execution_blockers']])
        inputs=model_input_example();inputs['fields']={}
        r=self.run_example(inputs=inputs)
        self.assertIn('parameters_unavailable',[b['code'] for b in r['execution_blockers']])
        self.assertIsNone(r['points'])

    def test_no_network_database_write_and_changed_policy_fails_closed(self):
        self.baseline()
        def snapshot():
            return json.dumps({t.name:[dict(r) for r in db.session.execute(select(t)).mappings()]
                for t in db.metadata.sorted_tables},sort_keys=True,default=str)
        before=snapshot()
        with patch('requests.sessions.Session.request',side_effect=AssertionError('Network')):self.run_example()
        self.assertEqual(before,snapshot());self.assertEqual(list(db.session.dirty),[])
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'contract.json'
            with self.assertRaises(ValueError):load_execution_contract(p)
            p.write_text('{}')
            with self.assertRaises(ValueError):load_execution_contract(p)

    def test_cli_json_export_and_non_overwrite(self):
        self.baseline();register_educational_pk_commands(self.app);runner=self.app.test_cli_runner()
        with tempfile.TemporaryDirectory() as tmp:
            cov=Path(tmp)/'inputs.json';req=Path(tmp)/'request.json';out=Path(tmp)/'pk.json'
            cov.write_text(json.dumps(model_input_example()));req.write_text(json.dumps(treatment_request_example()))
            args=['patient-pk-educational','--revision-id',str(self.revision.id),'--inputs-file',str(cov),'--treatment-file',str(req),'--disease-code','MM']
            r=runner.invoke(args=args+['--json']);self.assertEqual(r.exit_code,0,r.output)
            self.assertEqual(json.loads(r.output),self.run_example())
            self.assertEqual(runner.invoke(args=args+['--output',str(out)]).exit_code,0)
            saved=out.read_bytes();self.assertNotEqual(runner.invoke(args=args+['--output',str(out)]).exit_code,0)
            self.assertEqual(saved,out.read_bytes())


if __name__=='__main__':unittest.main()
