"""Revision lineage, retries and integrity preserve prior synthetic inputs."""
import copy
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
from intelligence_store.patient_state import digest, state_from_scenario
from intelligence_store.patient_state_revisions import PatientStateRevision, save_revision


from unittest.mock import patch
from intelligence_store.pk_model_inputs import model_input_example
from intelligence_store.patient_model_binding import review_model_binding


from intelligence_store.treatment_requests import (treatment_request_example,validate_treatment_request,
    treatment_request_preview,review_patient_treatment,register_treatment_request_commands)


class PatientTreatmentTests(unittest.TestCase):
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

    def test_explicit_request_removes_missing_blocker_but_does_not_enable_simulation(self):
        self.baseline();r=review_patient_treatment(self.revision.id,model_input_example(),treatment_request_example())
        self.assertEqual(r['status'],'review_required');self.assertFalse(r['ready_for_patient_simulation'])
        self.assertEqual(r['simulation_status'],'not_run');self.assertIsNone(r['predicted_outputs'])
        codes=[b['code'] for b in r['blockers']]
        self.assertNotIn('treatment_request_missing',codes)
        for code in ('applicability_not_established','covariate_provenance_not_verified','treatment_applicability_not_established'):
            self.assertIn(code,codes)
        self.assertEqual(r['treatment_request_preview']['request']['events'][0]['amount']['value'],5)
        self.assertEqual(digest(r['binding']),r['binding_sha256'])
        body=dict(r);sha=body.pop('report_sha256');self.assertEqual(digest(body),sha)
        original=review_model_binding(self.revision.id,model_input_example())
        self.assertEqual(r['model_binding_preview_sha256'],original['report_sha256'])

    def test_request_identity_is_explicit_and_changes_with_timing(self):
        self.baseline();first=treatment_request_example()
        a=review_patient_treatment(self.revision.id,model_input_example(),first)
        changed=copy.deepcopy(first);changed['events'][1]['time']['value']=25
        b=review_patient_treatment(self.revision.id,model_input_example(),changed)
        self.assertNotEqual(a['binding_sha256'],b['binding_sha256'])
        self.assertEqual(a['binding']['state_sha256'],b['binding']['state_sha256'])
        self.assertEqual(a['captured_state'],self.revision.payload['state'])
        self.assertNotEqual(a['treatment_request_preview']['request']['events'][0]['amount']['value'],
                            self.profile.get('dose_value'))

    def test_drug_mismatch_has_no_fallback_and_reads_are_database_immutable(self):
        self.profile={**self.profile,'selected_drug':'bortezomib'}
        self.analysis=analyze_for_save(1,self.profile);self.profile=self.analysis['report']['profile'];self.baseline()
        def snapshot():
            return json.dumps({t.name:[dict(r) for r in db.session.execute(select(t)).mappings()]
                for t in db.metadata.sorted_tables},sort_keys=True,default=str)
        before=snapshot()
        with patch('requests.sessions.Session.request',side_effect=AssertionError('Network')), \
             patch('intelligence_store.transit_kernel.solve_transit',side_effect=AssertionError('Solver')):
            r=review_patient_treatment(self.revision.id,model_input_example(),treatment_request_example())
        self.assertEqual(r['status'],'unsupported_drug');self.assertIsNone(r['standalone_input_preview'])
        self.assertIn('treatment_scenario_drug_mismatch',[b['code'] for b in r['blockers']])
        self.assertEqual(before,snapshot())

    def test_patient_cli_reports_exports_and_never_overwrites(self):
        self.baseline();register_treatment_request_commands(self.app);runner=self.app.test_cli_runner()
        with tempfile.TemporaryDirectory() as tmp:
            cov=Path(tmp)/'inputs.json';req=Path(tmp)/'request.json';out=Path(tmp)/'plan.json'
            cov.write_text(json.dumps(model_input_example()));req.write_text(json.dumps(treatment_request_example()))
            args=['patient-treatment-preview','--revision-id',str(self.revision.id),'--inputs-file',str(cov),'--treatment-file',str(req)]
            r=runner.invoke(args=args+['--json']);self.assertEqual(r.exit_code,0,r.output)
            self.assertEqual(json.loads(r.output),review_patient_treatment(self.revision.id,model_input_example(),treatment_request_example()))
            self.assertEqual(runner.invoke(args=args+['--output',str(out)]).exit_code,0)
            saved=out.read_bytes();self.assertNotEqual(runner.invoke(args=args+['--output',str(out)]).exit_code,0)
            self.assertEqual(saved,out.read_bytes())


