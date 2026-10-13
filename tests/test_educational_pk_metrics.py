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

from intelligence_store.educational_pk_metrics import summarize_pk_run,sampled_peak,register_educational_pk_metrics_commands
from intelligence_store.educational_pk_audit import analytic_state

class EducationalPKMetricsTests(unittest.TestCase):
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

    def test_archived_peak_and_finer_analytic_grid_preserve_source(self):
        self.baseline();row=self.save();before=export_pk_run(row.id);r=summarize_pk_run(row.id);peak=r['sampled_peak']
        self.assertEqual(r['status'],'sampled_metrics_available');self.assertFalse(r['continuous_peak_estimated'])
        self.assertEqual(peak['sample_count'],721);self.assertEqual(peak['sampling_step_h'],.1)
        self.assertEqual(peak['first_time_h'],49.1);self.assertFalse(peak['maximum_on_window_boundary'])
        archive=row.payload['report'];p=archive['parameters'];events=archive['preflight_review']['treatment_request_preview']['request']['events']
        refined=[(i/100,analytic_state(i/100,events,p['apparent_clearance_l_h'],p['apparent_volume_l'],p['transit_rate_h'])['concentration_ng_ml']) for i in range(7201)]
        time,value=max(refined,key=lambda x:x[1])
        self.assertGreaterEqual(value,peak['concentration_ng_ml']-1e-7)
        self.assertLess(value-peak['concentration_ng_ml'],.1)
        self.assertLessEqual(abs(time-peak['first_time_h']),.1)
        self.assertEqual(export_pk_run(row.id),before)
        body=dict(r);sha=body.pop('report_sha256');self.assertEqual(digest(body),sha)

    def test_ties_boundaries_and_nonuniform_grid_policy(self):
        points=[{'time_h':i,'concentration_ng_ml':v} for i,v in enumerate((0,2,2,1))]
        peak=sampled_peak(points);self.assertEqual(peak['equal_maximum_times_h'],[1,2])
        self.assertEqual(peak['first_time_h'],1);self.assertFalse(peak['maximum_on_window_boundary'])
        points[-1]['concentration_ng_ml']=2;self.assertTrue(sampled_peak(points)['maximum_on_window_boundary'])
        points[-1]['time_h']=3.1;self.assertIsNone(sampled_peak(points))
        self.assertIsNone(sampled_peak(points[:1]));points[1]['concentration_ng_ml']=float('nan')
        self.assertIsNone(sampled_peak(points))

    def test_short_window_boundary_is_explicit(self):
        self.baseline();request=treatment_request_example();request['events']=request['events'][:1];request['horizon']['value']=.1
        row=save_pk_run(self.revision.id,model_input_example(),request,'MM')
        r=summarize_pk_run(row.id);self.assertEqual(r['status'],'sampled_metrics_available')
        self.assertTrue(r['sampled_peak']['maximum_on_window_boundary']);self.assertEqual(r['sampled_peak']['first_time_h'],.1)
        self.assertFalse(r['continuous_peak_estimated'])

    def test_amount_linearity_preserves_sampled_peak_time(self):
        self.baseline();a=self.save();request=treatment_request_example()
        for event in request['events']:event['amount']['value']=15
        b=save_pk_run(self.revision.id,model_input_example(),request,'MM',title='Threefold requested amounts')
        x=summarize_pk_run(a.id)['sampled_peak'];y=summarize_pk_run(b.id)['sampled_peak']
        self.assertAlmostEqual(y['concentration_ng_ml'],3*x['concentration_ng_ml'],delta=1e-10)
        self.assertEqual(y['first_time_h'],x['first_time_h'])

    def test_failed_audit_withholds_metrics(self):
        self.baseline();row=self.save();payload=copy.deepcopy(row.payload);report=payload['report']
        report['points'][10]['concentration_ng_ml']+=1
        body=dict(report);body.pop('report_sha256');report['report_sha256']=digest(body)
        payload['identity']['report_sha256']=report['report_sha256']
        db.session.execute(update(EducationalPKRun).where(EducationalPKRun.id==row.id).values(payload=payload,payload_sha256=digest(payload),report_sha256=report['report_sha256'],save_key=digest(payload['identity'])))
        db.session.commit();db.session.expire_all()
        result=summarize_pk_run(row.id);self.assertEqual(result['status'],'metrics_withheld')
        self.assertIsNone(result['sampled_peak']);self.assertIsNone(result['exposure'])

    def test_page_cli_json_safe_export_and_no_ode(self):
        self.baseline();row=self.save();expected=summarize_pk_run(row.id);register_educational_pk_metrics_commands(self.app)
        path=f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{self.revision.id}/pk-runs/{row.id}/metrics'
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No ODE')),patch('socket.socket.connect',side_effect=AssertionError('No network')):
            response=self.client.get(path);self.assertEqual(response.status_code,200)
            text=response.get_data(as_text=True);self.assertIn('Sampled maximum concentration',text)
            self.assertIn('not presented as exact continuous Cmax or Tmax',text)
            self.assertEqual(text.count('class="nav-item active"'),1)
            self.assertEqual(self.client.get(path+'?format=json').get_json(),expected)
            runner=self.app.test_cli_runner();args=['patient-pk-metrics','--id',str(row.id)]
            result=runner.invoke(args=args+['--json']);self.assertEqual(result.exit_code,0,result.output)
            self.assertEqual(json.loads(result.output),expected)
            with tempfile.TemporaryDirectory() as directory:
                output=Path(directory)/'metrics.json';result=runner.invoke(args=args+['--output',str(output)])
                self.assertEqual(result.exit_code,0,result.output);before=output.read_bytes()
                self.assertNotEqual(runner.invoke(args=args+['--output',str(output)]).exit_code,0)
                self.assertEqual(output.read_bytes(),before)
        for query in ('?extra=x','?format=xml','?format=json&format=html'):
            self.assertEqual(self.client.get(path+query).status_code,400)
        self.assertEqual(self.client.get(path.replace('/revisions/1/','/revisions/999/')).status_code,404)
