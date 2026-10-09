#!/usr/bin/env python3
"""Synthetic paired-concentration metric checks. No model, database or network use."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys

INPUT_SCHEMA = 'synthetic-pk-paired-concentrations-v1'
REPORT_SCHEMA = 'synthetic-pk-metrics-preview-v1'
METRIC_VERSION = 'subject-balanced-log-error-v1.0'
MAX_INPUT_BYTES = 1_048_576
MAX_ROWS = 10_000
DESIGN_PROTOCOL_SHA256 = 'f2947b2193a2215fc3e70c4c562e46de773d25e5b0af36e32652f263d399292b'
STATUSES = {'quantified', 'blq', 'missing'}


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def exact_keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f'{label}: expected exactly these keys: {", ".join(sorted(expected))}')


def text_value(value, label, max_length=160):
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError(f'{label}: required nonblank string, at most {max_length} characters')
    if value != value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f'{label}: leading/trailing whitespace or control characters are not allowed')
    return value


def number(value, label, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{label}: required finite JSON number')
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f'{label}: number outside supported range') from exc
    if not math.isfinite(result) or (nonnegative and result < 0):
        raise ValueError(f'{label}: required finite' + (' nonnegative' if nonnegative else '') + ' number')
    return result


def _duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON object key is not allowed')
        value[key] = item
    return value


def _invalid_constant(_):
    raise ValueError('Nonfinite JSON constants are not allowed')


def parse_document(raw):
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError('Input exceeds the 1 MiB limit')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_duplicate_keys,
                          parse_constant=_invalid_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('Input must be a bounded valid UTF-8 JSON document') from exc


def load_document(path):
    # Bounded read, including files whose size changes while being read.
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    return parse_document(raw), hashlib.sha256(raw).hexdigest()


def calculate_preview(document, input_file_sha256=None):
    exact_keys(document, {'schema_version', 'purpose', 'fixture_id', 'concentration_unit',
                         'pairing_method', 'prediction_method', 'rows'}, 'document')
    if document['schema_version'] != INPUT_SCHEMA or document['purpose'] != 'synthetic_fixture':
        raise ValueError('Only this schema with purpose synthetic_fixture is accepted; real data are out of scope')
    text_value(document['fixture_id'], 'fixture_id')
    if document['concentration_unit'] != 'ng/mL':
        raise ValueError('concentration_unit must be ng/mL; no conversion is performed')
    if document['pairing_method'] != 'explicit_same_time_synthetic_pairs':
        raise ValueError('pairing_method must declare explicit_same_time_synthetic_pairs')
    if document['prediction_method'] != 'supplied_synthetic_values_no_fitting':
        raise ValueError('prediction_method must declare supplied_synthetic_values_no_fitting')
    rows = document['rows']
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise ValueError('rows must contain 1 to 10000 records')
    seen, participants, eligible, exclusions = set(), set(), defaultdict(list), Counter()
    row_keys = {'subject_id', 'sample_id', 'observed_time_h', 'predicted_time_h',
                'observation_status', 'observed_ng_ml', 'predicted_ng_ml',
                'observed_source_ref', 'predicted_source_ref'}
    for position, row in enumerate(rows, 1):
        label = f'row {position}'  # Never echo identifier/source contents in errors.
        exact_keys(row, row_keys, label)
        subject = text_value(row['subject_id'], label + ' subject_id')
        sample = text_value(row['sample_id'], label + ' sample_id')
        for key in ('observed_source_ref', 'predicted_source_ref'):
            text_value(row[key], label + ' ' + key, 500)
        pair_id = (subject, sample)
        if pair_id in seen:
            raise ValueError(label + ': duplicate subject_id/sample_id pair')
        seen.add(pair_id)
        participants.add(subject)
        observed_time = number(row['observed_time_h'], label + ' observed_time_h', True)
        predicted_time = number(row['predicted_time_h'], label + ' predicted_time_h', True)
        if observed_time != predicted_time:
            raise ValueError(label + ': observation and prediction times must match exactly; no alignment is performed')
        status = row['observation_status']
        if not isinstance(status, str) or status not in STATUSES:
            raise ValueError(label + ': invalid observation_status')
        predicted = number(row['predicted_ng_ml'], label + ' predicted_ng_ml')
        if status in {'blq', 'missing'}:
            if row['observed_ng_ml'] is not None:
                raise ValueError(label + ': BLQ/missing observed_ng_ml must be null, not an imputed value')
            exclusions['blq_unquantified' if status == 'blq' else 'observation_missing'] += 1
            continue
        observed = number(row['observed_ng_ml'], label + ' observed_ng_ml')
        if observed <= 0 or predicted <= 0:
            exclusions['quantified_pair_nonpositive'] += 1
            continue
        # log(p) - log(o) avoids overflow/underflow in p/o.
        eligible[subject].append(math.log(predicted) - math.log(observed))
    if eligible:
        per_subject_means, per_subject_squares = [], []
        for subject in sorted(eligible):
            errors = sorted(eligible[subject])
            per_subject_means.append(math.fsum(errors) / len(errors))
            per_subject_squares.append(math.fsum(e * e for e in errors) / len(errors))
        bias = math.fsum(per_subject_means) / len(eligible)
        rms = math.sqrt(math.fsum(per_subject_squares) / len(eligible))
    else:
        bias = rms = None
    report = {
        'schema_version': REPORT_SCHEMA,
        'metric_version': METRIC_VERSION,
        'status': 'synthetic_metrics_calculated' if eligible else 'no_eligible_synthetic_pairs',
        'purpose': 'synthetic_fixture',
        'fixture_id': document['fixture_id'],
        'input_canonical_sha256': digest(document),
        'input_file_sha256': input_file_sha256,
        'implementation_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'design_protocol_sha256': DESIGN_PROTOCOL_SHA256,
        'design_protocol_status': 'draft_not_locked_or_approved',
        'counts': {
            'input_rows': len(rows),
            'input_subjects': len(participants),
            'eligible_rows': sum(len(values) for values in eligible.values()),
            'eligible_subjects': len(eligible),
            'subjects_without_eligible_pairs': len(participants) - len(eligible),
            'excluded_rows': sum(exclusions.values()),
            'exclusions_by_reason': {key: exclusions.get(key, 0) for key in
                ('blq_unquantified', 'observation_missing', 'quantified_pair_nonpositive')},
        },
        'metrics': {
            'subject_balanced_mean_log_ratio': bias,
            'subject_balanced_root_mean_square_log_ratio': rms,
            'unit': 'dimensionless',
            'weighting': 'Equal weight for each eligible subject; equal sample weight within subject',
            'log_error_definition': 'ln(predicted_ng_ml) - ln(observed_ng_ml)',
            'bias_definition': 'mean_over_subjects(mean_within_subject(log_error))',
            'rms_definition': 'sqrt(mean_over_subjects(mean_within_subject(log_error_squared)))',
        },
        'acceptance_thresholds': None,
        'performance_acceptance_decision': 'not_assessed',
        'clinical_prediction_validated': False,
        'ready_for_patient_simulation': False,
        'empirical_validation_performed': False,
        'model_simulation_run': False,
        'prediction_provenance_independently_verified': False,
        'database_accessed': False,
        'network_accessed': False,
        'limitation': 'Synthetic arithmetic preview only. Supplied predictions are not generated or verified. '
                      'Exclusion rules are fixture-only and are not an approved empirical analysis plan. '
                      'No confidence interval, individual variability, source reproduction, efficacy, '
                      'toxicity or dose recommendation is established.',
    }
    report['report_sha256'] = digest(report)
    return report


def example_document():
    rows = []
    for subject, sample, time, status, obs, pred in [
        ('SYN-A', '1', 1, 'quantified', 10, 20),
        ('SYN-A', '2', 2, 'quantified', 20, 40),
        ('SYN-B', '1', 1, 'quantified', 20, 10),
        ('SYN-C', '1', 1, 'blq', None, 2),
        ('SYN-D', '1', 1, 'missing', None, 3),
        ('SYN-E', '1', 1, 'quantified', 0, 1),
    ]:
        rows.append(dict(subject_id=subject, sample_id=sample, observed_time_h=time,
                         predicted_time_h=time, observation_status=status,
                         observed_ng_ml=obs, predicted_ng_ml=pred,
                         observed_source_ref='invented-fixture-observation',
                         predicted_source_ref='invented-fixture-prediction'))
    return dict(schema_version=INPUT_SCHEMA, purpose='synthetic_fixture',
                fixture_id='unequal-sample-counts-demo-v1', concentration_unit='ng/mL',
                pairing_method='explicit_same_time_synthetic_pairs',
                prediction_method='supplied_synthetic_values_no_fitting', rows=rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--example', action='store_true', help='Calculate using invented built-in pairs')
    mode.add_argument('--input-file', type=Path, help='Read synthetic paired-concentration JSON')
    parser.add_argument('--output', type=Path, help='Create a new report file; never overwrite')
    args = parser.parse_args(argv)
    try:
        document, raw_sha = (example_document(), None) if args.example else load_document(args.input_file)
        report = calculate_preview(document, raw_sha)
        rendered = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
        if args.output:
            with args.output.open('x', encoding='utf-8') as stream:
                stream.write(rendered)
        sys.stdout.write(rendered)
        return 0 if report['status'] == 'synthetic_metrics_calculated' else 2
    except (OSError, ValueError, RecursionError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