class TreatmentRequestTests(unittest.TestCase):
    def test_canonical_provenance_and_zero_time_are_preserved_without_mutation(self):
        raw=treatment_request_example();before=copy.deepcopy(raw)
        canonical=validate_treatment_request(raw)
        self.assertEqual(canonical,raw);self.assertEqual(validate_treatment_request(canonical),canonical)
        self.assertEqual(raw,before);self.assertIsNot(raw,canonical)
        self.assertEqual(canonical['events'][0]['time']['value'],0)
        report=treatment_request_preview(raw)
        self.assertEqual(report['event_count'],3);self.assertEqual(report['total_requested_amount_mg'],15)
        self.assertEqual(report['request_sha256'],digest(canonical))
        body=dict(report);sha=body.pop('report_sha256');self.assertEqual(digest(body),sha)

    def test_route_drug_formulation_units_and_unsupported_fields_rejected(self):
        for field,value in (('route','intravenous'),('drug','bortezomib'),('formulation','solution'),('purpose','clinical')):
            r=treatment_request_example();r[field]=value
            with self.assertRaises(ValueError):validate_treatment_request(r)
        for target,unit in (('time','min'),('amount','mcg')):
            r=treatment_request_example();r['events'][0][target]['unit']=unit
            with self.assertRaises(ValueError):validate_treatment_request(r)
        r=treatment_request_example();r['dose_value']=25
        with self.assertRaises(ValueError):validate_treatment_request(r)

    def test_event_order_duplicates_horizon_and_implementation_budgets(self):
        for events in ([],treatment_request_example()['events'][::-1],
                       [treatment_request_example()['events'][0]]*2,
                       [treatment_request_example()['events'][0]]*21):
            r=treatment_request_example();r['events']=events
            with self.assertRaises(ValueError):validate_treatment_request(r)
        r=treatment_request_example();r['events'][-1]['time']['value']=73
        with self.assertRaises(ValueError):validate_treatment_request(r)
        r=treatment_request_example();r['horizon']['value']=169
        with self.assertRaises(ValueError):validate_treatment_request(r)
        # An event at the horizon is recorded, with no implied post-event exposure.
        r=treatment_request_example();r['events'][-1]['time']['value']=72
        self.assertEqual(validate_treatment_request(r)['events'][-1]['time']['value'],72)

    def test_invalid_numbers_and_unreferenced_assumptions_rejected(self):
        for value in (True,'5',0,-1,float('nan'),float('inf'),10**400):
            r=treatment_request_example();r['events'][0]['amount']['value']=value
            with self.assertRaises(ValueError):validate_treatment_request(r)
        r=treatment_request_example();r['events'][0]['time']['value']=-1
        with self.assertRaises(ValueError):validate_treatment_request(r)
        for target in ('request','event'):
            r=treatment_request_example();p=r if target=='request' else r['events'][0]
            p.update(origin='assumption',source_ref=None)
            with self.assertRaises(ValueError):validate_treatment_request(r)
            p['source_ref']='Explicit invented assumption';validate_treatment_request(r)

    def test_preview_does_not_read_patient_database_catalog_or_network(self):
        with patch('requests.sessions.Session.request',side_effect=AssertionError('Network')), \
             patch('sqlalchemy.engine.Engine.connect',side_effect=AssertionError('DB')), \
             patch('intelligence_store.treatment_requests.review_model_binding',side_effect=AssertionError('Patient')):
            r=treatment_request_preview(treatment_request_example())
        self.assertEqual(r['simulation_status'],'not_run');self.assertFalse(r['ready_for_patient_simulation'])

    def test_standalone_cli_modes_size_duplicate_keys_and_non_overwrite(self):
        app=Flask(__name__);register_treatment_request_commands(app);runner=app.test_cli_runner()
        r=runner.invoke(args=['treatment-request','--example','--json']);self.assertEqual(r.exit_code,0,r.output)
        self.assertEqual(json.loads(r.output),treatment_request_preview(treatment_request_example()))
        self.assertNotEqual(runner.invoke(args=['treatment-request']).exit_code,0)
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'request.json';out=Path(tmp)/'out.json'
            source.write_text(json.dumps(treatment_request_example()))
            args=['treatment-request','--request-file',str(source)]
            self.assertNotEqual(runner.invoke(args=args+['--example']).exit_code,0)
            self.assertEqual(runner.invoke(args=args+['--output',str(out)]).exit_code,0)
            saved=out.read_bytes();self.assertNotEqual(runner.invoke(args=args+['--output',str(out)]).exit_code,0)
            self.assertEqual(saved,out.read_bytes())
            for content in ('{"a":1,"a":2}',' '*65537,'{broken'):
                source.write_text(content);self.assertNotEqual(runner.invoke(args=args).exit_code,0)


if __name__=='__main__':unittest.main()
