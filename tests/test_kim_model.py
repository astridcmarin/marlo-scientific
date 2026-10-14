"""Kim 2026 model: formulas, pinned records, exact two-compartment solution and the typical-value run."""
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest

from intelligence_store.patient_state import digest, state_from_scenario
from intelligence_store.patient_state_revisions import save_revision
from intelligence_store.treatment_requests import treatment_request_example
from intelligence_store.covariate_estimation import (CKD_EPI_2021, DU_BOIS, CovariateEstimationError,
                                                     body_surface_area_du_bois, egfr_ckd_epi_2021,
                                                     load_formula_registry, load_formula_registry_v1)
from intelligence_store.kim_model import (CL_FORMS, calculate_kim_pk, central_amount_unit_dose, estimate_kim_covariates,
                                          load_extract, load_form_assessment, primary_cl_form, typical_parameters)
import test_estimated_pk as base  # module import so the base tests are not collected twice

ROOT = Path(__file__).resolve().parents[1]


def rk4_central(dose, ka, cl, v1, q, v2, horizon, dt=0.0005):
    """Independent numerical reference: depot -> central <-> peripheral, elimination from central."""
    k10, k12, k21 = cl / v1, q / v1, q / v2
    def f(y):
        d, c, p = y
        return (-ka * d, ka * d - (k10 + k12) * c + k21 * p, k12 * c - k21 * p)
    y, t, out = (dose, 0.0, 0.0), 0.0, {}
    steps = round(horizon / dt)
    for i in range(steps + 1):
        if i % round(0.5 / dt) == 0:
            out[round(t, 6)] = y[1]
        a = f(y); b = f(tuple(v + dt / 2 * k for v, k in zip(y, a)))
        c = f(tuple(v + dt / 2 * k for v, k in zip(y, b))); d = f(tuple(v + dt * k for v, k in zip(y, c)))
        y = tuple(v + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4) for v, k1, k2, k3, k4 in zip(y, a, b, c, d))
        t += dt
    return out


class Formulas(unittest.TestCase):
    def test_ckd_epi_2021_worked_examples(self):
        # Published calculators: 60-year-old man, SCr 1.0 mg/dL -> about 86; woman, SCr 0.7 mg/dL -> about 99.
        self.assertAlmostEqual(egfr_ckd_epi_2021(60, 88.4, 'MALE'), 86.2, delta=0.1)
        self.assertAlmostEqual(egfr_ckd_epi_2021(60, 0.7 * 88.4, 'FEMALE'), 99.0, delta=0.1)
        # Independent restatement of the equation for a high-creatinine case.
        scr, kappa, alpha = 3.0, 0.9, -0.302
        expected = 142 * min(scr / kappa, 1) ** alpha * max(scr / kappa, 1) ** -1.2 * 0.9938 ** 70
        self.assertAlmostEqual(egfr_ckd_epi_2021(70, scr * 88.4, 'MALE'), expected, places=10)
        with self.assertRaises(CovariateEstimationError):
            egfr_ckd_epi_2021(16, 80, 'MALE')

    def test_du_bois_worked_example(self):
        self.assertAlmostEqual(body_surface_area_du_bois(70, 175), 1.848, delta=0.002)

    def test_registry_v2_adds_formulas_without_changing_v1(self):
        v1, v2 = load_formula_registry_v1(), load_formula_registry()
        self.assertEqual(v2['registry_version'], 'covariate-formulas-v2.0')
        for name, spec in v1['formulas'].items():
            self.assertEqual(v2['formulas'][name], spec, name)
        self.assertEqual(set(v2['formulas']) - set(v1['formulas']), {'body_surface_area_du_bois', 'egfr_ckd_epi_2021_creatinine'})
        c = v2['formulas']['egfr_ckd_epi_2021_creatinine']['constants']
        self.assertEqual((c['coefficient'], c['age_base'], c['upper_exponent'], c['female_factor']),
                         (CKD_EPI_2021['coefficient'], CKD_EPI_2021['age_base'], CKD_EPI_2021['upper_exponent'], CKD_EPI_2021['female_factor']))
        for sex in ('FEMALE', 'MALE'):
            self.assertEqual((c[sex]['kappa'], c[sex]['alpha']), CKD_EPI_2021[sex])
        d = v2['formulas']['body_surface_area_du_bois']['constants']
        self.assertEqual((d['coefficient'], d['weight_exponent'], d['height_exponent']), DU_BOIS)


