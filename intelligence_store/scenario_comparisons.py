"""Descriptive comparison of two immutable synthetic reference analyses."""
import copy
from .saved_scenarios import read_scenario
from .regulatory import digest

METHOD = 'saved-scenario-comparison-v1.0'
FIELDS = {'selected_drug':'Reference drug ID', 'age_years':'Age (years)',
    'biological_sex':'Biological sex', 'weight_kg':'Weight (kg)',
    'egfr_ml_min_1_73m2':'eGFR (mL/min/1.73 m²)', 'dose_value':'Entered dose value',
    'dose_unit':'Entered dose unit', 'indication':'Indication context', 'medications':'Medication names'}
PROVENANCE = ('method_version', 'summary_method_version', 'criteria_method_version',
    'alias_catalog_version', 'alias_catalog_sha256', 'safety_catalog_version',
    'safety_catalog_sha256', 'interaction_catalog_version', 'interaction_catalog_sha256')


def compare_scenarios(left_id, right_id):
    if any(type(v) is not int or v < 1 for v in (left_id, right_id)) or left_id == right_id:
        raise ValueError('Choose two distinct saved scenario IDs.')
    rows = [read_scenario(v) for v in (left_id, right_id)]
    if any(row is None for row in rows):
        raise LookupError('A selected saved scenario does not exist.')
    reports = [row.payload['analysis']['report'] for row in rows]
    a, b = reports
    same_cohort = a['cohort']['id'] == b['cohort']['id']
    same_manifest = rows[0].payload['analysis']['source_manifest_sha256'] == rows[1].payload['analysis']['source_manifest_sha256']
    differing_methods = [k for k in PROVENANCE if a['provenance'].get(k) != b['provenance'].get(k)]
    sets = [set(r['reference_trials']['nct_ids']) for r in reports]
    groups = [{g['key']: g['count'] for g in r['criteria']['groups']['combined']} for r in reports]
    counts = [
        ('Whole source cohort', [r['total_trials'] for r in reports]),
        ('Studies reporting the reference name', [r['reference_trials']['count'] for r in reports]),
        ('Recruiting records reporting the name', [r['recruiting_reference_trials']['count'] for r in reports]),
        ('Age/sex criteria denominator (selected-name studies)', [r['criteria']['denominator'] for r in reports]),
        *[(label, [g[key] for g in groups]) for key, label in (
            ('within','Within reported age/sex fields'), ('outside','Outside a reported field'),
            ('unresolved','Unresolved age/sex comparison'))],
        *[(label, [r['medication_coverage'][key] for r in reports]) for key, label in (
            ('entered_unique','Unique entered medication names'), ('selected_references','Names with selected pair references'),
            ('unassessed','Unassessed medication names'), ('same_reference_name','Names in selected reference group'))]
    ]
    overlap = sorted(sets[0] & sets[1])
    payload = {'method_version': METHOD,
        'scenarios': [{'id':row.id, 'payload_sha256':row.payload_sha256, 'payload':copy.deepcopy(row.payload)} for row in rows],
        'context': {'same_cohort_id':same_cohort, 'same_source_manifest':same_manifest,
                    'differing_provenance_fields':differing_methods,
                    'same_evidence_and_methods':same_cohort and same_manifest and not differing_methods},
        'input_rows': [{'field':key, 'label':label, 'values':[r['profile'][key] for r in reports],
                        'different':a['profile'][key] != b['profile'][key]} for key,label in FIELDS.items()],
        'count_rows': [{'label':label,'values':values} for label,values in counts],
        'selected_name_overlap': {'count':len(overlap), 'nct_ids':overlap,
            'note':'NCT identity overlap only. Each side retains its own snapshot and source context; counts must not be added as unique studies.'},
        'limitation':'Descriptive comparison of frozen synthetic reference reports. Counts are not clinical risk, efficacy, compatibility or full eligibility scores. Different drugs can have different study subsets. No treatment ranking, causal effect or statistical comparison is calculated. PK curves are not included.'}
    payload['comparison_sha256'] = digest(payload)
    return payload
