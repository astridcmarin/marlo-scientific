"""Phase 2.5b: model scope for the two lenalidomide models (Hughes 2019, Kim 2026).

Each model's covariates (Hughes: Cockcroft-Gault creatinine clearance and fat-free mass with a declared weight basis;
Kim: CKD-EPI 2021 indexed eGFR and Du Bois BSA) come from its own estimator; the pinned scope file then decides, rule
by rule, whether the record is inside the model's scope and with which evidence tier. Where a rule names observed
data (the CC-5013-PK-001 renal-function groups from the EMA assessment), those group values are attached, labelled
as observations from other subjects. Nothing here changes a model calculation.
"""
import hashlib
import json
from pathlib import Path

from .covariate_estimation import estimate_hughes_covariates
from .kim_model import estimate_kim_covariates
from .model_scope import evaluate, load_scope
from .patient_state import digest

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).parent / 'data'
HUGHES_SCOPE_PATH = DATA / 'lenalidomide_hughes_scope_v2.json'
HUGHES_SCOPE_SHA256 = 'acc86c652649d09db0bd90a19ed3ceeae2728eb22c9bc733f185767ccffbd149'
KIM_SCOPE_PATH = DATA / 'lenalidomide_kim_scope_v3.json'
KIM_SCOPE_SHA256 = 'b2c1b49511d6132cae5d6cb27c52f8fe747247218ecac94d0f387abac0ab2b3c'
# Superseded scopes, kept unchanged and pinned for traceability (file name -> SHA-256).
#   Kim v1: moderate band not flagged; Kim v2: moderate band flagged (2.1f); Hughes v1: outside study population not recorded.
SUPERSEDED_SCOPES = {
    'lenalidomide_kim_scope_v1.json': 'a2d510ba6b16926e436ee644828dce41d3bfa7b3c8abd868d303e0ce8491bb01',
    'lenalidomide_kim_scope_v2.json': 'afaf3890ed225b6e5d2dae6a6998a90d79d0e650a171103979b7a1a829d9406a',
    'lenalidomide_hughes_scope_v1.json': 'e89c34106bee1a0187bbcb02c72f0b1faffdc246b388a5f3a2908d2736977b93',
}
RENAL_EVIDENCE_PATH = ROOT / 'landscape_ui' / 'data' / 'renal_pk' / 'renal_pk_group_evidence_v2.json'
RENAL_EVIDENCE_SHA256 = '38d164869ff2a4cf43c9b4b437efc0eb172fab29dc80451e3e794b7d7c2c8832'
# Renal evidence v1 (population "not established") is superseded by v2 and kept unchanged: locked plans, reports and
# extraction review queue v1 cite it. Its groups and values are identical to v2's (tests/test_renal_pk_evidence_pages.py).
SUPERSEDED_RENAL_EVIDENCE_PATH = ROOT / 'landscape_ui' / 'data' / 'renal_pk' / 'renal_pk_group_evidence_v1.json'
SUPERSEDED_RENAL_EVIDENCE_SHA256 = 'bb5a71f3a989ddfbf6ef1c6e855a18468f38888cdd3d6cc5835fe8bf6b1bed89'
SCHEMA_VERSION = 'lenalidomide-scope-evaluation-v1'


def load_hughes_scope():
    return load_scope(HUGHES_SCOPE_PATH, HUGHES_SCOPE_SHA256)


def load_kim_scope():
    return load_scope(KIM_SCOPE_PATH, KIM_SCOPE_SHA256)


def _renal_evidence():
    raw = RENAL_EVIDENCE_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != RENAL_EVIDENCE_SHA256:
        raise ValueError('Renal-function group evidence is missing or changed.')
    return json.loads(raw)


def _crcl_text(r):
    lo, hi = r['lower'], r['upper']
    if lo is None:
        return f'< {hi} {r["unit"]}'
    if hi is None:
        return f'> {lo} {r["unit"]}'
    return f'{lo}-{hi} {r["unit"]}'


def observed_groups(spec):
    if spec['source'] != 'renal_pk_group_evidence':
        raise ValueError('Unknown observed-data source.')
    evidence = _renal_evidence()
    groups = {g['group']: g for g in evidence['groups']}
    ref = groups[spec['reference_group']]['measurements']['auc_infinity']
    rows = []
    for name in spec['groups']:
        g = groups[name]
        auc = g['measurements']['auc_infinity']
        rows.append({'group': name, 'creatinine_clearance': _crcl_text(g['crcl_range']), 'n': g['n'],
                     'auc_infinity_mean': auc['mean'], 'auc_infinity_sd': auc['sd'], 'unit': auc['unit'],
                     'ratio_to_reference_mean': auc['mean'] / ref['mean']})
    return {'kind': 'observed_group_values_from_other_subjects', 'study': evidence['study_id'],
            'source': evidence['source']['title'] + ' (' + evidence['source']['document_reference'] + ')',
            'design': f'Single {evidence["design"]["dose_mg"]} mg oral dose, {evidence["design"]["food_state"]}',
            'population': evidence['population']['summary'],
            'reference_group': spec['reference_group'],
            'reference_creatinine_clearance': _crcl_text(groups[spec['reference_group']]['crcl_range']),
            'reference_auc_infinity_mean': ref['mean'], 'groups': rows,
            'not_this': 'Arithmetic means of small groups of other subjects after one 25 mg dose; not a prediction for this record.'}


def _attach(evaluation):
    observed = []
    for rule in evaluation['rules']:
        if 'observed' in rule:
            observed.append(dict(observed_groups(rule['observed']), triggered_by=rule['id'], tier=rule.get('tier'),
                                 status=rule['status']))
    return observed


def _result(model_id, scope_sha, estimate, evaluation):
    result = {'schema_version': SCHEMA_VERSION, 'model_id': model_id, 'scope_sha256': scope_sha,
              'covariate_estimate_sha256': estimate['report_sha256'], 'state_sha256': estimate['state_sha256'],
              'scope_evaluation': evaluation, 'observed': _attach(evaluation), 'clinical_prediction_validated': False}
    result['result_sha256'] = digest(result)
    return result


def hughes_scope(state, weight_basis, disease_code):
    estimate = estimate_hughes_covariates(state, weight_basis)
    derived = {}
    if estimate['status'] == 'estimated':
        derived = {k: estimate['estimates'][k]['value'] for k in ('creatinine_clearance', 'fat_free_mass')}
    evaluation = evaluate(load_hughes_scope(), estimate_state(state), {'disease_code': disease_code}, derived)
    evaluation['weight_basis'] = weight_basis
    return _result('lenalidomide_hughes_2019', HUGHES_SCOPE_SHA256, estimate, evaluation)


def kim_scope(state, disease_code):
    estimate = estimate_kim_covariates(state)
    derived = {}
    if estimate['status'] == 'estimated':
        derived = {k: estimate['estimates'][k]['value'] for k in ('egfr_indexed', 'body_surface_area')}
    evaluation = evaluate(load_kim_scope(), estimate_state(state), {'disease_code': disease_code}, derived)
    return _result('lenalidomide_kim_2026', KIM_SCOPE_SHA256, estimate, evaluation)


def estimate_state(state):
    from .patient_state import validate_patient_state
    return validate_patient_state(state)
