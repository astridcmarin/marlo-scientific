"""Patient Lab 2.0d: estimated covariates drive the educational calculation and are archived with runs."""
import copy
from datetime import datetime
import json
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
from intelligence_store.patient_state_revisions import PatientStateRevision, save_revision, export_revision
from intelligence_store.treatment_requests import treatment_request_example
from intelligence_store.covariate_estimation import WEIGHT_BASES, estimate_hughes_covariates, to_hughes_model_inputs
from intelligence_store.estimated_pk import (calculate_estimated_pk, compare_estimated_pk, compare_published_models,
                                             estimate_for_revision, primary_weight_basis, PREDICTION_TYPE,
                                             register_estimated_pk_commands)
from intelligence_store.kim_model import calculate_kim_pk
from intelligence_store.educational_pk_runs import (EducationalPKRun, SCHEMA, SCHEMA_V2, export_pk_run, read_pk_run,
                                                    save_estimated_pk_run, save_pk_run)
from intelligence_store.pk_model_inputs import model_input_example


def full_state(**overrides):
    values = dict(age_years=65, biological_sex='FEMALE', weight=70, height=165, serum_creatinine=80)
    values.update(overrides)
    fields = {name: {'value': value, 'unit': UNITS[name], 'origin': 'synthetic_input', 'observed_at': None,
                     'source_ref': None} for name, value in values.items()}
    return {'schema_version': STATE_SCHEMA, 'purpose': 'synthetic_educational', 'fields': fields}


class EstimatedPKTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite://', INTELLIGENCE_WORKSPACE_SECRET='web-test-secret-40')
        app.add_url_rule('/', 'home', lambda: 'Home')
        from landscape_ui import register_landscape
        register_landscape(app)
        self.app = app
        self.client = app.test_client()
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
        db.session.add(CohortTrial(cohort_id=1, nct_id=snap.nct_id, snapshot_id=snap.id))
        db.session.commit()
        profile = load_scenario_presets()['index']['interaction-reference']['profile']
        analysis = analyze_for_save(1, profile)
        self.scenario = save_scenario('Invented profile', 1, analysis['report']['profile'], digest(analysis), 'a' * 64)

    def tearDown(self):
        db.session.rollback()
        db.session.execute(delete(EducationalPKRun))
        db.session.commit()
        if inspect(db.engine).has_table(PatientStateRevision.__tablename__):
            ids = list(db.session.scalars(select(PatientStateRevision.id).order_by(PatientStateRevision.revision_number.desc())))
            for item in ids:
                db.session.execute(delete(PatientStateRevision).where(PatientStateRevision.id == item))
            db.session.commit()
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def revision(self, state=None, title='Estimated baseline'):
        return save_revision(self.scenario.id, state or full_state(), title=title)

    # ------------------------------------------------------------ calculation

    def test_estimate_drives_calculation_with_provenance(self):
        revision = self.revision()
        before = export_revision(revision.id)
        result = calculate_estimated_pk(revision.id, 'ideal_body_weight_devine', treatment_request_example(), 'MM')
        self.assertEqual(result['status'], 'completed_educational_calculation')
        self.assertEqual(result['prediction_type'], PREDICTION_TYPE)
        self.assertFalse(result['clinical_prediction_validated'])
        self.assertFalse(result['ready_for_patient_simulation'])
        estimate = result['covariate_estimate']
        self.assertEqual(estimate, estimate_hughes_covariates(full_state(), 'ideal_body_weight_devine'))
        self.assertEqual(estimate['state_sha256'], revision.state_sha256)
        review = result['calculation']['preflight_review']
        self.assertEqual(review['explicit_model_inputs'], to_hughes_model_inputs(estimate))
        crcl = estimate['estimates']['creatinine_clearance']['value']
        ffm = estimate['estimates']['fat_free_mass']['value']
        expected_cl = 12.0 * (ffm / 55) ** 0.75 * (crcl / 90) ** 0.224
        self.assertAlmostEqual(result['calculation']['parameters']['apparent_clearance_l_h'], expected_cl, places=10)
        body = {k: v for k, v in result.items() if k != 'report_sha256'}
        self.assertEqual(result['report_sha256'], digest(body))
        self.assertEqual(export_revision(revision.id), before)

    def test_weight_basis_changes_exposure_through_clearance_only(self):
        revision = self.revision(full_state(weight=110))
        ideal = calculate_estimated_pk(revision.id, 'ideal_body_weight_devine', treatment_request_example(), 'MM')
        total = calculate_estimated_pk(revision.id, 'total_body_weight', treatment_request_example(), 'MM')
        crcl_ratio = (total['covariate_estimate']['estimates']['creatinine_clearance']['value']
                      / ideal['covariate_estimate']['estimates']['creatinine_clearance']['value'])
        auc_ratio = (ideal['calculation']['analytic_auc_0_infinity_ng_h_ml']
                     / total['calculation']['analytic_auc_0_infinity_ng_h_ml'])
        self.assertAlmostEqual(auc_ratio, crcl_ratio ** 0.224, places=10)
        self.assertEqual(ideal['calculation']['parameters']['apparent_volume_l'],
                         total['calculation']['parameters']['apparent_volume_l'])

    def test_missing_estimator_inputs_never_calculate_or_save(self):
        legacy = state_from_scenario(self.scenario.payload['analysis']['report']['profile'])
        revision = self.revision(legacy, 'Legacy without height or creatinine')
        with patch('intelligence_store.estimated_pk.calculate_educational_pk', side_effect=AssertionError('No calculation')):
            result = calculate_estimated_pk(revision.id, 'ideal_body_weight_devine', treatment_request_example(), 'MM')
        self.assertEqual(result['status'], 'missing_estimator_inputs')
        self.assertIsNone(result['calculation'])
        self.assertEqual(set(result['covariate_estimate']['missing_fields']), {'height', 'serum_creatinine'})
        with self.assertRaisesRegex(ValueError, 'missing estimator inputs'):
            save_estimated_pk_run(revision.id, 'ideal_body_weight_devine', treatment_request_example(), 'MM')
        self.assertEqual(db.session.scalars(select(EducationalPKRun)).all(), [])

    def test_declared_crcl_conflict_blocks_and_stays_visible(self):
        state = full_state()
        state['fields']['creatinine_clearance'] = {'value': 200.0, 'unit': 'mL/min', 'origin': 'synthetic_input',
                                                    'observed_at': None, 'source_ref': None}
        revision = self.revision(state)
        result = calculate_estimated_pk(revision.id, 'ideal_body_weight_devine', treatment_request_example(), 'MM')
        self.assertEqual(result['status'], 'blocked_educational_calculation')
        self.assertIsNone(result['calculation']['points'])
        self.assertIn('neither replaces the other', ' '.join(result['covariate_estimate']['warnings']))

    def test_unknown_basis_and_missing_revision_are_rejected(self):
        revision = self.revision()
        with self.assertRaises(ValueError):
            calculate_estimated_pk(revision.id, 'lean_body_weight', treatment_request_example(), 'MM')
        with self.assertRaisesRegex(ValueError, 'does not exist'):
            estimate_for_revision(999, 'ideal_body_weight_devine')

    def test_comparison_runs_every_basis(self):
        revision = self.revision(full_state(weight=110))
        comparison = compare_estimated_pk(revision.id, treatment_request_example(), 'MM')
        self.assertEqual([r['weight_basis'] for r in comparison['rows']], list(WEIGHT_BASES))
        spread = comparison['spread']
        self.assertGreater(spread['crcl_max_to_min_ratio'], 1.0)
        self.assertLess(spread['auc_max_to_min_ratio'], spread['crcl_max_to_min_ratio'])
        self.assertEqual(primary_weight_basis(), 'ideal_body_weight_devine')

    # ------------------------------------------------------------ published-model comparison

    def request_mg(self, amount):
        request = treatment_request_example()
        for event in request['events']:
            event['amount']['value'] = amount
        return request

    def test_model_comparison_matches_each_model_run_alone(self):
        revision = self.revision(full_state(serum_creatinine=120))
        request = self.request_mg(7.5)
        models = compare_published_models(revision.id, 'ideal_body_weight_devine', 'linear_multiplicative', request, 'MM')
        hughes, kim = models['rows']
        self.assertEqual(hughes['report_sha256'], calculate_estimated_pk(revision.id, 'ideal_body_weight_devine', request, 'MM')['report_sha256'])
        self.assertEqual(kim['report_sha256'], calculate_kim_pk(revision.id, request, 'MM', 'linear_multiplicative')['report_sha256'])
        self.assertEqual({round(t, 6) for t in hughes['times_h']}, {round(t, 6) for t in kim['times_h']})
        self.assertGreater(models['ratio']['kim_to_hughes_auc_0_infinity'], 1.3)
        self.assertTrue(any('under-predicts' in w for w in hughes['warnings']))
        for row in (hughes, kim):
            ref = row['reference_exposure']
            self.assertEqual(ref['daily_dose_mg'], 7.5)
            self.assertAlmostEqual(ref['typical_daily_auc_ng_h_ml'], row['auc_0_infinity_ng_h_ml'] / len(request['events']), places=6)
            self.assertAlmostEqual(ref['ratio_to_reference'], ref['typical_daily_auc_ng_h_ml'] / 2181, places=12)
        self.assertFalse(models['clinical_prediction_validated'])
        body = {k: v for k, v in models.items() if k != 'report_sha256'}
        self.assertEqual(models['report_sha256'], digest(body))

    def test_model_comparison_blocks_rather_than_substitutes(self):
        revision = self.revision()
        only_hughes = compare_published_models(revision.id, 'ideal_body_weight_devine', 'linear_multiplicative', self.request_mg(25), 'MM')
        self.assertEqual(only_hughes['rows'][0]['status'], 'completed_educational_calculation')
        self.assertEqual([b['code'] for b in only_hughes['rows'][1]['blockers']], ['amount_outside_study'])
        self.assertIn('reference_exposure', only_hughes['rows'][0])
        self.assertNotIn('reference_exposure', only_hughes['rows'][1])
        self.assertIsNone(only_hughes['ratio'])
        only_kim = compare_published_models(revision.id, 'ideal_body_weight_devine', 'linear_multiplicative', self.request_mg(10), 'MM')
        self.assertNotIn('times_h', only_kim['rows'][0])
        self.assertIn('times_h', only_kim['rows'][1])
        not_mm = compare_published_models(revision.id, 'ideal_body_weight_devine', 'linear_multiplicative', self.request_mg(5), 'CLL')
        self.assertIn('disease_context_outside_study', [b['code'] for b in not_mm['rows'][1]['blockers']])
        with self.assertRaises(ValueError):
            compare_published_models(revision.id, 'ideal_body_weight_devine', 'printed', self.request_mg(5), 'MM')
        severe = save_revision(self.scenario.id, full_state(serum_creatinine=180), parent_revision_id=revision.id, title='Severe')
        below = compare_published_models(severe.id, 'ideal_body_weight_devine', 'linear_multiplicative', self.request_mg(5), 'MM')
        self.assertLess(below['rows'][0]['covariates']['creatinine_clearance'], 36)
        self.assertIn('outside_context_range', [b['code'] for b in below['rows'][0]['blockers']])
        self.assertEqual(below['rows'][1]['status'], 'completed')

    def test_page_compares_models_and_keeps_the_form_explicit(self):
        revision = self.revision(full_state(serum_creatinine=120))
        text = self.client.get(self.page(revision)).get_data(as_text=True)
        self.assertIn('value="linear_multiplicative" selected', text)
        self.assertIn('primary reading', text)
        text = self.client.post(self.page(revision), data=self.form(revision, 'models', events='0, 7.5')).get_data(as_text=True)
        self.assertIn('Published-model comparison', text)
        self.assertIn('Concentration by published model', text)
        self.assertIn('Kim/Hughes AUC to infinity', text)
        self.assertIn('Typical daily AUC ÷ reference', text)
        self.assertIn('It is not a target, limit, toxicity prediction or dose recommendation.', text)
        text = self.client.post(self.page(revision), data=self.form(revision, 'models')).get_data(as_text=True)
        self.assertIn('Not run — amount_outside_study', text)
        bad = self.form(revision, 'models')
        bad['cl_form'] = 'printed'
        self.assertEqual(self.client.post(self.page(revision), data=bad).status_code, 400)
        bad = self.form(revision, 'models')
        del bad['cl_form']
        self.assertEqual(self.client.post(self.page(revision), data=bad).status_code, 400)

    # ------------------------------------------------------------ saved runs

    def test_saved_v2_run_archives_and_verifies_estimate(self):
        revision = self.revision()
        row = save_estimated_pk_run(revision.id, 'ideal_body_weight_devine', treatment_request_example(), 'MM',
                                    title='Estimated run')
        self.assertEqual(row.schema_version, SCHEMA_V2)
        again = save_estimated_pk_run(revision.id, 'ideal_body_weight_devine', treatment_request_example(), 'MM',
                                      title='Estimated run')
        self.assertEqual(row.id, again.id)
        with patch('intelligence_store.educational_pk_runs.calculate_estimated_pk', side_effect=AssertionError('No rerun')):
            payload = export_pk_run(row.id)['payload']
        self.assertEqual(payload['weight_basis'], 'ideal_body_weight_devine')
        self.assertEqual(payload['covariate_estimate']['state_sha256'], revision.state_sha256)
        self.assertEqual(payload['report']['preflight_review']['explicit_model_inputs'],
                         to_hughes_model_inputs(payload['covariate_estimate']))
        other = save_estimated_pk_run(revision.id, 'total_body_weight', treatment_request_example(), 'MM',
                                      title='Estimated run')
        self.assertNotEqual(other.id, row.id)

    def test_v1_runs_are_unchanged(self):
        revision = self.revision()
        row = save_pk_run(revision.id, model_input_example(), treatment_request_example(), 'MM')
        self.assertEqual(row.schema_version, SCHEMA)
        self.assertNotIn('covariate_estimate', read_pk_run(row.id).payload)

    def test_tampered_estimate_or_basis_is_detected(self):
        revision = self.revision()
        row = save_estimated_pk_run(revision.id, 'ideal_body_weight_devine', treatment_request_example(), 'MM')
        original = copy.deepcopy(read_pk_run(row.id).payload)
        for change in ('estimate', 'basis'):
            payload = copy.deepcopy(original)
            if change == 'estimate':
                payload['covariate_estimate']['estimates']['creatinine_clearance']['value'] += 1
            else:
                payload['weight_basis'] = 'total_body_weight'
            db.session.execute(update(EducationalPKRun).where(EducationalPKRun.id == row.id).values(
                payload=payload, payload_sha256=digest(payload)))
            db.session.commit()
            db.session.expire_all()
            with self.assertRaises(ValueError):
                read_pk_run(row.id)

    def test_cli_requires_explicit_basis(self):
        import tempfile
        from pathlib import Path
        revision = self.revision()
        register_estimated_pk_commands(self.app)
        runner = self.app.test_cli_runner()
        with tempfile.TemporaryDirectory() as tmp:
            request = Path(tmp) / 'request.json'
            request.write_text(json.dumps(treatment_request_example()))
            base = ['patient-pk-estimated', '--revision-id', str(revision.id), '--treatment-file', str(request), '--disease-code', 'MM']
            self.assertNotEqual(runner.invoke(args=base).exit_code, 0)
            result = runner.invoke(args=base + ['--weight-basis', 'ideal_body_weight_devine'])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(json.loads(result.output)['status'], 'completed_educational_calculation')

    # ------------------------------------------------------------ pages

    def page(self, revision):
        return f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{revision.id}/estimated-pk'

    def form(self, revision, action='calculate', **values):
        text = self.client.get(self.page(revision)).get_data(as_text=True)
        token = re.search(r'name="form_token" value="([^"]+)"', text).group(1)
        data = {'form_token': token, 'action': action, 'weight_basis': 'ideal_body_weight_devine',
                'cl_form': 'linear_multiplicative', 'disease': 'MM',
                'horizon': '24', 'events': '0, 25', 'source_ref': 'Invented request for page test'}
        data.update(values)
        return data

    def test_page_preselects_primary_assumption_and_shows_estimate(self):
        revision = self.revision()
        with patch('intelligence_store.estimated_pk.calculate_educational_pk', side_effect=AssertionError('No GET run')):
            response = self.client.get(self.page(revision))
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        self.assertIn('value="ideal_body_weight_devine" selected', text)
        self.assertIn('primary assumption', text)
        self.assertIn('creatinine_clearance_cockcroft_gault', text)
        self.assertIn('Not a clinical prediction', text)

    def test_page_calculate_compare_download_and_save(self):
        revision = self.revision()
        text = self.client.post(self.page(revision), data=self.form(revision)).get_data(as_text=True)
        self.assertIn('Educational calculation completed', text)
        self.assertIn('typical_value_for_declared_covariates', text)
        text = self.client.post(self.page(revision), data=self.form(revision, 'compare')).get_data(as_text=True)
        self.assertIn('Weight-basis comparison', text)
        self.assertIn('Central concentration by weight basis', text)
        download = self.client.post(self.page(revision), data=self.form(revision, 'download'))
        self.assertEqual(download.get_json()['schema_version'], 'estimated-educational-pk-v1')
        saved = self.client.post(self.page(revision), data=self.form(revision, 'save', title='Saved from page'))
        self.assertEqual(saved.status_code, 303)
        run = db.session.scalar(select(EducationalPKRun))
        self.assertEqual(run.schema_version, SCHEMA_V2)
        page = self.client.get(saved.headers['Location']).get_data(as_text=True)
        self.assertIn('Why these covariates?', page)

    def test_page_missing_inputs_and_strict_forms(self):
        legacy = state_from_scenario(self.scenario.payload['analysis']['report']['profile'])
        revision = self.revision(legacy, 'Legacy')
        text = self.client.get(self.page(revision)).get_data(as_text=True)
        self.assertIn('missing estimator inputs', text)
        bad = self.form(revision)
        bad['weight_basis'] = 'lean_body_weight'
        self.assertEqual(self.client.post(self.page(revision), data=bad).status_code, 400)
        bad = self.form(revision)
        bad['form_token'] = 'bad'
        self.assertNotEqual(self.client.post(self.page(revision), data=bad).status_code, 200)
        self.assertEqual(self.client.get(self.page(revision) + '?x=1').status_code, 400)


if __name__ == '__main__':
    unittest.main()
