#!/usr/bin/env python3
"""Fixed synthetic comparison of the installed RK4 kernel with an analytic reference."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys

import pk_prediction_metrics_preview as metrics
import pk_synthetic_time_pairs as reference

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = PROJECT_ROOT / 'examples' / 'pk_numerical_case_plan_v1.json'
PLAN_SHA256 = '1cad762459fcbef5f51a282c27f3eb4d8fa8c79a5f1289ad10b4655211698d9e'
KERNEL_SHA256 = '088f8da0a5cfd9c392411079810a3220e56750289871999fc22a9bb511b29ebe'
REFERENCE_SHA256 = '57ce339ef584e0190534379aec232a584860d853a23e8a36273a63902c9ff441'
PLAN_CANONICAL_SHA256 = '35dd8a505a2d3ee714682258aa2a1669d7b5cbb0ebf9113e5defff87bff05252'
METHOD = 'fixed-synthetic-rk4-analytic-crosscheck-v1.0'


def check_hash(path, expected, label):
    actual = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(label + ' differs from the specified version; no comparison is authorized by this fixed case plan')
    return actual


def load_plan(path=PLAN_PATH):
    with Path(path).open('rb') as stream:
        raw = stream.read(metrics.MAX_INPUT_BYTES + 1)
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError('Case plan bytes differ from this version; restore the supplied plan or create a separately versioned campaign')
    return metrics.parse_document(raw)


def validate_plan(plan):
    metrics.exact_keys(plan, {'schema_version', 'purpose', 'plan_id', 'case_selection', 'max_step_h',
                             'display_step_h', 'comparison_tolerance', 'cases'}, 'plan')
    if (plan['schema_version'] != 'synthetic-rk4-analytic-case-plan-v1'
            or plan['purpose'] != 'mathematical_verification_only'):
        raise ValueError('Only the synthetic mathematical case plan is supported')
    if type(plan['max_step_h']) is not float or plan['max_step_h'] != 0.001:
        raise ValueError('Plan maximum step must be exactly 0.001 h')
    if type(plan['display_step_h']) is not float or plan['display_step_h'] != 0.1:
        raise ValueError('Plan display step must be exactly 0.1 h')
    tolerance = plan['comparison_tolerance']
    metrics.exact_keys(tolerance, {'absolute_ng_ml', 'relative', 'authority'}, 'tolerance')
    if (type(tolerance['absolute_ng_ml']) is not float or tolerance['absolute_ng_ml'] != 5e-7
            or type(tolerance['relative']) is not float or tolerance['relative'] != 1e-8):
        raise ValueError('The fixed campaign tolerances must not be changed')
    cases = plan['cases']
    if not isinstance(cases, list) or not 1 <= len(cases) <= 8:
        raise ValueError('Require one to eight mathematical cases')
    seen = set()
    for case in cases:
        metrics.exact_keys(case, {'case_id', 'parameters', 'events', 'sample_times_h'}, 'case')
        cid = metrics.text_value(case['case_id'], 'case_id')
        if cid in seen:
            raise ValueError('Duplicate case_id')
        seen.add(cid)
        reference.validate_parameters(case['parameters'], 'case parameters')
        reference.validate_events(case['events'], 'case')
        times = case['sample_times_h']
        if not isinstance(times, list) or not 1 <= len(times) <= 8:
            raise ValueError('Require one to eight sample times per case')
        checked = [reference.bounded(t, 'sample time', 0, 72) for t in times]
        if len(set(checked)) != len(checked):
            raise ValueError('Duplicate sample time')
    if metrics.digest(plan) != PLAN_CANONICAL_SHA256:
        raise ValueError('Case plan content differs from the fixed campaign')
    return plan


def compare_case(case, solver):
    """Calls the actual solver at each unique dose age; no copied RK4 implementation."""
    cl, volume, ktr = reference.validate_parameters(case['parameters'], 'case parameters')
    events = reference.validate_events(case['events'], 'case')
    cache = {}
    samples = []
    solver_steps = 0
    unit_calls = []
    for time in case['sample_times_h']:
        time = float(time)
        terms = []
        for event_time, amount in events:
            age = time - event_time
            if age <= 0:
                continue  # Zero-age central amount is exactly zero; future events have no effect.
            if age not in cache:
                response = solver(dose_mg=1.0, volume_l=volume, clearance_l_h=cl,
                                  transit_rate_h=ktr, stages=8, horizon_h=age,
                                  display_step_h=0.1, max_step_h=0.001)
                endpoint = response['points'][-1]
                if endpoint['time_h'] != age:
                    raise ValueError('RK4 endpoint does not match the exact requested dose age')
                c = metrics.number(endpoint['concentration_ng_ml'], 'RK4 endpoint concentration', True)
                balance = metrics.number(response['amount_balance']['max_absolute_error_mg'], 'RK4 amount balance', True)
                if balance > 1e-9:
                    raise ValueError('RK4 unit-response amount balance exceeded project tolerance')
                steps = response['solver']['steps']
                if type(steps) is not int or not 0 < steps <= 250000:
                    raise ValueError('Invalid RK4 step count')
                cache[age] = c
                solver_steps += steps
                unit_calls.append({'dose_age_h': age, 'unit_response_sha256': response['report_sha256'],
                                   'steps': steps, 'max_amount_balance_error_mg': balance})
            terms.append(amount * cache[age])
        actual = math.fsum(terms)
        expected = reference.concentration_at_time(time, events, cl, volume, ktr)
        error = abs(actual - expected)
        allowed = 5e-7 + 1e-8 * abs(expected)
        samples.append({'time_h': time, 'rk4_concentration_ng_ml': actual,
                        'analytic_concentration_ng_ml': expected, 'absolute_error_ng_ml': error,
                        'allowed_error_ng_ml': allowed, 'status': 'passed' if error <= allowed else 'failed'})
    return {'case_id': case['case_id'], 'inputs': case, 'status': 'passed' if all(s['status'] == 'passed' for s in samples) else 'failed',
            'samples': samples, 'unit_response_calls': unit_calls, 'solver_steps': solver_steps,
            'max_absolute_concentration_error_ng_ml': max(s['absolute_error_ng_ml'] for s in samples)}


def run_crosscheck(plan, kernel):
    validate_plan(plan)
    check_hash(kernel.__file__, KERNEL_SHA256, 'Installed transit kernel')
    check_hash(reference.__file__, REFERENCE_SHA256, 'Analytic reference')
    results = [compare_case(case, kernel.solve_transit) for case in plan['cases']]
    report = {
        'schema_version': 'synthetic-rk4-analytic-crosscheck-report-v1', 'method_version': METHOD,
        'status': 'mathematical_crosscheck_passed' if all(r['status'] == 'passed' for r in results) else 'mathematical_crosscheck_failed',
        'purpose': 'mathematical_verification_only', 'plan_id': plan['plan_id'],
        'case_plan_file_sha256': PLAN_SHA256, 'case_plan_canonical_sha256': metrics.digest(plan),
        'implementation_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'kernel_sha256': hashlib.sha256(Path(kernel.__file__).read_bytes()).hexdigest(),
        'kernel_method_version': kernel.METHOD_VERSION,
        'reference_sha256': hashlib.sha256(Path(reference.__file__).read_bytes()).hexdigest(),
        'python_version': platform.python_version(), 'comparison_tolerance': plan['comparison_tolerance'],
        'case_count': len(results), 'sample_count': sum(len(r['samples']) for r in results),
        'total_solver_steps': sum(r['solver_steps'] for r in results), 'cases': results,
        'actual_installed_kernel_called': True, 'synthetic_analytic_reference_calculated': True,
        'comparison_method': 'Independent unit-response endpoint evaluations at exact dose ages; linear dose superposition',
        'full_patient_execution_path_tested': False, 'saved_runs_read_or_modified': False,
        'database_accessed': False, 'network_accessed': False,
        'clinical_prediction_validated': False, 'ready_for_patient_simulation': False,
        'empirical_validation_performed': False, 'source_model_reproduction_established': False,
        'not_checked': ['Source equation independent signoff', 'Covariate-to-parameter derivation',
                        'Patient applicability and production preflight gates', 'Production display-grid/event composer',
                        'AUC or compartment-amount reference comparisons', 'Observed concentrations',
                        'Uncertainty, clinical outcomes or dosing decisions'],
        'limitation': 'A fixed engineering campaign checks concentration agreement and kernel unit-response balance only. '
                      'Some cases use source-typical numeric parameters as test inputs, not verified individual estimates. '
                      'Off-grid endpoints use the generic kernel, not a new patient execution mode. No scientific gate is cleared.',
    }
    report['report_sha256'] = metrics.digest(report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Create a new report; never overwrite')
    args = parser.parse_args(argv)
    try:
        plan = load_plan()
        check_hash(reference.__file__, REFERENCE_SHA256, 'Analytic reference')
        sys.path.insert(0, str(PROJECT_ROOT))
        from intelligence_store import transit_kernel as kernel
        check_hash(kernel.__file__, KERNEL_SHA256, 'Installed transit kernel')
        report = run_crosscheck(plan, kernel)
        rendered = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
        if args.output:
            with args.output.open('x', encoding='utf-8') as stream:
                stream.write(rendered)
        sys.stdout.write(rendered)
        return 0 if report['status'] == 'mathematical_crosscheck_passed' else 1
    except (ImportError, OSError, ValueError, KeyError, RecursionError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
