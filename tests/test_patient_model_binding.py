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


class PatientModelBindingTests(unittest.TestCase):
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

    def test_additional_covariates_are_associated_without_replacing_unknown_state(self):
        self.baseline();report=review_model_binding(self.revision.id,model_input_example())
        self.assertEqual(report['status'],'review_required')
        self.assertEqual(report['consistency_checks'][0]['status'],'additional_explicit_input')
        self.assertIsNone(report['captured_state']['fields']['creatinine_clearance']['value'])
        self.assertEqual(report['explicit_model_inputs']['fields']['creatinine_clearance']['value'],90)
        self.assertEqual(report['standalone_input_preview']['status'],'parameter_preview_available')
        self.assertFalse(report['ready_for_patient_simulation']);self.assertIsNone(report['predicted_outputs'])
        self.assertEqual(report['simulation_status'],'not_run')
        self.assertIn('treatment_request_missing',[b['code'] for b in report['blockers']])

    def test_matching_values_keep_separate_provenance_and_review_blockers(self):
        state=example_state();state['fields']['creatinine_clearance'].update(value=90,origin='synthetic_input')
        self.baseline(state)
        report=review_model_binding(self.revision.id,model_input_example())
        self.assertEqual(report['consistency_checks'][0]['status'],'value_matches_provenance_separate')
        self.assertEqual(report['conflicts'],[])
        self.assertIn('covariate_provenance_not_verified',[b['code'] for b in report['blockers']])
        self.assertNotEqual(report['consistency_checks'][0]['saved_input'],report['consistency_checks'][0]['explicit_input'])

    def test_conflicting_crcl_is_preserved_and_blocks_association(self):
        state=example_state();state['fields']['creatinine_clearance'].update(value=45,origin='synthetic_input')
        self.baseline(state)
        report=review_model_binding(self.revision.id,model_input_example())
        self.assertEqual(report['status'],'binding_conflict')
        self.assertIn('creatinine_clearance_value_conflict',report['conflicts'])
        self.assertEqual(report['captured_state']['fields']['creatinine_clearance']['value'],45)
        self.assertEqual(report['explicit_model_inputs']['fields']['creatinine_clearance']['value'],90)
        self.assertEqual(read_revision(self.revision.id).payload['state']['fields']['creatinine_clearance']['value'],45)

    def test_ffm_total_weight_consistency_never_derives_ffm(self):
        state=example_state();state['fields']['weight']['value']=40
        self.baseline(state)
        report=review_model_binding(self.revision.id,model_input_example())
        self.assertIn('fat_free_mass_exceeds_recorded_weight',report['conflicts'])
        self.assertEqual(report['explicit_model_inputs']['fields']['fat_free_mass']['value'],55)
        self.assertEqual(report['captured_state']['fields']['weight']['value'],40)

    def test_missing_and_outside_inputs_are_preserved_with_no_parameter_preview(self):
        self.baseline()
        inputs=model_input_example();inputs['fields']={}
        r=review_model_binding(self.revision.id,inputs)
        self.assertIsNone(r['standalone_input_preview']['parameter_preview'])
        self.assertIn('missing_inputs',[b['code'] for b in r['blockers']])
        inputs=model_input_example();inputs['fields']['creatinine_clearance']['value']=250
        r=review_model_binding(self.revision.id,inputs)
        self.assertIsNone(r['standalone_input_preview']['parameter_preview'])
        self.assertIn('outside_reference_range',[b['code'] for b in r['blockers']])

    def test_unsupported_drug_never_substitutes_model_or_computes_parameters(self):
        self.profile={**self.profile,'selected_drug':'bortezomib'}
        self.analysis=analyze_for_save(1,self.profile)
        self.profile=self.analysis['report']['profile'];self.baseline()
        with patch('intelligence_store.patient_model_binding.preview_model_inputs',side_effect=AssertionError('No fallback')):
            report=review_model_binding(self.revision.id,model_input_example())
        self.assertEqual(report['status'],'unsupported_drug');self.assertIsNone(report['standalone_input_preview'])
        self.assertIn('unsupported_drug',[b['code'] for b in report['blockers']])

    def test_binding_identity_is_revision_specific_and_integrity_is_verified(self):
        self.baseline();first=review_model_binding(self.revision.id,model_input_example())
        body=dict(first);sha=body.pop('report_sha256');self.assertEqual(digest(body),sha)
        self.assertEqual(digest(first['binding']),first['binding_sha256'])
        self.assertEqual(first,review_model_binding(self.revision.id,model_input_example()))
        second=save_revision(self.scenario.id,self.base,parent_revision_id=self.revision.id,title='Second revision')
        later=review_model_binding(second.id,model_input_example())
        self.assertNotEqual(first['binding_sha256'],later['binding_sha256'])
        changed=copy.deepcopy(self.revision.payload);changed['title']='Tampered'
        db.session.execute(update(PatientStateRevision).where(PatientStateRevision.id==self.revision.id).values(payload=changed))
        db.session.commit();db.session.expire_all()
        with self.assertRaises(ValueError):review_model_binding(self.revision.id,model_input_example())
        with self.assertRaises(ValueError):review_model_binding(second.id,model_input_example())

    def test_read_only_no_network_solver_and_missing_ids_fail(self):
        self.baseline()
        # Datetimes need canonical string encoding for the table snapshot.
        def snapshot():
            return json.dumps({t.name:[dict(r) for r in db.session.execute(select(t)).mappings()]
                               for t in db.metadata.sorted_tables},sort_keys=True,default=str)
        before=snapshot()
        with patch('requests.sessions.Session.request',side_effect=AssertionError('Network')), \
             patch('intelligence_store.transit_kernel.solve_transit',side_effect=AssertionError('Solver')):
            review_model_binding(self.revision.id,model_input_example())
        self.assertEqual(before,snapshot());self.assertEqual(list(db.session.dirty),[])
        for bad in (True,0,-1,'1',999):
            with self.assertRaises(ValueError):review_model_binding(bad,model_input_example())

    def test_cli_export_json_bounds_and_no_overwrite(self):
        self.baseline();register_patient_model_binding_commands(self.app);runner=self.app.test_cli_runner()
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'inputs.json';out=Path(tmp)/'binding.json'
            source.write_text(json.dumps(model_input_example()))
            args=['patient-model-bind-preview','--revision-id',str(self.revision.id),'--inputs-file',str(source)]
            result=runner.invoke(args=args+['--json']);self.assertEqual(result.exit_code,0,result.output)
            self.assertEqual(json.loads(result.output),review_model_binding(self.revision.id,model_input_example()))
            self.assertEqual(runner.invoke(args=args+['--output',str(out)]).exit_code,0)
            saved=out.read_bytes();self.assertNotEqual(runner.invoke(args=args+['--output',str(out)]).exit_code,0)
            self.assertEqual(saved,out.read_bytes())
            for invalid in ('{"a":1,"a":2}',' '*65537):
                source.write_text(invalid);self.assertNotEqual(runner.invoke(args=args).exit_code,0)


if __name__=='__main__':unittest.main()
