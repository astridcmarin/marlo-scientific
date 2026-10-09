"""Independent expected arithmetic, rejection boundaries and standalone CLI behavior."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

# Loads only the standalone script. Does not import Flask or intelligence_store.
SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'pk_prediction_metrics_preview.py'
SPEC = importlib.util.spec_from_file_location('pk_prediction_metrics_preview', SCRIPT)
metrics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metrics)


class PredictionMetricPreviewTests(unittest.TestCase):
    def test_subject_weighting_and_exclusion_partition(self):
        report = metrics.calculate_preview(metrics.example_document())
        # A has two errors ln(2); B has one error -ln(2).
        # Equal subject weighting gives zero, unlike pooled sample bias ln(2)/3.
        self.assertAlmostEqual(report['metrics']['subject_balanced_mean_log_ratio'], 0, places=14)
        self.assertAlmostEqual(report['metrics']['subject_balanced_root_mean_square_log_ratio'], math.log(2), places=14)
        counts = report['counts']
        self.assertEqual((counts['input_rows'], counts['eligible_rows'], counts['excluded_rows']), (6, 3, 3))
        self.assertEqual((counts['input_subjects'], counts['eligible_subjects'], counts['subjects_without_eligible_pairs']), (5, 2, 3))
        self.assertEqual(set(counts['exclusions_by_reason'].values()), {1})
        self.assertEqual(sum(counts['exclusions_by_reason'].values()), counts['excluded_rows'])

    def test_perfect_predictions_and_no_acceptance_claim(self):
        doc = metrics.example_document()
        doc['rows'] = doc['rows'][:3]
        for row in doc['rows']:
            row['predicted_ng_ml'] = row['observed_ng_ml']
        report = metrics.calculate_preview(doc)
        self.assertEqual(report['metrics']['subject_balanced_mean_log_ratio'], 0)
        self.assertEqual(report['metrics']['subject_balanced_root_mean_square_log_ratio'], 0)
        self.assertIsNone(report['acceptance_thresholds'])
        self.assertEqual(report['performance_acceptance_decision'], 'not_assessed')
        for flag in ('clinical_prediction_validated', 'ready_for_patient_simulation',
                     'empirical_validation_performed', 'model_simulation_run', 'database_accessed', 'network_accessed'):
            self.assertIs(report[flag], False)

    def test_order_invariance_and_no_input_mutation(self):
        doc = metrics.example_document()
        original = copy.deepcopy(doc)
        first = metrics.calculate_preview(doc)
        doc['rows'].reverse()
        second = metrics.calculate_preview(doc)
        self.assertEqual(first['metrics'], second['metrics'])
        self.assertEqual(first['counts'], second['counts'])
        doc['rows'].reverse()
        self.assertEqual(doc, original)

    def test_log_difference_handles_extreme_finite_concentrations(self):
        doc = metrics.example_document()
        doc['rows'] = doc['rows'][:1]
        doc['rows'][0].update(observed_ng_ml=1e-300, predicted_ng_ml=1e300)
        value = metrics.calculate_preview(doc)['metrics']
        self.assertAlmostEqual(value['subject_balanced_mean_log_ratio'], 600 * math.log(10), places=10)
        self.assertTrue(math.isfinite(value['subject_balanced_root_mean_square_log_ratio']))

    def test_all_excluded_has_null_metrics_not_zero_or_pass(self):
        doc = metrics.example_document()
        doc['rows'] = doc['rows'][3:]
        report = metrics.calculate_preview(doc)
        self.assertEqual(report['status'], 'no_eligible_synthetic_pairs')
        self.assertIsNone(report['metrics']['subject_balanced_mean_log_ratio'])
        self.assertIsNone(report['metrics']['subject_balanced_root_mean_square_log_ratio'])
        self.assertEqual(report['counts']['eligible_subjects'], 0)

    def test_schema_units_methods_and_duplicates_fail_closed(self):
        cases = [
            ('purpose', 'real_patient_data'), ('schema_version', 'other'),
            ('concentration_unit', 'mg/L'), ('pairing_method', 'rounded_time'),
            ('prediction_method', 'fitted_etas'), ('rows', []), ('rows', [{}] * 10001),
        ]
        for key, value in cases:
            with self.subTest(key=key):
                doc = metrics.example_document(); doc[key] = value
                with self.assertRaises(ValueError): metrics.calculate_preview(doc)
        doc = metrics.example_document(); doc['rows'].append(copy.deepcopy(doc['rows'][0]))
        with self.assertRaises(ValueError): metrics.calculate_preview(doc)
        doc = metrics.example_document(); doc['extra'] = 'unrecognized'
        with self.assertRaises(ValueError): metrics.calculate_preview(doc)

    def test_numbers_times_status_and_missing_values_are_explicit(self):
        cases = [
            ('predicted_ng_ml', True), ('predicted_ng_ml', float('nan')),
            ('predicted_ng_ml', float('inf')), ('observed_ng_ml', None),
            ('observed_time_h', -1), ('predicted_time_h', 1.01),
            ('observation_status', []), ('subject_id', ' '),
            ('predicted_source_ref', 'line\nbreak'),
        ]
        for key, value in cases:
            with self.subTest(key=key):
                doc = metrics.example_document(); doc['rows'][0][key] = value
                with self.assertRaises(ValueError): metrics.calculate_preview(doc)
        for status in ('blq', 'missing'):
            doc = metrics.example_document()
            doc['rows'][0].update(observation_status=status, observed_ng_ml=0)
            with self.assertRaises(ValueError): metrics.calculate_preview(doc)

    def test_negative_or_zero_quantified_values_are_excluded_with_reason(self):
        for observed, predicted in ((-1, 2), (1, 0), (1, -2), (0, 0)):
            doc = metrics.example_document(); doc['rows'] = doc['rows'][:1]
            doc['rows'][0].update(observed_ng_ml=observed, predicted_ng_ml=predicted)
            report = metrics.calculate_preview(doc)
            self.assertEqual(report['counts']['exclusions_by_reason']['quantified_pair_nonpositive'], 1)
            self.assertEqual(report['status'], 'no_eligible_synthetic_pairs')

    def test_json_limits_duplicate_keys_and_nonfinite_constants(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff', b'x' * (metrics.MAX_INPUT_BYTES + 1)):
            with self.assertRaises(ValueError): metrics.parse_document(raw)
        doc = metrics.example_document()
        self.assertEqual(metrics.parse_document(json.dumps(doc).encode()), doc)

    def test_report_integrity_and_raw_source_hash_are_distinct(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'input.json'
            source.write_text(json.dumps(metrics.example_document(), indent=2))
            doc, raw_hash = metrics.load_document(source)
            report = metrics.calculate_preview(doc, raw_hash)
            report_hash = report.pop('report_sha256')
            self.assertEqual(metrics.digest(report), report_hash)
            self.assertEqual(report['input_file_sha256'], raw_hash)
            self.assertNotEqual(report['input_canonical_sha256'], raw_hash)

    def test_cli_runs_without_app_and_never_overwrites_input_or_report(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.json'
            result = subprocess.run([sys.executable, str(SCRIPT), '--example', '--output', str(output)],
                                    cwd=folder, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            original = output.read_bytes()
            again = subprocess.run([sys.executable, str(SCRIPT), '--example', '--output', str(output)],
                                   cwd=folder, capture_output=True, text=True)
            self.assertEqual(again.returncode, 1)
            self.assertEqual(output.read_bytes(), original)
            source = Path(folder) / 'input.json'
            source.write_text(json.dumps(metrics.example_document()))
            before = source.read_bytes()
            same = subprocess.run([sys.executable, str(SCRIPT), '--input-file', str(source), '--output', str(source)],
                                  cwd=folder, capture_output=True, text=True)
            self.assertEqual(same.returncode, 1)
            self.assertEqual(source.read_bytes(), before)

    def test_cli_no_eligible_pairs_reports_exit_two(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'all-excluded.json'
            doc = metrics.example_document(); doc['rows'] = doc['rows'][3:]
            source.write_text(json.dumps(doc))
            result = subprocess.run([sys.executable, str(SCRIPT), '--input-file', str(source)],
                                    cwd=folder, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'], 'no_eligible_synthetic_pairs')


if __name__ == '__main__':
    unittest.main()
