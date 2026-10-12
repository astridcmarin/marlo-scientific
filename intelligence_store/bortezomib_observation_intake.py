"""Review extraction completeness; never fit, simulate or certify observations."""
import hashlib
import json
import math
from pathlib import Path

SCHEMA = 'bortezomib-paired-observation-intake-v1'
MODEL_PIN = 'ac5e3ad9a9cb8156ca019ba0b9bf31956b96c973631e595ebafabdc4166b59be'
MODEL_PATH = Path(__file__).with_name('data') / 'bortezomib_proteasome_reference_v1.json'
TEMPLATE_PATH = Path(__file__).with_name('data') / 'bortezomib_observation_template_v1.json'


def load_json(path):
    """Strict JSON: reject duplicate fields and nonfinite literals."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON field: ' + key)
            result[key] = value
        return result
    def bad(value):
        raise ValueError('Nonfinite JSON literal: ' + value)
    return json.loads(Path(path).read_text(encoding='utf-8'),
                      object_pairs_hook=unique, parse_constant=bad)


def number(value, minimum=None):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value) and (minimum is None or value >= minimum)
    except OverflowError:
        return False


def filled(value):
    return isinstance(value, str) and bool(value.strip())


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def review_intake(document, *, verified_archive_hashes=None):
    """Caller supplies hashes of archived bytes; declarations alone are insufficient.

    Complete records are eligible only for manual comparison review. Neither a
    software pass nor self-declared source review resolves the Step105 mismatch.
    """
    if not isinstance(document, dict) or document.get('schema_version') != SCHEMA:
        raise ValueError('Unsupported observation intake schema')
    raw = MODEL_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MODEL_PIN:
        raise ValueError('Step104 model reference changed; intake review withheld')
    model = json.loads(raw)
    problems = []
    def require(condition, code):
        if not condition:
            problems.append(code)
    require(document.get('drug_id') == 'bortezomib', 'drug_identity_not_supported')
    require(document.get('data_origin') == 'published_observations', 'not_published_observations')
    require(document.get('relationship_to_model') in (
        'model_development_data', 'independent_dataset'), 'dataset_relationship_unresolved')
    checks = document.get('source_review')
    checks = checks if isinstance(checks, dict) else {}
    for field in ('series_selection', 'normalization', 'aggregation', 'population_and_schedule'):
        item = checks.get(field)
        item = item if isinstance(item, dict) else {}
        require(item.get('status') == 'reviewed' and filled(item.get('source_location'))
                and filled(item.get('rationale')), field + '_review_pending')
    require(filled(checks.get('reviewer')) and filled(checks.get('reviewed_on')),
            'review_attribution_missing')
    sources = document.get('sources')
    if not isinstance(sources, list):
        raise ValueError('sources must be an array')
    require(bool(sources), 'source_records_missing')
    source_map = {}
    verified = verified_archive_hashes or {}
    for i, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError('Each source must be an object')
        sid = source.get('id')
        require(filled(sid) and sid not in source_map, f'source_{i}_identity_invalid')
        if not filled(sid) or sid in source_map:
            continue
        source_map[sid] = source
        require(all(filled(source.get(k)) for k in ('doi', 'citation', 'location')),
                f'source_{i}_citation_incomplete')
        sha = source.get('sha256')
        require(isinstance(sha, str) and len(sha) == 64 and all(c in '0123456789abcdef' for c in sha),
                f'source_{i}_hash_invalid')
        require(sha is not None and verified.get(sid) == sha,
                f'source_{i}_archive_not_verified')
        if source.get('doi') == '10.1007/s00280-010-1283-3':
            require(document.get('relationship_to_model') == 'model_development_data',
                    'development_source_cannot_be_external_validation')
    rows = document.get('observations')
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ValueError('observations must be an array with at most 10000 records')
    require(bool(rows), 'matched_observations_missing')
    ids = set()
    signatures = set()
    accepted = []
    warnings = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError('Each observation must be an object')
        local = []
        def check(ok, code):
            if not ok:
                local.append(code)
        rid = row.get('id')
        check(filled(rid) and rid not in ids, 'row_identity_missing_or_duplicate')
        if filled(rid):
            ids.add(rid)
        check(filled(row.get('source_id')) and row['source_id'] in source_map, 'unknown_source')
        check(row.get('aggregation') in ('individual', 'group_mean_at_time'),
              'peaks_or_unsupported_aggregation')
        check(all(filled(row.get(k)) for k in ('series_id', 'subject_or_group_id', 'visit_id',
              'arm', 'population', 'schedule', 'pairing_evidence_location')), 'series_context_incomplete')
        check(row.get('route') == 'IV' and number(row.get('dose_mg_per_m2'), 0)
              and row.get('dose_mg_per_m2', 0) > 0, 'route_or_dose_unresolved')
        a = row.get('concentration'); b = row.get('response')
        a = a if isinstance(a, dict) else {}
        b = b if isinstance(b, dict) else {}
        check(a.get('quantity') == 'plasma_total_bortezomib' and a.get('unit') == 'nM',
              'concentration_basis_or_units_incompatible')
        check(number(a.get('value'), 0), 'concentration_invalid')
        check(b.get('quantity') in ('20S_activity_percent_of_baseline',
              '20S_inhibition_percentage_points'), 'response_definition_incompatible')
        check(number(b.get('value')), 'response_invalid')
        check(number(a.get('time_h'), 0) and number(b.get('time_h'), 0)
              and a.get('time_h') == b.get('time_h'), 'sampling_times_not_matched')
        for name, item in (('concentration', a), ('response', b)):
            check(filled(item.get('source_location')), name + '_location_missing')
            check(number(item.get('extraction_uncertainty'), 0)
                  and item.get('uncertainty_kind') == 'absolute_digitization_bound',
                  name + '_extraction_uncertainty_missing')
        n = row.get('endpoint_n')
        check(type(n) is int and n > 0, 'endpoint_denominator_missing')
        if row.get('aggregation') == 'individual':
            check(n == 1, 'individual_record_requires_n_1')
        signature = tuple(row.get(k) for k in ('source_id', 'series_id', 'subject_or_group_id', 'visit_id')) + (a.get('time_h'),)
        # Avoid trusting unhashable fields supplied by malformed JSON.
        try:
            check(signature not in signatures, 'duplicate_sampling_record')
            signatures.add(signature)
        except TypeError:
            check(False, 'sampling_context_invalid')
        if local:
            problems.extend(f'row_{i}:{code}' for code in local)
        else:
            activity = b['value'] if b['quantity'] == '20S_activity_percent_of_baseline' else 100 - b['value']
            accepted.append({'id': rid, 'time_h': a['time_h'],
                'concentration_nm': a['value'], 'activity_percent_of_baseline': activity,
                'aggregation': row['aggregation'], 'endpoint_n': n})
            if activity < 0 or activity > 100:
                warnings.append(f'row_{i}:activity_outside_nominal_baseline_range')
    report = {'schema_version': 'bortezomib-intake-readiness-report-v1',
        'status': 'manual_comparison_review_required' if not problems else 'evidence_incomplete',
        'input_sha256': digest(document), 'model_reference_sha256': MODEL_PIN,
        'model_source_doi': model['source']['doi'],
        'dataset_relationship': document.get('relationship_to_model'),
        'submitted_record_count': len(rows), 'structurally_matched_record_count': len(accepted),
        'eligible_for_manual_comparison_review': not problems,
        'blocking_issues': problems, 'warnings': warnings,
        'normalized_records': accepted, 'declared_source_review': checks,
        'archived_source_hashes': {k: verified[k] for k in source_map if k in verified},
        'observed_concentration_domain_nm':
            [min(r['concentration_nm'] for r in accepted), max(r['concentration_nm'] for r in accepted)]
            if accepted and not problems else None,
        'pairing_scope': 'same declared source series, sampling time and subject/group; declarations require source review',
        'rmse': None, 'mae': None, 'fitting_performed': False,
        'step105_discrepancy_resolved': False, 'clinical_prediction_validated': False,
        'ready_for_patient_simulation': False,
        'limitations': ['A structural pass does not verify source truth, pairing, compatibility or model validity.',
            'Extraction uncertainty is recorded, not propagated.',
            'Group means are not individual observations; no efficacy or toxicity is inferred.']}
    report['report_sha256'] = digest(report)
    return report
