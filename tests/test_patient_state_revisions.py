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


class PatientStateRevisionTests(unittest.TestCase):
    def setUp(self):
            app = Flask(__name__)
            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
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

    def test_append_retains_source_and_prior_states_and_duplicate_retries(self):
        scenario=self.save_scenario();before=copy.deepcopy(scenario.payload)
        state=state_from_scenario(scenario.payload['analysis']['report']['profile'])
        first=save_revision(scenario.id,state,title='Baseline')
        captured=export_revision(first.id)
        second_state=copy.deepcopy(state)
        second_state['fields']['height'].update(value=165,origin='synthetic_input')
        second=save_revision(scenario.id,second_state,parent_revision_id=first.id,title='Height added')
        self.assertEqual(second.revision_number,2)
        self.assertEqual(second.payload['parent_payload_sha256'],first.payload_sha256)
        self.assertEqual(export_revision(first.id),captured)
        self.assertEqual(scenario.payload,before)
        self.assertEqual(save_revision(scenario.id,state,title='Baseline').id,first.id)
        self.assertEqual(save_revision(scenario.id,second_state,parent_revision_id=first.id,title='Height added').id,second.id)
        self.assertEqual(db.session.query(PatientStateRevision).count(),2)
        exported=export_revision(second.id);exported['payload']['state']['fields']['height']['value']=99
        self.assertEqual(export_revision(second.id)['payload']['state']['fields']['height']['value'],165)

    def test_stale_parent_cannot_branch_or_replace_latest(self):
        scenario=self.save_scenario();state=example_state();first=save_revision(scenario.id,state)
        second=save_revision(scenario.id,state,parent_revision_id=first.id)
        altered=copy.deepcopy(state);altered['fields']['weight']['value']=71
        for parent in [None,first.id]:
            with self.subTest(parent=parent),self.assertRaisesRegex(ValueError,'Stale parent'):
                save_revision(scenario.id,altered,parent_revision_id=parent)
        self.assertEqual(db.session.query(PatientStateRevision).count(),2)
        self.assertEqual(read_revision(second.id).state_sha256,digest(state))

    def test_missing_and_cross_scenario_parent_are_rejected(self):
        scenario=self.save_scenario();first=save_revision(scenario.id,example_state())
        other=self.save_scenario(key='b')
        with self.assertRaises(ValueError):save_revision(other.id,example_state(),parent_revision_id=first.id)
        with self.assertRaises(ValueError):save_revision(99999,example_state())
        with self.assertRaises(ValueError):read_revision(True)
        self.assertIsNone(read_revision(99999))
        self.assertEqual(db.session.query(PatientStateRevision).count(),1)

    def test_orm_updates_and_deletes_are_blocked(self):
        scenario=self.save_scenario();row=save_revision(scenario.id,example_state());row_id=row.id
        row.title='Changed'
        with self.assertRaisesRegex(ValueError,'cannot be updated'):db.session.commit()
        db.session.rollback();row=read_revision(row_id)
        db.session.delete(row)
        with self.assertRaisesRegex(ValueError,'cannot be updated'):db.session.commit()
        db.session.rollback();self.assertEqual(read_revision(row_id).title,'Patient state')

    def test_tampered_ancestor_is_detected_by_descendant_and_platform_check(self):
        scenario=self.save_scenario();first=save_revision(scenario.id,example_state())
        second=save_revision(scenario.id,example_state(),parent_revision_id=first.id)
        first_id,second_id=first.id,second.id
        # Bulk SQL bypasses ORM hooks deliberately to exercise read-time checks.
        db.session.execute(update(PatientStateRevision).where(PatientStateRevision.id==first_id).values(title='Changed'))
        db.session.commit();db.session.expire_all()
        with self.assertRaisesRegex(ValueError,'integrity'):export_revision(second_id)
        report=validate_platform(1);self.assertEqual(report['status'],'failed')
        check=next(c for c in report['checks'] if c['key']=='patient_states')
        self.assertEqual(check['status'],'failed')

    def test_invalid_state_is_not_written_and_empty_table_passes(self):
        scenario=self.save_scenario();state=example_state();state['fields']['weight']['unit']='lb'
        with self.assertRaises(ValueError):save_revision(scenario.id,state)
        self.assertEqual(db.session.query(PatientStateRevision).count(),0)
        check=next(c for c in validate_platform(1)['checks'] if c['key']=='patient_states')
        self.assertEqual(check['status'],'passed')

    def test_cli_save_list_export_and_retry_from_existing_scenario(self):
        scenario=self.save_scenario();register_patient_state_revision_commands(current_app)
        runner=current_app.test_cli_runner()
        args=['patient-state-save','--scenario-id',str(scenario.id)]
        result=runner.invoke(args=args);self.assertEqual(result.exit_code,0,result.output)
        self.assertEqual(runner.invoke(args=args).exit_code,0)
        row=db.session.scalar(select(PatientStateRevision));self.assertEqual(row.revision_number,1)
        listed=runner.invoke(args=['patient-state-list','--scenario-id',str(scenario.id)])
        self.assertEqual(listed.exit_code,0,listed.output);self.assertIn('1 patient-state revisions',listed.output)
        exported=runner.invoke(args=['patient-state-export','--id',str(row.id)])
        self.assertEqual(exported.exit_code,0,exported.output)
        self.assertEqual(json.loads(exported.output),export_revision(row.id))
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'state.json';p.write_text(json.dumps(example_state()))
            result=runner.invoke(args=['patient-state-save','--scenario-id',str(scenario.id),
                '--parent-id',str(row.id),'--state-file',str(p)])
            self.assertEqual(result.exit_code,0,result.output)
        self.assertEqual(db.session.query(PatientStateRevision).count(),2)

    def test_missing_table_fails_without_automatic_creation(self):
        scenario=self.save_scenario();PatientStateRevision.__table__.drop(db.engine)
        with self.assertRaisesRegex(ValueError,'migration'):save_revision(scenario.id,example_state())

    def test_database_constraint_prevents_duplicate_revision_number(self):
        scenario=self.save_scenario();row=save_revision(scenario.id,example_state());row_id=row.id
        values={c.name:copy.deepcopy(getattr(row,c.name)) for c in PatientStateRevision.__table__.columns if c.name!='id'}
        values['save_key']='f'*64
        db.session.add(PatientStateRevision(**values))
        with self.assertRaises(IntegrityError):db.session.commit()
        db.session.rollback();self.assertIsNotNone(read_revision(row_id))

    def test_changed_scenario_anchor_is_detected_even_with_new_scenario_digest(self):
        scenario=self.save_scenario();row=save_revision(scenario.id,example_state());row_id=row.id
        payload=copy.deepcopy(scenario.payload);payload['scope_note']='Changed source context'
        scenario.payload=payload;scenario.payload_sha256=digest(payload);db.session.commit()
        with self.assertRaisesRegex(ValueError,'source anchor'):export_revision(row_id)


if __name__=='__main__':unittest.main()