class Records(unittest.TestCase):
    def test_extract_and_assessment_are_pinned_and_consistent(self):
        extract, assessment = load_extract(), load_form_assessment()
        self.assertEqual(extract['covariate_equations']['cl_form_assessment'], 'kim_cl_equation_form_assessment_v1.json')
        self.assertEqual(set(extract['covariate_equations']['cl_forms']), set(CL_FORMS))
        self.assertEqual(assessment['status'], 'unresolved')
        self.assertEqual(primary_cl_form(), 'linear_multiplicative')

    def test_assessment_script_reproduces_recorded_results(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'assess_kim_cl_equation_form.py')],
                                capture_output=True, text=True, check=True, timeout=300)
        forms = json.loads(result.stdout)['forms']
        recorded = load_form_assessment()['reconstruction']['results']
        for form, values in recorded.items():
            self.assertEqual(forms[form]['mean_abs_error_pct_points'], values['mean_abs_error_pct_points'])
            self.assertEqual(forms[form]['dose_escalation_raises_pta_as_reported'], values['dose_escalation_raises_pta_as_reported'])


class Parameters(unittest.TestCase):
    def test_reference_covariates_reproduce_table3(self):
        for form in CL_FORMS:
            p = typical_parameters(46.92, 1.64, form)
            self.assertAlmostEqual(p['unbound_clearance_l_h'], 8.52, places=12)
            self.assertAlmostEqual(p['unbound_central_volume_l'], 48.8, places=12)
            self.assertAlmostEqual(p['total_clearance_l_h'], 8.52 * 0.614, places=12)

    def test_forms_differ_only_in_bsa_effect(self):
        lin = typical_parameters(46.92, 2.0, 'linear_multiplicative')['unbound_clearance_l_h']
        exp_ = typical_parameters(46.92, 2.0, 'exponential')['unbound_clearance_l_h']
        add = typical_parameters(46.92, 2.0, 'additive_as_printed')['unbound_clearance_l_h']
        self.assertAlmostEqual(lin, 8.52 * (1 + 1.1 * 0.36), places=10)
        self.assertAlmostEqual(exp_, 8.52 * math.exp(1.1 * 0.36), places=10)
        self.assertAlmostEqual(add, 8.52 + 1.1 * 0.36, places=10)
        with self.assertRaises(ValueError):
            typical_parameters(46.92, 1.64, None)


class ExactSolution(unittest.TestCase):
    def test_matches_numerical_integration(self):
        cases = [(1.16, 8.52, 48.8, 8.05, 21.2), (1.16, 3.0, 40.0, 8.05, 21.2), (0.4, 12.0, 60.0, 2.0, 30.0)]
        for ka, cl, v1, q, v2 in cases:
            reference = rk4_central(1.0, ka, cl, v1, q, v2, horizon=48)
            error = max(abs(central_amount_unit_dose(t, ka, cl, v1, q, v2) - a) for t, a in reference.items())
            self.assertLess(error, 1e-9, (ka, cl))

    def test_near_coincident_rates_are_handled(self):
        cl, v1, q, v2 = 8.52, 48.8, 8.05, 21.2
        k10, k12, k21 = cl / v1, q / v1, q / v2
        s = k10 + k12 + k21
        alpha = (s + math.sqrt(s * s - 4 * k10 * k21)) / 2
        reference = rk4_central(1.0, alpha, cl, v1, q, v2, horizon=24)
        error = max(abs(central_amount_unit_dose(t, alpha, cl, v1, q, v2) - a) for t, a in reference.items())
        self.assertLess(error, 1e-7)

    def test_area_under_unbound_curve_equals_dose_over_clearance(self):
        ka, cl, v1, q, v2 = 1.16, 8.52, 48.8, 8.05, 21.2
        step = 0.01
        area = math.fsum(central_amount_unit_dose(i * step, ka, cl, v1, q, v2) / v1 for i in range(1, 30000)) * step
        self.assertAlmostEqual(area, 1 / cl, delta=1e-4 / cl)


