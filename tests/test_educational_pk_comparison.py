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
from intelligence_store.patient_state_revisions import PatientStateRevision, save_revision


from unittest.mock import patch
from intelligence_store.pk_model_inputs import model_input_example


from intelligence_store.treatment_requests import treatment_request_example






from intelligence_store.educational_pk_runs import EducationalPKRun, save_pk_run, export_pk_run

from intelligence_store.educational_pk_comparison import compare_pk_runs,register_educational_pk_comparison_commands

class EducationalPKComparisonTests(unittest.TestCase):
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

    def pair(self):
        self.baseline();a=self.save('Left reference')
        inputs=model_input_example();inputs['fields']['creatinine_clearance']['value']=45
        b=save_pk_run(self.revision.id,inputs,treatment_request_example(),'MM',title='Right synthetic CrCl')
        return a,b

    def compare(self,a,b):return compare_pk_runs(a.id,b.id,revision_id=self.revision.id)

    def test_compatible_comparison_arithmetic_and_source_integrity(self):
        a,b=self.pair();before=(export_pk_run(a.id),export_pk_run(b.id))
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No solver')):
            r=self.compare(a,b)
        self.assertEqual(r['status'],'compatible_educational_comparison');self.assertEqual(len(r['points']),721)
        self.assertAlmostEqual(r['exposure_difference']['auc_right_minus_left_ng_h_ml'],b.payload['report']['auc_0_horizon_ng_h_ml']-a.payload['report']['auc_0_horizon_ng_h_ml'])
        for point,x,y in zip(r['points'],a.payload['report']['points'],b.payload['report']['points']):
            self.assertEqual(point['difference_ng_ml'],y['concentration_ng_ml']-x['concentration_ng_ml'])
        changes={c['field']:c for c in r['covariate_changes']}
        self.assertTrue(changes['creatinine_clearance']['value_changed']);self.assertFalse(changes['fat_free_mass']['value_changed'])
        self.assertFalse(r['treatment_request_changed']);self.assertFalse(r['clinical_prediction_validated'])
        body=dict(r);sha=body.pop('report_sha256');self.assertEqual(digest(body),sha)
        self.assertEqual((export_pk_run(a.id),export_pk_run(b.id)),before)

    def test_identical_run_zero_difference_and_direction(self):
        a,b=self.pair();r=self.compare(a,a)
        self.assertEqual(r['exposure_difference']['auc_right_minus_left_ng_h_ml'],0)
        self.assertTrue(all(p['difference_ng_ml']==0 for p in r['points']))
        x=self.compare(a,b);y=self.compare(b,a)
        self.assertEqual(x['exposure_difference']['auc_right_minus_left_ng_h_ml'],-y['exposure_difference']['auc_right_minus_left_ng_h_ml'])

    def test_different_time_grid_and_disease_withhold_numerical_comparison(self):
        a,b=self.pair();request=treatment_request_example();request['horizon']['value']=48
        short=save_pk_run(self.revision.id,model_input_example(),request,'MM',title='Short window')
        other=save_pk_run(self.revision.id,model_input_example(),treatment_request_example(),'CLL',title='Other disease')
        for row,code in ((short,'time_grid'),(other,'declared_disease_code')):
            r=self.compare(a,row);self.assertEqual(r['status'],'comparison_withheld')
            self.assertIsNone(r['points']);self.assertIsNone(r['exposure_difference'])
            self.assertFalse(next(c for c in r['compatibility_checks'] if c['code']==code)['matches'])

    def test_model_contract_difference_withholds_and_corruption_rejected(self):
        a,b=self.pair();payload=copy.deepcopy(b.payload);report=payload['report'];report['execution_contract_sha256']='0'*64
        body=dict(report);body.pop('report_sha256');report['report_sha256']=digest(body)
        payload['identity']['report_sha256']=report['report_sha256']
        db.session.execute(update(EducationalPKRun).where(EducationalPKRun.id==b.id).values(payload=payload,payload_sha256=digest(payload),report_sha256=report['report_sha256'],save_key=digest(payload['identity'])))
        db.session.commit();db.session.expire_all()
        self.assertEqual(self.compare(a,b)['status'],'comparison_withheld')
        db.session.execute(update(EducationalPKRun).where(EducationalPKRun.id==b.id).values(title='Corrupt'));db.session.commit();db.session.expire_all()
        with self.assertRaises(ValueError):self.compare(a,b)

    def test_page_json_and_strict_context_checks(self):
        a,b=self.pair();path=f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{self.revision.id}/pk-runs/compare'
        self.assertEqual(self.client.get(path).status_code,200)
        with patch('socket.socket.connect',side_effect=AssertionError('No network')),patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No solver')):
            response=self.client.get(path+f'?left={a.id}&right={b.id}');self.assertEqual(response.status_code,200)
            text=response.get_data(as_text=True);self.assertIn('Compatible educational comparison',text)
            self.assertEqual(text.count('<polyline '),2);self.assertEqual(text.count('class="nav-item active"'),1)
            response=self.client.get(path+f'?left={a.id}&right={b.id}&format=json')
            self.assertEqual(response.get_json(),self.compare(a,b));self.assertEqual(response.headers['Cache-Control'],'no-store')
        for query in ('?left=1','?left=1&right=0','?left=1&right=1&left=2','?extra=x','?format=json'):
            self.assertEqual(self.client.get(path+query).status_code,400)
        with self.assertRaises(ValueError):compare_pk_runs(a.id,b.id,revision_id=999)
        with self.assertRaises(ValueError):compare_pk_runs(a.id,999,revision_id=self.revision.id)

    def test_cli_json_and_never_overwrite(self):
        a,b=self.pair();register_educational_pk_comparison_commands(self.app)
        args=['patient-pk-compare','--revision-id',str(self.revision.id),'--left',str(a.id),'--right',str(b.id)]
        runner=self.app.test_cli_runner();result=runner.invoke(args=args+['--json'])
        self.assertEqual(result.exit_code,0,result.output);self.assertEqual(json.loads(result.output),self.compare(a,b))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'compare.json';result=runner.invoke(args=args+['--output',str(path)])
            self.assertEqual(result.exit_code,0,result.output);before=path.read_bytes()
            self.assertNotEqual(runner.invoke(args=args+['--output',str(path)]).exit_code,0)
            self.assertEqual(path.read_bytes(),before)
