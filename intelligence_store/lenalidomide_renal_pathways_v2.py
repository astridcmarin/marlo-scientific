"""Simulation 2.0d: lenalidomide renal pathways v2, in which tubular secretion falls faster than filtration.

Built and run as the locked plan states (lenalidomide_renal_pathways_plan_v2.json). Secretion is
S_ref * (CrCl / CrCl_ref) ** k; everything else is the 2.0a calibration the body map uses, so k = 1 is the current
model. One parameter, k, is fitted on CC-5013-PK-001's impaired groups only. The model is then compared with Bridoux 2016
and Kim 2026, two myeloma studies the analyst has seen but no fit has used: neither comparison is blind.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

from scipy.stats import t as student_t

from .lenalidomide_renal_pathways import calibrate, pathways
from .patient_state import digest

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'lenalidomide_renal_pathways_plan_v2.json'
PLAN_SHA256 = 'fd97319efd3b44e84e6e3ef994179803b86d262c544e2feb6a71be66eb0c6ad8'
REPORT_PATH = ROOT / 'docs' / 'verification' / 'lenalidomide_renal_pathways_check_v2.json'
SCHEMA_VERSION = 'lenalidomide-renal-pathways-check-report-v2'
METHOD_VERSION = 'lenalidomide-renal-pathways-v2.0'
CRCL_REF = 110.0
FU = 0.77
K_BOUNDS = (0.0, 8.0)
FIT_GROUPS = (('mild', 'mild'), ('moderate', 'moderate'), ('severe_without_dialysis', 'severe'))  # evidence name, Chen name
BRIDOUX_GROUPS = ('normal', 'mild', 'moderate', 'severe')
KIM_GROUPS = ('control', 'moderate', 'severe')
DECIDING = (('bridoux', 'moderate'), ('bridoux', 'severe'), ('kim', 'moderate'), ('kim', 'severe'))


class RenalPathwaysV2Error(ValueError):
    pass


def _pinned(path, sha, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        raise RenalPathwaysV2Error(f'{label} is missing or changed; nothing was computed.')
    return json.loads(raw)


def load_plan():
    plan = _pinned(PLAN_PATH, PLAN_SHA256, 'Renal pathways plan v2')
    if plan['status'] != 'locked_before_computation':
        raise RenalPathwaysV2Error('The renal pathways v2 plan is not locked.')
    return plan


def load_inputs(plan=None):
    plan = plan or load_plan()
    return {name: _pinned(ROOT / ref['file'], ref['sha256'], name) for name, ref in plan['pinned_inputs'].items()}


# ---------------------------------------------------------------- the model
def clearances_v2(cal, crcl, k):
    """Pathway clearances (mL/min) with secretion S_ref * (CrCl / CrCl_ref) ** k."""
    if not (math.isfinite(crcl) and crcl > 0):
        raise RenalPathwaysV2Error('Creatinine clearance must be a finite positive number.')
    filtration = cal['fu'] * crcl
    secretion = cal['secretion_ml_min'] * (crcl / cal['crcl_ml_min']) ** k
    renal = filtration + secretion
    total = renal + cal['non_renal_ml_min']
    return {'crcl_ml_min': crcl, 'filtration_ml_min': filtration, 'secretion_ml_min': secretion, 'renal_ml_min': renal,
            'non_renal_ml_min': cal['non_renal_ml_min'], 'total_ml_min': total, 'fe': renal / total}


def _auc(dose_mg, total_ml_min):
    return dose_mg * 1e6 / (total_ml_min * 60.0)


def _fit_points(inputs, target):
    ev, chen = inputs['pathway_evidence'], inputs['chen_2007_demographics']['sources']['chen_2007']['table_I_demographics']
    dose = ev['study']['dose_mg']
    groups = {g['group']: g for g in ev['groups']}
    pts = []
    for ev_name, chen_name in FIT_GROUPS:
        g = groups[ev_name]
        cl_obs = dose * 1e6 / g['auc_ng_h_ml'][0] / 60.0
        pts.append({'group': ev_name, 'n': g['n'], 'crcl_ml_min': chen[chen_name]['crcl_ml_min_mean'], 'dose_mg': dose,
                    'auc_observed': g['auc_ng_h_ml'][0], 'fe_observed': g['fe_percent'] / 100.0,
                    'renal_observed_ml_min': g['fe_percent'] / 100.0 * cl_obs})
    return pts


def _objective(cal, pts, k, target):
    s = 0.0
    for p in pts:
        c = clearances_v2(cal, p['crcl_ml_min'], k)
        if target == 'auc':
            s += p['n'] * (math.log(_auc(p['dose_mg'], c['total_ml_min'])) - math.log(p['auc_observed'])) ** 2
        else:
            s += p['n'] * (math.log(c['renal_ml_min']) - math.log(p['renal_observed_ml_min'])) ** 2
    return s


def fit_k(cal, pts, target='auc'):
    """Grid over the bounds at 0.01, then golden-section refinement to 1e-9 around the best grid point."""
    lo_b, hi_b = K_BOUNDS
    grid = [round(lo_b + 0.01 * i, 10) for i in range(int(round((hi_b - lo_b) / 0.01)) + 1)]
    values = [_objective(cal, pts, k, target) for k in grid]
    best = min(range(len(grid)), key=values.__getitem__)
    lo, hi = max(lo_b, grid[best] - 0.01), min(hi_b, grid[best] + 0.01)
    g = (math.sqrt(5) - 1) / 2
    while hi - lo > 1e-9:
        a, b = hi - g * (hi - lo), lo + g * (hi - lo)
        if _objective(cal, pts, a, target) < _objective(cal, pts, b, target):
            hi = b
        else:
            lo = a
    k = (lo + hi) / 2
    obj = _objective(cal, pts, k, target)
    return {'k': k, 'objective': obj, 'grid_min_objective': min(values), 'not_above_grid': obj <= min(values) + 1e-15,
            'at_bound': k - lo_b < 0.01 or hi_b - k < 0.01}


# ---------------------------------------------------------------- comparisons
def _t(n):
    return float(student_t.ppf(0.95, n - 1))


def _classify(value, ci):
    if value < ci[0]:
        return 'model_under_predicts'
    if value > ci[1]:
        return 'model_over_predicts'
    return 'consistent'


def _bridoux(cal, k, inputs):
    design, obs = inputs['bridoux_design'], inputs['bridoux_observed']
    crcl = design['design']['per_group']['crcl_mean_sd_ml_min']
    out = {}
    for g in BRIDOUX_GROUPS:
        o = obs['groups'][g]
        s = math.sqrt(math.log(1 + (o['auc24_gcv_pct'] / 100.0) ** 2))
        half = _t(o['n']) * s / math.sqrt(o['n'])
        ci = [o['auc24_gm'] * math.exp(-half), o['auc24_gm'] * math.exp(half)]
        c = clearances_v2(cal, crcl[g][0], k)
        model = _auc(o['dose_mg_per_24h'], c['total_ml_min'])
        out[g] = {'crcl_ml_min_cockcroft_gault': crcl[g][0], 'dose_mg_per_24h': o['dose_mg_per_24h'], 'n': o['n'],
                  'endpoint': 'auc24_ng_h_ml', 'model': model, 'observed_gm': o['auc24_gm'], 'observed_gcv_pct': o['auc24_gcv_pct'],
                  'observed_ci90': ci, 'model_over_observed': model / o['auc24_gm'], 'model_fe': c['fe'],
                  'classification': _classify(model, ci)}
    return out



def _kim(cal, k, inputs, indexed=False):
    ext = inputs['kim_extract']['author_reported_groups']
    out = {}
    for g in KIM_GROUPS:
        med = ext['table1_medians'][g]
        crcl = med['egfr'] if indexed else med['egfr'] * med['bsa'] / 1.73
        obs = ext['table2_total_cl_f_l_h'][g]
        n = med['n']
        half = _t(n) * obs['sd'] / math.sqrt(n)
        ci = [obs['mean'] - half, obs['mean'] + half]
        model = clearances_v2(cal, crcl, k)['total_ml_min'] * 60.0 / 1000.0
        out[g] = {'input_ml_min': crcl, 'input_basis': 'median eGFR (indexed)' if indexed else 'median eGFR de-indexed by median BSA',
                  'n': n, 'endpoint': 'total_cl_f_l_h', 'model': model, 'observed_mean': obs['mean'], 'observed_sd': obs['sd'],
                  'observed_ci90': ci, 'model_over_observed': model / obs['mean'], 'classification': _classify(model, ci)}
    return out


def _scenario(plan, inputs, crcl_cal=CRCL_REF, target='auc', kim_indexed=False):
    cal = calibrate(inputs['pathway_evidence'], crcl_cal, FU)
    pts = _fit_points(inputs, target)
    fit = fit_k(cal, pts, target)
    k = fit['k']
    in_sample = []
    for p in pts:
        c = clearances_v2(cal, p['crcl_ml_min'], k)
        c1 = clearances_v2(cal, p['crcl_ml_min'], 1.0)
        in_sample.append({'group': p['group'], 'crcl_ml_min': p['crcl_ml_min'], 'auc_observed': p['auc_observed'],
                          'auc_v2': _auc(p['dose_mg'], c['total_ml_min']), 'auc_v1': _auc(p['dose_mg'], c1['total_ml_min']),
                          'fe_observed': p['fe_observed'], 'fe_v2': c['fe'], 'fe_v1': c1['fe']})
    return {'calibration': cal, 'fit': fit, 'in_sample': in_sample,
            'bridoux': {'v2': _bridoux(cal, k, inputs), 'v1': _bridoux(cal, 1.0, inputs)},
            'kim': {'v2': _kim(cal, k, inputs, kim_indexed), 'v1': _kim(cal, 1.0, inputs, kim_indexed)}}


def _numerical_checks(inputs):
    cal = calibrate(inputs['pathway_evidence'], CRCL_REF, FU)
    worst = 0.0
    for crcl in (5.0, 20.0, 40.0, 65.0, 110.0, 140.0):
        a, b = pathways(cal, crcl, 'A_intact_nephron'), clearances_v2(cal, crcl, 1.0)
        for key in ('filtration_ml_min', 'secretion_ml_min', 'renal_ml_min', 'total_ml_min'):
            worst = max(worst, abs(a[key] - b[key]) / abs(a[key]))
    monotone = all(
        clearances_v2(cal, c2, k)['secretion_ml_min'] <= clearances_v2(cal, c1, k)['secretion_ml_min'] and
        clearances_v2(cal, c2, k)['secretion_ml_min'] >= 0
        for k in (0.0, 0.5, 1.0, 2.0, 4.0, 8.0) for c1, c2 in ((140.0, 110.0), (110.0, 60.0), (60.0, 20.0), (20.0, 2.0)))
    return {'k1_equals_2_0a_reading_a_max_relative_difference': worst, 'k1_equals_2_0a_pass': worst < 1e-12,
            'secretion_non_negative_and_falls_with_crcl_pass': monotone}


def _count(block, groups):
    return sum(block[g]['classification'] == 'consistent' for g in groups)


def run_check():
    plan = load_plan()
    inputs = load_inputs(plan)
    numerics = _numerical_checks(inputs)
    primary = _scenario(plan, inputs)
    if not (numerics['k1_equals_2_0a_pass'] and numerics['secretion_non_negative_and_falls_with_crcl_pass']
            and primary['fit']['not_above_grid']):
        raise RenalPathwaysV2Error(f'Numerical checks failed: {numerics}, {primary["fit"]}')
    sens = {'calibration_at_chen_normal_mean': _scenario(plan, inputs, crcl_cal=inputs['chen_2007_demographics']['sources']['chen_2007']['table_I_demographics']['normal']['crcl_ml_min_mean']),
            'fit_on_renal_clearance': _scenario(plan, inputs, target='renal'),
            'kim_indexed_egfr': _scenario(plan, inputs, kim_indexed=True)}
    deciding = {f'{study}_{g}': primary[study]['v2'][g]['classification'] for study, g in DECIDING}
    n_deciding = sum(v == 'consistent' for v in deciding.values())
    others = {'v2': _count(primary['bridoux']['v2'], ('normal', 'mild')) + _count(primary['kim']['v2'], ('control',)),
              'v1': _count(primary['bridoux']['v1'], ('normal', 'mild')) + _count(primary['kim']['v1'], ('control',))}
    at_bound = primary['fit']['at_bound']
    if not at_bound and n_deciding == 4 and others['v2'] >= others['v1']:
        outcome = 'adopt'
    elif not at_bound and n_deciding == 3:
        outcome = 'partial_reported_not_adopted'
    else:
        outcome = 'fail_recorded'
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'input_sha256': {n: r['sha256'] for n, r in plan['pinned_inputs'].items()},
              'classification': 'checks_on_seen_but_unfitted_data_not_blind',
              'what_is_known_before_computation': plan['what_is_known_before_computation'],
              'numerical_checks': numerics, 'primary': primary, 'sensitivity': sens,
              'decision': {'rule': plan['decision_rule']['adopt'], 'k': primary['fit']['k'], 'k_at_bound': at_bound,
                           'deciding_comparisons': deciding, 'deciding_consistent': n_deciding,
                           'other_groups_consistent': others, 'outcome': outcome,
                           'sensitivity_deciding_consistent': {name: sum(s[st]['v2'][g]['classification'] == 'consistent'
                                                                         for st, g in DECIDING) for name, s in sens.items()}},
              'known_limitations': copy.deepcopy(plan['known_limitations']),
              'clinical_prediction_validated': False, 'ready_for_patient_simulation': False}
    report['report_sha256'] = digest(report)
    return report


def write_report(path=REPORT_PATH):
    report = run_check()
    Path(path).write_text(json.dumps(report, indent=1, ensure_ascii=False, allow_nan=False) + '\n')
    return report
