"""Patient Lab 2.1f: immutable saved Kim 2026 runs."""
import copy
from datetime import datetime
import re
import unittest
from unittest.mock import patch

from flask import Flask
from sqlalchemy import delete, inspect, select, update

from intelligence_store.extensions import db
from intelligence_store.models import AnalysisCohort, CohortTrial, TrialSnapshot
from intelligence_store.patient_scenarios import load_scenario_presets
from intelligence_store.saved_scenarios import analyze_for_save, save_scenario
from intelligence_store.patient_state import UNITS, SCHEMA_VERSION as STATE_SCHEMA, digest, state_from_scenario
from intelligence_store.patient_state_revisions import PatientStateRevision, save_revision
from intelligence_store.treatment_requests import treatment_request_example
from intelligence_store.kim_pk_runs import (SCHEMA, KimPKRun, export_kim_pk_run, read_kim_pk_run, save_kim_pk_run)


def full_state(**overrides):
    values = dict(age_years=65, biological_sex='FEMALE', weight=70, height=165, serum_creatinine=80)
    values.update(overrides)
    return {'schema_version': STATE_SCHEMA, 'purpose': 'synthetic_educational',
            'fields': {name: {'value': value, 'unit': UNITS[name], 'origin': 'synthetic_input', 'observed_at': None,
                              'source_ref': None} for name, value in values.items()}}


def request_mg(amount):
    request = treatment_request_example()
    for event in request['events']:
        event['amount']['value'] = amount
    return request


class KimPKRunTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite://', INTELLIGENCE_WORKSPACE_SECRET='web-test-secret-40')
        app.add_url_rule('/', 'home', lambda: 'Home')
        from landscape_ui import register_landscape
        register_landscape(app)
        self.client = app.test_client()
        db.init_app(app)
        self.context = app.app_context()
        self.context.push()
        db.create_all()
        db.session.add(AnalysisCohort(id=1, condition='Synthetic example', api_url='https://clinicaltrials.gov/api/v2/studies',
            query_params={'query.cond': 'Example'}, query_version='qa-v1', normalization_version='qa-v1', scope='all-studies',
            max_pages=1, status='COMPLETE', expected_count=1, retrieved_count=1, pages_fetched=1, page_log=[],
            finished_at_utc=datetime(2026, 10, 7)))
        raw = {'protocolSection': {'identificationModule': {'nctId': 'NCT00000001', 'briefTitle': 'Frozen title'},
            'statusModule': {'overallStatus': 'RECRUITING'}, 'designModule': {'studyType': 'INTERVENTIONAL'},
            'armsInterventionsModule': {'interventions': [{'type': 'DRUG', 'name': 'Lenalidomide'}]},
            'eligibilityModule': {'minimumAge': '18 Years', 'maximumAge': '80 Years', 'sex': 'ALL'}}}
        snap = TrialSnapshot(nct_id='NCT00000001', source_url='https://clinicaltrials.gov/study/NCT00000001', raw_study=raw)
        db.session.add(snap)
        db.session.flush()
        db.session.add(CohortTrial(cohort_id=1, nct_id=snap.nct_id, snapshot_id=snap.id))
        db.session.commit()
        profile = load_scenario_presets()['index']['interaction-reference']['profile']
        analysis = analyze_for_save(1, profile)
        self.scenario = save_scenario('Invented profile', 1, analysis['report']['profile'], digest(analysis), 'a' * 64)
        self.revision = save_revision(self.scenario.id, full_state(serum_creatinine=180), title='Severe synthetic')

    def tearDown(self):
        db.session.rollback()
        db.session.execute(delete(KimPKRun))
        db.session.commit()
        if inspect(db.engine).has_table(PatientStateRevision.__tablename__):
            ids = list(db.session.scalars(select(PatientStateRevision.id).order_by(PatientStateRevision.revision_number.desc())))
            for item in ids:
                db.session.execute(delete(PatientStateRevision).where(PatientStateRevision.id == item))
            db.session.commit()
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def save(self, **kw):
        args = dict(request=request_mg(5.0), disease_code='MM', cl_form='linear_multiplicative', title='Kim run')
        args.update(kw)
        return save_kim_pk_run(self.revision.id, args['request'], args['disease_code'], args['cl_form'], title=args['title'])

    def test_saved_run_archives_estimate_assumption_and_warnings(self):
        row = self.save()
        self.assertEqual(row.schema_version, SCHEMA)
        self.assertEqual(self.save().id, row.id)
        with patch('intelligence_store.kim_pk_runs.calculate_kim_pk', side_effect=AssertionError('No rerun')):
            payload = export_kim_pk_run(row.id)['payload']
        report = payload['report']
        self.assertEqual(payload['cl_form'], 'linear_multiplicative')
        self.assertEqual(report['covariate_estimate']['state_sha256'], self.revision.state_sha256)
        self.assertTrue(report['cl_form_evidence']['is_primary_form'])
        self.assertTrue(any('may under-predict' in w for w in report['covariate_estimate']['warnings']))
        self.assertFalse(report['clinical_prediction_validated'])
        other = self.save(cl_form='exponential')
        self.assertNotEqual(other.id, row.id)

    def test_blocked_or_incomplete_runs_are_not_saved(self):
        for kw, code in ((dict(request=request_mg(25.0)), 'amount_outside_study'),
                         (dict(disease_code='CLL'), 'disease_context_outside_study')):
            with self.assertRaisesRegex(ValueError, code):
                self.save(**kw)
        legacy = state_from_scenario(self.scenario.payload['analysis']['report']['profile'])
        bare = save_revision(self.scenario.id, legacy, parent_revision_id=self.revision.id, title='Legacy')
        with self.assertRaisesRegex(ValueError, 'missing_estimator_inputs'):
            save_kim_pk_run(bare.id, request_mg(5.0), 'MM', 'linear_multiplicative')
        with self.assertRaises(ValueError):
            self.save(cl_form='printed')
        self.assertEqual(db.session.scalars(select(KimPKRun)).all(), [])

    def test_tampering_is_detected(self):
        row = self.save()
        original = copy.deepcopy(read_kim_pk_run(row.id).payload)
        changes = {
            'cl_form': lambda p: p.update(cl_form='exponential'),
            'estimate': lambda p: p['report']['covariate_estimate']['estimates']['egfr_indexed'].update(value=60.0),
            'curve': lambda p: p['report']['total_concentration_ng_ml'].__setitem__(5, 1.0),
            'validation_flag': lambda p: p['report'].update(clinical_prediction_validated=True)}
        for name, change in changes.items():
            payload = copy.deepcopy(original)
            change(payload)
            db.session.execute(update(KimPKRun).where(KimPKRun.id == row.id).values(payload=payload, payload_sha256=digest(payload)))
            db.session.commit()
            db.session.expire_all()
            with self.assertRaises(ValueError, msg=name):
                read_kim_pk_run(row.id)

    def page(self):
        return f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{self.revision.id}/estimated-pk'

    def test_page_saves_and_shows_a_verified_run(self):
        text = self.client.get(self.page()).get_data(as_text=True)
        token = re.search(r'name="form_token" value="([^"]+)"', text).group(1)
        data = {'form_token': token, 'action': 'save_kim', 'weight_basis': 'ideal_body_weight_devine',
                'cl_form': 'linear_multiplicative', 'disease': 'MM', 'horizon': '24', 'events': '0, 5',
                'source_ref': 'Invented request for page test', 'title': 'Kim from page'}
        saved = self.client.post(self.page(), data=data)
        self.assertEqual(saved.status_code, 303)
        view = self.client.get(saved.headers['Location']).get_data(as_text=True)
        for expected in ('Kim from page', 'linear multiplicative', 'Run record', 'may under-predict',
                         'Clinical prediction validated: <strong>false</strong>', 'the model is not re-run'):
            self.assertIn(expected, view)
        exported = self.client.get(saved.headers['Location'] + '?format=json')
        self.assertEqual(exported.get_json()['payload']['schema_version'], SCHEMA)
        run_id = saved.headers['Location'].rsplit('/', 1)[1]
        other = save_revision(self.scenario.id, full_state(), parent_revision_id=self.revision.id, title='Other')
        wrong = f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{other.id}/kim-runs/{run_id}'
        self.assertEqual(self.client.get(wrong).status_code, 404)
        blocked = dict(data, form_token=re.search(r'name="form_token" value="([^"]+)"',
                       self.client.get(self.page()).get_data(as_text=True)).group(1), events='0, 25')
        response = self.client.post(self.page(), data=blocked)
        self.assertEqual(response.status_code, 400)
        self.assertIn('amount_outside_study', response.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
