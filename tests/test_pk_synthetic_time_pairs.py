"""Exact-time analytic reference checked against independently integrated equations."""
import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'pk_synthetic_time_pairs.py'
sys.path.insert(0, str(SCRIPT.parent))
import pk_synthetic_time_pairs as harness
import pk_prediction_metrics_preview as metrics


def quadrature_concentration(t, dose, cl, volume, ktr):
    # Independent Simpson integral of Erlang-8 arrival density times central survival.
    # This uses the density, not the harness's Poisson-tail/series expression.
    n = 10000
    width = t / n
    ke = cl / volume
    def f(u):
        return (ktr**8 * u**7 * math.exp(-ktr * u) / math.factorial(7)
                * math.exp(-ke * (t - u)))
    weighted = f(0) + f(t)
    weighted += 4 * math.fsum(f(i * width) for i in range(1, n, 2))
    weighted += 2 * math.fsum(f(i * width) for i in range(2, n, 2))
    return 1000 * dose / volume * width / 3 * weighted


class SyntheticTimePairTests(unittest.TestCase):
    def test_exact_off_grid_times_and_quad_reference(self):
        document = harness.example_document()
        report = harness.evaluate_document(document)
        pairs = report['generated_pairs']['rows']
        self.assertEqual([p['predicted_time_h'] for p in pairs], [0.137, 1.037, 7.253, 24.037])
        for pair in pairs:
            self.assertEqual(pair['observed_time_h'], pair['predicted_time_h'])
            expected = quadrature_concentration(pair['observed_time_h'], 1, 2, 10, 1)
            self.assertTrue(math.isclose(pair['predicted_ng_ml'], expected, rel_tol=1e-9, abs_tol=1e-12))
        rounded = harness.concentration_at_time(1.0, [(0, 1)], 2, 10, 1)
        self.assertNotAlmostEqual(pairs[1]['predicted_ng_ml'], rounded, places=7)

    def test_equal_and_nearly_equal_rate_limits_are_finite(self):
        t = 3.137
        expected = 100 * math.exp(-t) * t**8 / math.factorial(8)
        actual = harness.concentration_at_time(t, [(0, 1)], 10, 10, 1)
        nearby = harness.concentration_at_time(t, [(0, 1)], 10 * (1 - 1e-12), 10, 1)
        self.assertAlmostEqual(actual, expected, places=12)
        self.assertTrue(math.isclose(nearby, expected, rel_tol=1e-11))
        self.assertTrue(math.isfinite(nearby))

    def test_series_branch_boundary_matches_independent_integral(self):
        for t in (12.499999, 12.5, 12.500001):  # (ktr-ke)*t crosses 10.
            actual = harness.concentration_at_time(t, [(0, 1)], 2, 10, 1)
            expected = quadrature_concentration(t, 1, 2, 10, 1)
            self.assertTrue(math.isclose(actual, expected, rel_tol=1e-9))

    def test_future_events_do_not_act_and_event_concentration_is_continuous(self):
        params = (2, 10, 1)
        first = [(0, 1)]
        both = [(0, 1), (24, 2)]
        self.assertEqual(harness.concentration_at_time(12.137, first, *params),
                         harness.concentration_at_time(12.137, both, *params))
        self.assertEqual(harness.concentration_at_time(24, first, *params),
                         harness.concentration_at_time(24, both, *params))
        t = 26.037
        expected = quadrature_concentration(t, 1, *params) + quadrature_concentration(t - 24, 2, *params)
        self.assertTrue(math.isclose(harness.concentration_at_time(t, both, *params), expected, rel_tol=1e-9))

    def test_unit_conversion_dose_scaling_and_zero_initial_state(self):
        c = harness.concentration_at_time(7, [(0, 1)], 2, 10, 1)
        doubled = harness.concentration_at_time(7, [(0, 2)], 2, 10, 1)
        self.assertEqual(doubled, 2 * c)
        self.assertEqual(harness.concentration_at_time(0, [(0, 1)], 2, 10, 1), 0)
        self.assertEqual(harness.concentration_at_time(2, [(24, 1)], 2, 10, 1), 0)
        # At ke == ktr, a 1 mg dose / 10 L gives 100 ng/mL times central fraction.
        self.assertAlmostEqual(harness.concentration_at_time(8, [(0, 1)], 10, 10, 1),
                               100 * math.exp(-8) * 8**8 / math.factorial(8), places=12)

    def test_report_integrity_no_input_mutation_and_science_flags(self):
        doc = harness.example_document(); original = copy.deepcopy(doc)
        report = harness.evaluate_document(doc)
        self.assertEqual(doc, original)
        report_digest = report.pop('report_sha256')
        self.assertEqual(metrics.digest(report), report_digest)
        nested = copy.deepcopy(report['metric_report'])
        nested_digest = nested.pop('report_sha256')
        self.assertEqual(metrics.digest(nested), nested_digest)
        self.assertIs(report['synthetic_model_reference_calculated'], True)
        for flag in ('production_pk_solver_run', 'empirical_validation_performed',
                     'clinical_prediction_validated', 'ready_for_patient_simulation',
                     'source_model_reproduction_established', 'database_accessed', 'network_accessed'):
            self.assertIs(report[flag], False)
        self.assertIsNone(report['metric_report']['acceptance_thresholds'])

    def test_schema_and_history_fail_closed(self):
        for key, value in (('purpose', 'real_data'), ('model_kind', 'patient_model'),
                           ('initial_amounts', 'unknown'), ('subjects', [])):
            doc = harness.example_document(); doc[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): harness.evaluate_document(doc)
        for events in ([{'time_h': 1, 'amount_mg': 1, 'source_ref': 'synthetic'}],
                       [{'time_h': 0, 'amount_mg': 1, 'source_ref': 'synthetic'},
                        {'time_h': 23, 'amount_mg': 1, 'source_ref': 'synthetic'}], []):
            doc = harness.example_document(); doc['subjects'][0]['events'] = events
            with self.assertRaises(ValueError): harness.evaluate_document(doc)
        doc = harness.example_document(); doc['subjects'].append(copy.deepcopy(doc['subjects'][0]))
        with self.assertRaises(ValueError): harness.evaluate_document(doc)

    def test_parameter_and_time_limits_reject_nonfinite_and_unsupported(self):
        for key, value in (('apparent_volume_l', 0), ('transit_rate_h', 21),
                           ('apparent_clearance_l_h', float('nan')), ('apparent_clearance_l_h', True),
                           ('apparent_clearance_l_h', 11)):
            doc = harness.example_document()
            doc['subjects'][0]['parameters'][key] = value
            # Last case: CL/V=1.1 exceeds KTR=1.
            with self.subTest(key=key,value=value), self.assertRaises(ValueError): harness.evaluate_document(doc)
        for t in (-1, 72.001, float('inf'), True):
            doc = harness.example_document(); doc['subjects'][0]['samples'][0]['time_h'] = t
            with self.assertRaises(ValueError): harness.evaluate_document(doc)

    def test_blq_missing_and_zero_predicted_pairs_flow_to_metrics(self):
        doc = harness.example_document()
        samples = doc['subjects'][0]['samples']
        samples[0].update(observation_status='blq', observed_ng_ml=None)
        samples[1].update(observation_status='missing', observed_ng_ml=None)
        samples[2]['time_h'] = 0  # Prediction at dose time is zero; not loggable.
        report = harness.evaluate_document(doc)
        self.assertEqual(report['metric_report']['counts']['exclusions_by_reason'],
                         {'blq_unquantified': 1, 'observation_missing': 1, 'quantified_pair_nonpositive': 1})
        self.assertEqual(report['metric_report']['counts']['eligible_rows'], 1)
        samples[0]['observed_ng_ml'] = 0
        with self.assertRaises(ValueError): harness.evaluate_document(doc)

    def test_duplicate_samples_and_work_limits_are_rejected(self):
        doc = harness.example_document()
        doc['subjects'][0]['samples'].append(copy.deepcopy(doc['subjects'][0]['samples'][0]))
        with self.assertRaises(ValueError): harness.evaluate_document(doc)
        doc = harness.example_document()
        doc['subjects'] *= 101
        with self.assertRaises(ValueError): harness.evaluate_document(doc)
        doc = harness.example_document()
        doc['subjects'][0]['samples'] *= 2501
        with self.assertRaises(ValueError): harness.evaluate_document(doc)

    def test_cli_is_standalone_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'report.json'
            first = subprocess.run([sys.executable, str(SCRIPT), '--example', '--output', str(target)],
                                   cwd=folder, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            before = target.read_bytes()
            second = subprocess.run([sys.executable, str(SCRIPT), '--example', '--output', str(target)],
                                    cwd=folder, capture_output=True, text=True)
            self.assertEqual(second.returncode, 1)
            self.assertEqual(target.read_bytes(), before)
            self.assertEqual(json.loads(first.stdout)['sample_count'], 4)


if __name__ == '__main__':
    unittest.main()
