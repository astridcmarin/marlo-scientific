"""Patient Lab 2.0e: exact transit solution, seeded random effects and the population band."""
import json
import math
from pathlib import Path
import statistics
import tempfile
import unittest

from intelligence_store.transit_kernel import solve_transit
from intelligence_store.treatment_requests import treatment_request_example
from intelligence_store.covariate_estimation import load_variability_extract
from intelligence_store.patient_state import digest, state_from_scenario
from intelligence_store.population_pk import (DEFAULT_SEED, _percentile, calculate_population_pk,
                                              central_amount_unit_dose, register_population_pk_commands,
                                              sample_random_effects, _diagnostics)
import test_estimated_pk as base  # module import so the base tests are not collected twice

OMEGA = load_variability_extract()['random_effects']['omega_matrix']


class ExactTransitSolution(unittest.TestCase):
    def test_matches_numerical_solver_in_every_regime(self):
        cases = [(13.5, 12.0 / 68.8), (2.0, 2.0 * (1 - 2e-7)), (2.0, 2.0), (0.6, 1.5), (40.0, 0.05)]
        for ktr, k in cases:
            volume = 10.0
            ref = solve_transit(dose_mg=1.0, volume_l=volume, clearance_l_h=k * volume, transit_rate_h=ktr, stages=8,
                                horizon_h=48, display_step_h=0.1, max_step_h=0.0005)
            error = max(abs(central_amount_unit_dose(p['time_h'], ktr, k, 8) - p['central_amount_mg'])
                        for p in ref['points'])
            self.assertLess(error, 1e-9, (ktr, k))

    def test_branch_boundary_is_continuous_and_mass_is_conserved(self):
        ktr, k = 13.5, 0.17
        t = 50 / (ktr - k)
        below, above = central_amount_unit_dose(t * (1 - 1e-12), ktr, k, 8), central_amount_unit_dose(t * (1 + 1e-12), ktr, k, 8)
        self.assertAlmostEqual(below, above, places=10)
        # The integral of central amount for a unit dose equals 1/k.
        step = 0.01
        area = math.fsum(central_amount_unit_dose(i * step, ktr, k, 8) for i in range(1, 30000)) * step
        self.assertAlmostEqual(area, 1 / k, delta=1e-3 / k)


class RandomEffects(unittest.TestCase):
    def test_draws_are_seeded_and_reproduce_omega(self):
        a = sample_random_effects(200, 7, OMEGA)
        self.assertEqual(a, sample_random_effects(200, 7, OMEGA))
        self.assertNotEqual(a, sample_random_effects(200, 8, OMEGA))
        diag = _diagnostics(sample_random_effects(40000, DEFAULT_SEED, OMEGA), OMEGA)
        for key in ('omega_cl', 'omega_v', 'omega_ktr'):
            self.assertAlmostEqual(diag['sampled'][key], diag['specified'][key], delta=0.03 * diag['specified'][key])
        self.assertAlmostEqual(diag['sampled']['corr_cl_v'], 0.862, delta=0.01)

    def test_invalid_omega_is_refused(self):
        with self.assertRaises(ValueError):
            sample_random_effects(10, 1, [[0.1, 0.5, 0], [0.5, 0.1, 0], [0, 0, 0.1]])
        with self.assertRaises(ValueError):
            sample_random_effects(10, 1, [[0.3, 0.2, 0.1], [0.2, 0.3, 0], [0.1, 0, 0.3]])

    def test_percentile_matches_standard_inclusive_method(self):
        values = sorted([3.1, 0.2, 9.7, 4.4, 5.0, 2.2, 8.8])
        expected = statistics.quantiles(values, n=20, method='inclusive')
        self.assertAlmostEqual(_percentile(values, 5), expected[0], places=12)
        self.assertAlmostEqual(_percentile(values, 95), expected[-1], places=12)
        self.assertEqual(_percentile(values, 50), statistics.median(values))