class KimRun(unittest.TestCase):
    setUp = base.EstimatedPKTests.setUp
    tearDown = base.EstimatedPKTests.tearDown
    revision = base.EstimatedPKTests.revision

    def test_estimate_records_formulas_and_coverage(self):
        estimate = estimate_kim_covariates(base.full_state())
        self.assertEqual(estimate['status'], 'estimated')
        self.assertEqual([d['formula_id'] for d in estimate['derivations']], ['egfr_ckd_epi_2021_creatinine', 'body_surface_area_du_bois'])
        self.assertAlmostEqual(estimate['estimates']['egfr_indexed']['value'], egfr_ckd_epi_2021(65, 80, 'FEMALE'), places=12)
        self.assertAlmostEqual(estimate['estimates']['body_surface_area']['value'], body_surface_area_du_bois(70, 165), places=12)
        self.assertTrue(any('Korean' in w for w in estimate['warnings']))
        body = {k: v for k, v in estimate.items() if k != 'report_sha256'}
        self.assertEqual(estimate['report_sha256'], digest(body))

    def test_run_produces_total_and_unbound_curves(self):
        revision = self.revision()
        report = calculate_kim_pk(revision.id, treatment_request_example(), 'MM', 'linear_multiplicative')
        self.assertEqual(report['status'], 'completed')
        self.assertFalse(report['clinical_prediction_validated'])
        self.assertTrue(report['cl_form_evidence']['is_primary_form'])
        for u, t in zip(report['unbound_concentration_ng_ml'], report['total_concentration_ng_ml']):
            self.assertAlmostEqual(t, u / 0.614, places=9)
        dose = sum(e['amount']['value'] for e in treatment_request_example()['events'])
        self.assertAlmostEqual(report['exposure']['total_auc_0_infinity_ng_h_ml'],
                               1000 * dose / report['parameters']['total_clearance_l_h'], places=9)
        self.assertGreater(report['exposure']['terminal_half_life_h'], report['exposure']['distribution_half_life_h'])

    def test_scope_blocks_are_explicit(self):
        revision = self.revision()
        self.assertEqual(calculate_kim_pk(revision.id, treatment_request_example(), 'UNKNOWN', 'exponential')['status'], 'blocked')
        request = treatment_request_example()
        for event in request['events']:
            event['amount']['value'] = 25.0
        blocked = calculate_kim_pk(revision.id, request, 'MM', 'exponential')
        self.assertIn('amount_outside_study', [b['code'] for b in blocked['execution_blockers']])
        with self.assertRaises(ValueError):
            calculate_kim_pk(revision.id, treatment_request_example(), 'MM', None)
        legacy = save_revision(self.scenario.id, state_from_scenario(self.scenario.payload['analysis']['report']['profile']),
                               parent_revision_id=revision.id, title='Legacy')
        missing = calculate_kim_pk(legacy.id, treatment_request_example(), 'MM', 'exponential')
        self.assertIn('missing_estimator_inputs', [b['code'] for b in missing['execution_blockers']])



class ReproductionAndComparison(unittest.TestCase):
    def test_typical_clearance_reproduces_reported_group_means(self):
        from intelligence_store.kim_model import reproduce_group_clearance
        report = reproduce_group_clearance()
        self.assertEqual(report['classification'], 'internal_descriptive_reproduction')
        for group in report['groups']:
            for form, row in group['forms'].items():
                self.assertTrue(row['total_within_one_sd'], (group['group'], form))
                self.assertAlmostEqual(row['typical_total_cl_f'], row['typical_unbound_cl_f'] * 0.614, places=12)
        severe = next(g for g in report['groups'] if g['group'] == 'severe')
        control = next(g for g in report['groups'] if g['group'] == 'control')
        self.assertLess(severe['forms']['linear_multiplicative']['typical_total_cl_f'],
                        control['forms']['linear_multiplicative']['typical_total_cl_f'])

    def test_models_agree_at_normal_and_diverge_at_low_renal_function(self):
        from intelligence_store.kim_model import compare_typical_exposure
        from intelligence_store.patient_state import UNITS, SCHEMA_VERSION
        def state(scr):
            values = dict(age_years=68, biological_sex='FEMALE', weight=70, height=165, serum_creatinine=scr)
            return {'schema_version': SCHEMA_VERSION, 'purpose': 'synthetic_educational',
                    'fields': {k: {'value': v, 'unit': UNITS[k], 'origin': 'synthetic_input', 'observed_at': None,
                                   'source_ref': None} for k, v in values.items()}}
        normal = compare_typical_exposure(state(70), 10)
        severe = compare_typical_exposure(state(180), 10)
        self.assertAlmostEqual(normal['kim_to_hughes_auc_ratio'], 1.0, delta=0.1)
        self.assertGreater(severe['kim_to_hughes_auc_ratio'], 1.4)
        hughes = severe['models']['lenalidomide_hughes_2019']
        self.assertTrue(any('under-predicts' in w for w in hughes['warnings']))
        self.assertEqual(hughes['assumption'], {'weight_basis': 'ideal_body_weight_devine'})
        self.assertEqual(severe['models']['lenalidomide_kim_2026']['assumption'], {'cl_form': 'linear_multiplicative'})
        for model in severe['models'].values():
            self.assertAlmostEqual(model['auc_0_infinity_ng_h_ml'], 10000 / model['typical_total_cl_f_l_h'], places=9)
        body = {k: v for k, v in severe.items() if k != 'report_sha256'}
        self.assertEqual(severe['report_sha256'], digest(body))
        with self.assertRaises(ValueError):
            compare_typical_exposure(state(70), 0)

if __name__ == '__main__':
    unittest.main()
