#!/usr/bin/env python3
"""Exact-time analytic concentration reference for synthetic eight-stage fixtures."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import pk_prediction_metrics_preview as metrics

SCHEMA = 'synthetic-eight-stage-time-evaluation-v1'
METHOD = 'synthetic-eight-stage-analytic-time-v1.0'
MAX_SUBJECTS = 100
MAX_SAMPLES = 10_000


def bounded(value, label, lower, upper):
    value = metrics.number(value, label)
    if not lower <= value <= upper:
        raise ValueError(f'{label}: outside mathematical implementation bounds [{lower}, {upper}]')
    return value


def validate_parameters(parameters, label):
    metrics.exact_keys(parameters, {'apparent_clearance_l_h', 'apparent_volume_l', 'transit_rate_h'}, label)
    cl = bounded(parameters['apparent_clearance_l_h'], label + ' clearance', 0.01, 1000)
    volume = bounded(parameters['apparent_volume_l'], label + ' volume', 1, 1000)
    ktr = bounded(parameters['transit_rate_h'], label + ' transit rate', 0.01, 20)
    ke = cl / volume
    if ke > ktr:
        raise ValueError(label + ': elimination rate must not exceed transit rate in this reference implementation')
    return cl, volume, ktr


def validate_events(events, label):
    if not isinstance(events, list) or not 1 <= len(events) <= 4:
        raise ValueError(label + ': require one to four events')
    result = []
    for i, event in enumerate(events):
        metrics.exact_keys(event, {'time_h', 'amount_mg', 'source_ref'}, label + ' event')
        time = bounded(event['time_h'], label + ' event time', 0, 72)
        if time != 24 * i:
            raise ValueError(label + ': event times must be 0, 24, 48, 72 in that order; history is not inferred')
        amount = bounded(event['amount_mg'], label + ' event amount', 0.001, 1000)
        metrics.text_value(event['source_ref'], label + ' event source_ref', 500)
        result.append((time, amount))
    return result


def _central_fraction(age, ktr, ke):
    if age == 0:
        return 0.0
    z = ktr * age
    x = (ktr - ke) * age
    if x < 10:
        # Stable convolution expression, including the ke == ktr limit.
        # S(x) = sum_{j>=0} 8! * x^j / (8+j)!; no subtraction or division by x.
        term = total = 1.0
        for j in range(1, 200):
            term *= x / (8 + j)
            total += term
            if term <= 1e-17 * total:
                break
        else:
            raise ValueError('Analytic reference series did not converge')
        return math.exp(-z) * z**8 / math.factorial(8) * total
    tail = 1 - math.exp(-x) * math.fsum(x**j / math.factorial(j) for j in range(8))
    return (ktr / (ktr - ke))**8 * math.exp(-ke * age) * tail


def concentration_at_time(time_h, events, cl, volume, ktr):
    """Internal primitive for validated inputs: eight precentral boxes, then central."""
    ke = cl / volume
    central = math.fsum(amount * _central_fraction(time_h - t, ktr, ke)
                        for t, amount in events if t <= time_h)
    concentration = 1000 * central / volume
    if not math.isfinite(concentration) or concentration < 0:
        raise ValueError('Analytic reference produced invalid concentration')
    return concentration


def evaluate_document(document, input_file_sha256=None):
    metrics.exact_keys(document, {'schema_version', 'purpose', 'fixture_id', 'model_kind',
                                 'initial_amounts', 'subjects'}, 'document')
    if document['schema_version'] != SCHEMA or document['purpose'] != 'synthetic_fixture':
        raise ValueError('Only versioned synthetic fixtures are accepted; real data are out of scope')
    metrics.text_value(document['fixture_id'], 'fixture_id')
    if document['model_kind'] != 'generic_eight_stage_mathematical_reference':
        raise ValueError('model_kind must declare generic_eight_stage_mathematical_reference')
    if document['initial_amounts'] != 'all_zero_explicit_synthetic_assumption':
        raise ValueError('Initial amounts must be explicitly declared zero for this synthetic fixture')
    subjects = document['subjects']
    if not isinstance(subjects, list) or not 1 <= len(subjects) <= MAX_SUBJECTS:
        raise ValueError('Require 1 to 100 synthetic subjects')
    seen, validated, sample_total = set(), [], 0
    for index, subject in enumerate(subjects, 1):
        label = f'subject {index}'
        metrics.exact_keys(subject, {'subject_id', 'parameters', 'parameter_source_ref', 'events', 'samples'}, label)
        sid = metrics.text_value(subject['subject_id'], label + ' subject_id')
        if sid in seen:
            raise ValueError(label + ': duplicate subject_id')
        seen.add(sid)
        metrics.text_value(subject['parameter_source_ref'], label + ' parameter_source_ref', 500)
        parameters = validate_parameters(subject['parameters'], label + ' parameters')
        events = validate_events(subject['events'], label)
        samples = subject['samples']
        if not isinstance(samples, list) or not samples:
            raise ValueError(label + ': samples must be a nonempty list')
        sample_total += len(samples)
        if sample_total > MAX_SAMPLES:
            raise ValueError('Total sample count exceeds 10000')
        sample_ids = set()
        validated_samples = []
        for row in samples:
            metrics.exact_keys(row, {'sample_id', 'time_h', 'observation_status', 'observed_ng_ml', 'source_ref'}, label + ' sample')
            sample_id = metrics.text_value(row['sample_id'], label + ' sample_id')
            if sample_id in sample_ids:
                raise ValueError(label + ': duplicate sample_id')
            sample_ids.add(sample_id)
            time = bounded(row['time_h'], label + ' sample time', 0, 72)
            metrics.text_value(row['source_ref'], label + ' observation source_ref', 500)
            status = row['observation_status']
            if not isinstance(status, str) or status not in metrics.STATUSES:
                raise ValueError(label + ': invalid observation status')
            if status == 'quantified':
                metrics.number(row['observed_ng_ml'], label + ' observed concentration')
            elif row['observed_ng_ml'] is not None:
                raise ValueError(label + ': BLQ/missing concentration must be null')
            validated_samples.append((row, time))
        validated.append((sid, parameters, events, validated_samples))
    # No prediction is calculated until the entire fixture has passed validation.
    source_digest = metrics.digest(document)
    rows = []
    for sid, (cl, volume, ktr), events, samples in validated:
        for sample, time in samples:
            rows.append(dict(subject_id=sid, sample_id=sample['sample_id'],
                             observed_time_h=time, predicted_time_h=time,
                             observation_status=sample['observation_status'],
                             observed_ng_ml=sample['observed_ng_ml'],
                             predicted_ng_ml=concentration_at_time(time, events, cl, volume, ktr),
                             observed_source_ref=sample['source_ref'],
                             predicted_source_ref=f'{METHOD}; input-sha256:{source_digest}'))
    paired = dict(schema_version=metrics.INPUT_SCHEMA, purpose='synthetic_fixture',
                  fixture_id=document['fixture_id'], concentration_unit='ng/mL',
                  pairing_method='explicit_same_time_synthetic_pairs',
                  prediction_method='supplied_synthetic_values_no_fitting', rows=rows)
    metric_report = metrics.calculate_preview(paired)
    report = {
        'schema_version': 'synthetic-exact-time-reference-report-v1',
        'method_version': METHOD,
        'status': 'synthetic_reference_evaluated',
        'purpose': 'synthetic_fixture',
        'fixture_id': document['fixture_id'],
        'input_file_sha256': input_file_sha256,
        'input_canonical_sha256': source_digest,
        'implementation_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'model_kind': document['model_kind'],
        'equation': 'Eight serial first-order precentral boxes with equal rate KTR; one central box eliminated at CL/V',
        'time_method': 'Closed-form linear superposition at each explicit sample time; no rounding, grid lookup or interpolation',
        'structure': {'precentral_boxes': 8, 'central_boxes': 1, 'initial_amounts_mg': 0},
        'synthetic_model_reference_calculated': True,
        'production_pk_solver_run': False,
        'events_in_input': sum(len(events) for _, _, events, _ in validated),
        'sample_count': len(rows),
        'generated_pairs': paired,
        'metric_report': metric_report,
        'clinical_prediction_validated': False,
        'ready_for_patient_simulation': False,
        'empirical_validation_performed': False,
        'source_model_reproduction_established': False,
        'database_accessed': False,
        'network_accessed': False,
        'limitation': 'Synthetic mathematical reference only. Supplied parameters and observations are not verified patient estimates or measurements. '
                      'No drug applicability, covariate derivation, source estimation replay, variability, efficacy, toxicity or dose suitability is established. '
                      'The production execution contract and scientific gates remain unchanged. Full generated synthetic pairs are included in this report.',
    }
    report['report_sha256'] = metrics.digest(report)
    return report


def example_document():
    parameters = dict(apparent_clearance_l_h=2, apparent_volume_l=10, transit_rate_h=1)
    events = [dict(time_h=0, amount_mg=1, source_ref='invented-administration')]
    # Deliberately invented observations, not calculated to force a perfect metric.
    samples = [dict(sample_id=str(i), time_h=t, observation_status='quantified',
                    observed_ng_ml=obs, source_ref='invented-observation')
               for i, (t, obs) in enumerate(((0.137, 0.000001), (1.037, 0.002),
                                              (7.253, 25), (24.037, 4)), 1)]
    return dict(schema_version=SCHEMA, purpose='synthetic_fixture',
                fixture_id='off-grid-eight-stage-demo-v1',
                model_kind='generic_eight_stage_mathematical_reference',
                initial_amounts='all_zero_explicit_synthetic_assumption',
                subjects=[dict(subject_id='SYN-A', parameters=parameters,
                               parameter_source_ref='invented-mathematical-inputs', events=events, samples=samples)])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--example', action='store_true')
    mode.add_argument('--input-file', type=Path)
    parser.add_argument('--output', type=Path, help='Create a new report; never overwrite')
    args = parser.parse_args(argv)
    try:
        document, raw_sha = (example_document(), None) if args.example else metrics.load_document(args.input_file)
        report = evaluate_document(document, raw_sha)
        rendered = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
        if args.output:
            with args.output.open('x', encoding='utf-8') as stream:
                stream.write(rendered)
        sys.stdout.write(rendered)
        return 0 if report['metric_report']['status'] == 'synthetic_metrics_calculated' else 2
    except (OSError, ValueError, RecursionError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