class PopulationBand(unittest.TestCase):
    setUp = base.EstimatedPKTests.setUp
    tearDown = base.EstimatedPKTests.tearDown
    revision = base.EstimatedPKTests.revision
    page = base.EstimatedPKTests.page
    form = base.EstimatedPKTests.form

    def test_band_is_ordered_reproducible_and_centred_on_typical(self):
        revision = self.revision()
        result = calculate_population_pk(revision.id, 'ideal_body_weight_devine', treatment_request_example(), 'MM',
                                         n_subjects=2000)
        self.assertEqual(result['status'], 'completed_population_calculation')
        self.assertFalse(result['clinical_prediction_validated'])
        self.assertEqual(len(result['band']), len(result['times_h']))
        for row in result['band']:
            self.assertTrue(row['p05'] <= row['p25'] <= row['p50'] <= row['p75'] <= row['p95'])
        self.assertLess(result['verification']['exact_vs_numerical_typical_max_abs_ng_ml'], 1e-6)
        body = {k: v for k, v in result.items() if k != 'report_sha256'}
        self.assertEqual(result['report_sha256'], digest(body))
        again = calculate_population_pk(revision.id, 'ideal_body_weight_devine', treatment_request_example(), 'MM',
                                        n_subjects=2000)
        self.assertEqual(result['report_sha256'], again['report_sha256'])
        # AUC to infinity = dose/CL and median(exp(-eta_CL)) = 1, so the median matches the typical value.
        dose = sum(e['amount']['value'] for e in treatment_request_example()['events'])
        typical_auc_inf = 1000 * dose / result['typical_parameters']['apparent_clearance_l_h']
        auc = result['exposure']['auc_0_infinity_ng_h_ml']
        self.assertAlmostEqual(auc['p50'] / typical_auc_inf, 1.0, delta=0.06)
        # Its 5th-95th spread follows directly from omega_CL: exp(2 * 1.645 * sqrt(0.296)).
        expected = math.exp(2 * 1.645 * math.sqrt(0.296))
        self.assertAlmostEqual(auc['p95'] / auc['p05'], expected, delta=0.1 * expected)

    def test_seed_changes_draws_not_conclusions(self):
        revision = self.revision()
        a = calculate_population_pk(revision.id, 'ideal_body_weight_devine', treatment_request_example(), 'MM', n_subjects=1000, seed=1)
        b = calculate_population_pk(revision.id, 'ideal_body_weight_devine', treatment_request_example(), 'MM', n_subjects=1000, seed=2)
        self.assertNotEqual(a['report_sha256'], b['report_sha256'])
        self.assertAlmostEqual(a['exposure']['auc_0_infinity_ng_h_ml']['p50'], b['exposure']['auc_0_infinity_ng_h_ml']['p50'],
                               delta=0.1 * a['exposure']['auc_0_infinity_ng_h_ml']['p50'])

    def test_missing_inputs_and_bad_arguments(self):
        legacy = state_from_scenario(self.scenario.payload['analysis']['report']['profile'])
        revision = self.revision(legacy, 'Legacy')
        result = calculate_population_pk(revision.id, 'ideal_body_weight_devine', treatment_request_example(), 'MM')
        self.assertEqual(result['status'], 'missing_estimator_inputs')
        self.assertIsNone(result['band'])
        for kwargs in ({'n_subjects': 50}, {'n_subjects': 6000}, {'n_subjects': True}, {'seed': -1}):
            with self.assertRaises(ValueError):
                calculate_population_pk(revision.id, 'ideal_body_weight_devine', treatment_request_example(), 'MM', **kwargs)

    def test_page_and_cli(self):
        revision = self.revision()
        text = self.client.post(self.page(revision), data=self.form(revision, 'population')).get_data(as_text=True)
        self.assertIn('Population band', text)
        self.assertIn('virtual patients share this record', text)
        self.assertIn('fill-opacity="0.15"', text)
        register_population_pk_commands(self.app)
        runner = self.app.test_cli_runner()
        with tempfile.TemporaryDirectory() as tmp:
            request = Path(tmp) / 'request.json'
            request.write_text(json.dumps(treatment_request_example()))
            result = runner.invoke(args=['patient-pk-population', '--revision-id', str(revision.id),
                                         '--weight-basis', 'ideal_body_weight_devine', '--treatment-file', str(request),
                                         '--disease-code', 'MM', '--subjects', '200'])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(json.loads(result.output)['n_subjects'], 200)


if __name__ == '__main__':
    unittest.main()
