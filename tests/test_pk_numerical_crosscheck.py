"""Actual installed-kernel campaign plus deliberate failure checks."""
import copy
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'pk_numerical_crosscheck.py'
sys.path.insert(0, str(SCRIPT.parent))
import pk_numerical_crosscheck as crosscheck
import pk_prediction_metrics_preview as metrics
from intelligence_store import transit_kernel as kernel


class NumericalCrosscheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = crosscheck.load_plan()
        cls.report = crosscheck.run_crosscheck(cls.plan, kernel)

    def test_actual_campaign_passes_all_cases_and_samples(self):
        self.assertEqual(self.report['status'], 'mathematical_crosscheck_passed')
        self.assertEqual(self.report['case_count'], 6)
        self.assertEqual(self.report['sample_count'], 25)
        self.assertGreater(self.report['total_solver_steps'], 0)
        for case in self.report['cases']:
            self.assertEqual(case['status'], 'passed')
            for sample in case['samples']:
                self.assertLessEqual(sample['absolute_error_ng_ml'], sample['allowed_error_ng_ml'])
            for call in case['unit_response_calls']:
                self.assertLessEqual(call['max_amount_balance_error_mg'], 1e-9)

    def test_exact_requested_times_and_event_boundary_are_retained(self):
        first = self.report['cases'][0]['samples']
        self.assertEqual([row['time_h'] for row in first], [0, 0.137, 1.037, 7.253, 24.037])
        self.assertEqual(first[0]['rk4_concentration_ng_ml'], 0)
        repeated = self.report['cases'][2]['samples']
        self.assertEqual([row['time_h'] for row in repeated], [23.999, 24, 24.037, 48.037, 72])

    def test_digest_identity_no_science_promotion_and_input_unchanged(self):
        report = copy.deepcopy(self.report)
        digest = report.pop('report_sha256')
        self.assertEqual(metrics.digest(report), digest)
        self.assertEqual(report['kernel_sha256'], crosscheck.KERNEL_SHA256)
        self.assertEqual(report['reference_sha256'], crosscheck.REFERENCE_SHA256)
        self.assertEqual(metrics.digest(self.plan), crosscheck.PLAN_CANONICAL_SHA256)
        self.assertIs(report['actual_installed_kernel_called'], True)
        for flag in ('clinical_prediction_validated', 'ready_for_patient_simulation',
                     'empirical_validation_performed', 'source_model_reproduction_established',
                     'full_patient_execution_path_tested', 'database_accessed', 'network_accessed'):
            self.assertIs(report[flag], False)

    def test_changed_case_plan_fails_before_solver_runs(self):
        changed = copy.deepcopy(self.plan)
        changed['cases'][0]['parameters']['apparent_clearance_l_h'] = 3
        with patch.object(kernel, 'solve_transit') as call:
            with self.assertRaises(ValueError): crosscheck.run_crosscheck(changed, kernel)
            call.assert_not_called()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'changed.json'
            path.write_text(json.dumps(self.plan, separators=(',', ':')))
            # Same content with changed bytes is also a different file identity.
            with self.assertRaises(ValueError): crosscheck.load_plan(path)

    def test_changed_implementation_hash_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = Path(folder) / 'kernel.py'; fake.write_text('changed')
            with self.assertRaises(ValueError): crosscheck.check_hash(fake, crosscheck.KERNEL_SHA256, 'kernel')
        with patch.object(crosscheck, 'KERNEL_SHA256', '0' * 64), patch.object(kernel, 'solve_transit') as call:
            with self.assertRaises(ValueError): crosscheck.run_crosscheck(self.plan, kernel)
            call.assert_not_called()

    def test_deliberately_wrong_concentration_fails_numeric_check(self):
        case = copy.deepcopy(self.plan['cases'][0]); case['sample_times_h'] = [1.037]
        def wrong_solver(**kwargs):
            return {'points': [{'time_h': kwargs['horizon_h'], 'concentration_ng_ml': 10}],
                    'amount_balance': {'max_absolute_error_mg': 0},
                    'solver': {'steps': 1}, 'report_sha256': 'synthetic-test-double'}
        result = crosscheck.compare_case(case, wrong_solver)
        self.assertEqual(result['status'], 'failed')
        self.assertGreater(result['samples'][0]['absolute_error_ng_ml'], result['samples'][0]['allowed_error_ng_ml'])

    def test_wrong_time_nonfinite_and_mass_balance_fail_closed(self):
        case = copy.deepcopy(self.plan['cases'][0]); case['sample_times_h'] = [1.037]
        for fault in ('time', 'nonfinite', 'balance'):
            def invalid_solver(**kwargs):
                return {'points': [{'time_h': 1 if fault == 'time' else kwargs['horizon_h'],
                                    'concentration_ng_ml': float('nan') if fault == 'nonfinite' else 0}],
                        'amount_balance': {'max_absolute_error_mg': 1e-8 if fault == 'balance' else 0},
                        'solver': {'steps': 1}, 'report_sha256': 'synthetic-test-double'}
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                crosscheck.compare_case(case, invalid_solver)

    def test_export_never_overwrites_and_failed_campaign_has_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.json'; output.write_text('keep')
            # Reuse an already computed actual report; this test checks I/O, not the solver again.
            with patch.object(crosscheck, 'run_crosscheck', return_value=self.report), patch('sys.stdout'), patch('sys.stderr'):
                self.assertEqual(crosscheck.main(['--output', str(output)]), 1)
            self.assertEqual(output.read_text(), 'keep')
            failed = copy.deepcopy(self.report); failed['status'] = 'mathematical_crosscheck_failed'
            with patch.object(crosscheck, 'run_crosscheck', return_value=failed), patch('sys.stdout'), patch('sys.stderr'):
                self.assertEqual(crosscheck.main([]), 1)


if __name__ == '__main__':
    unittest.main()
