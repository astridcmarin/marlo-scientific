"""Phase 3.1c: label-based exposure engine (one compartment, typical value) and its internal-consistency check.

A label gives typical apparent clearance and volume, a half-life, a Tmax and exposure at the labelled dose, often
pooled across studies or diseases. This module builds a one-compartment oral curve from those numbers by the
fixed rules of label_exposure_consistency_plan_v1.json (locked before computation), checks that the curve
reproduces the label's own statements, and selects the parameter set the engine may use. A label agreeing with
itself is not validation; outside checks are a separate step.

Oral one-compartment model with first-order absorption, no lag, apparent parameters (F not needed):
  single dose   C(t) = D ka / (V (ka - k)) (e^(-k t) - e^(-ka t))
  steady state  C(t) = D ka / (V (ka - k)) (e^(-k t) / (1 - e^(-k tau)) - e^(-ka t) / (1 - e^(-ka tau)))
ka is derived from the label's single-dose Tmax: Tmax = ln(ka / k) / (ka - k), solved for ka > k.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

import click

from .patient_state import digest

DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'label_exposure_consistency_plan_v1.json'
PLAN_SHA256 = '146854b3471dacf4c5c578143ec99dec2e35e55a589961e5773580fc40bceb54'
LABEL_PATHS = {'pomalidomide': (DATA / 'label_pk_pomalidomide_v1.json',
                                'ce4b9afa97e1ba84b9e7cf802c5da80b8927e5db51c8506dddb0c993d6398417')}
REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'label_exposure_pomalidomide_consistency_v1.json'
SCHEMA_VERSION = 'label-exposure-consistency-report-v1'
METHOD_VERSION = 'label-exposure-v1.0'
TOLERANCE = (0.67, 1.5)
GRID_H = 0.001
PASS_FAIL = ('C1_clearance_vs_exposure', 'C2_half_life', 'C3_steady_state_cmax', 'C4_steady_state_auc')


def _load(path, expected, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'{label} is missing or changed; nothing was run.')
    return json.loads(raw)


def load_plan(path=PLAN_PATH):
    return _load(path, PLAN_SHA256, 'Label consistency plan')


def load_label(drug='pomalidomide', path=None):
    default, pin = LABEL_PATHS[drug]
    return _load(path or default, pin, f'{drug} label extract')


# ---------------------------------------------------------------- model
def ka_from_tmax(tmax_h, k):
    """Solve Tmax = ln(ka/k)/(ka - k) for ka > k by bisection (the right side falls monotonically as ka rises)."""
    tmax_limit = 1.0 / k  # Tmax tends to 1/k as ka approaches k from above
    if not 0 < tmax_h < tmax_limit:
        raise ValueError(f'Tmax {tmax_h} h cannot be reached with k = {k:.4g}/h (needs Tmax < {tmax_limit:.4g} h).')
    f = lambda ka: math.log(ka / k) / (ka - k) - tmax_h
    lo, hi = k * (1 + 1e-9), k * 2.0
    while f(hi) > 0:
        hi *= 2.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-13 * hi:
            break
    return (lo + hi) / 2


def single_dose_ng_ml(t_h, dose_mg, cl_l_h, v_l, ka):
    k = cl_l_h / v_l
    return 1000.0 * dose_mg * ka / (v_l * (ka - k)) * (math.exp(-k * t_h) - math.exp(-ka * t_h)) if t_h >= 0 else 0.0


def steady_state_ng_ml(t_h, dose_mg, tau_h, cl_l_h, v_l, ka):
    k = cl_l_h / v_l
    return 1000.0 * dose_mg * ka / (v_l * (ka - k)) * (math.exp(-k * t_h) / (1 - math.exp(-k * tau_h))
                                                        - math.exp(-ka * t_h) / (1 - math.exp(-ka * tau_h)))


def steady_state_tmax_h(tau_h, cl_l_h, v_l, ka):
    k = cl_l_h / v_l
    return math.log(ka * (1 - math.exp(-k * tau_h)) / (k * (1 - math.exp(-ka * tau_h)))) / (ka - k)


def steady_state_summary(dose_mg, tau_h, cl_l_h, v_l, ka):
    n = int(round(tau_h / GRID_H))
    conc = [steady_state_ng_ml(i * GRID_H, dose_mg, tau_h, cl_l_h, v_l, ka) for i in range(n + 1)]
    i_max = max(range(n + 1), key=conc.__getitem__)
    auc = GRID_H * (sum(conc) - (conc[0] + conc[-1]) / 2)
    return {'cmax_ng_ml': conc[i_max], 'tmax_h_grid': i_max * GRID_H,
            'tmax_h_closed_form': steady_state_tmax_h(tau_h, cl_l_h, v_l, ka),
            'auc_tau_ng_h_ml_trapezoid': auc, 'auc_tau_ng_h_ml_exact': 1000.0 * dose_mg / cl_l_h,
            'ctrough_ng_ml': conc[-1]}


# ---------------------------------------------------------------- parameter sets from the label (plan rules)
def parameter_sets(label):
    v = label['values']
    dose = label['regimen']['dose_mg']
    half_life = v['half_life_h_patients']['value']
    cl_a = 1000.0 * dose / v['auc_tau_ss_mm_4mg_ng_h_ml']['value']
    sets = {
        'A_exposure_derived_mm': {
            'cl_f_l_h': cl_a, 'v_f_l': cl_a * half_life / math.log(2),
            'provenance': {'cl_f_l_h': 'Dose / AUC_tau,ss = 4 mg / 860 ng.h/mL (MM only)',
                           'v_f_l': 'CL/F x 7.5 h / ln 2 (median half-life, MM or KS)'}},
        'B_stated_pooled': {
            'cl_f_l_h': math.sqrt(v['cl_f_l_h']['range'][0] * v['cl_f_l_h']['range'][1]),
            'v_f_l': math.sqrt(v['vd_f_l']['range'][0] * v['vd_f_l']['range'][1]),
            'provenance': {'cl_f_l_h': 'geometric midpoint of 7-10 L/h (MM or KS)',
                           'v_f_l': 'geometric midpoint of 62-138 L (MM or KS)'}}}
    return sets


def _ratio_check(model, label_value, pass_or_fail=True):
    ratio = model / label_value
    return {'model': model, 'label': label_value, 'ratio': ratio,
            'result': (('pass' if TOLERANCE[0] <= ratio <= TOLERANCE[1] else 'fail') if pass_or_fail else None)}


def check_set(pset, label, tmax_for_ka):
    v = label['values']
    dose, tau = label['regimen']['dose_mg'], label['regimen']['interval_h']
    cl, vol = pset['cl_f_l_h'], pset['v_f_l']
    k = cl / vol
    ka = ka_from_tmax(tmax_for_ka, k)
    ss = steady_state_summary(dose, tau, cl, vol, ka)
    lo, hi = v['vd_f_l']['range']
    tmax_lo, tmax_hi = v['tmax_h']['range']
    checks = {
        'C1_clearance_vs_exposure': _ratio_check(cl, 1000.0 * dose / v['auc_tau_ss_mm_4mg_ng_h_ml']['value']),
        'C2_half_life': _ratio_check(math.log(2) / k, v['half_life_h_patients']['value']),
        'C3_steady_state_cmax': _ratio_check(ss['cmax_ng_ml'], v['cmax_ss_mm_4mg_ng_ml']['value']),
        'C4_steady_state_auc': _ratio_check(ss['auc_tau_ng_h_ml_trapezoid'], v['auc_tau_ss_mm_4mg_ng_h_ml']['value']),
        'C5_volume_in_stated_range': {'model': vol, 'label_range': [lo, hi], 'inside': lo <= vol <= hi, 'result': None},
        'C6_tmax': {'model': ss['tmax_h_grid'], 'label_range': [tmax_lo, tmax_hi],
                    'inside': tmax_lo <= ss['tmax_h_grid'] <= tmax_hi, 'result': None}}
    return {'tmax_used_for_ka_h': tmax_for_ka, 'ka_per_h': ka, 'k_per_h': k, 'steady_state': ss, 'checks': checks,
            'passes_c1_to_c4': all(checks[c]['result'] == 'pass' for c in PASS_FAIL)}


def numerical_checks(sets, label):
    """Closed-form steady state against superposition of 60 single doses; grid AUC and Tmax against exact values."""
    dose, tau = label['regimen']['dose_mg'], label['regimen']['interval_h']
    worst_super, worst_auc, worst_tmax = 0.0, 0.0, 0.0
    for pset in sets.values():
        k = pset['cl_f_l_h'] / pset['v_f_l']
        ka = ka_from_tmax(2.5, k)
        for t in (0.0, 0.5, 2.0, 2.5, 6.0, 12.0, 23.9):
            closed = steady_state_ng_ml(t, dose, tau, pset['cl_f_l_h'], pset['v_f_l'], ka)
            summed = math.fsum(single_dose_ng_ml(t + n * tau, dose, pset['cl_f_l_h'], pset['v_f_l'], ka) for n in range(60))
            worst_super = max(worst_super, abs(closed - summed) / closed)
        ss = steady_state_summary(dose, tau, pset['cl_f_l_h'], pset['v_f_l'], ka)
        worst_auc = max(worst_auc, abs(ss['auc_tau_ng_h_ml_trapezoid'] - ss['auc_tau_ng_h_ml_exact']) / ss['auc_tau_ng_h_ml_exact'])
        worst_tmax = max(worst_tmax, abs(ss['tmax_h_grid'] - ss['tmax_h_closed_form']))
        tmax_single = math.log(ka / k) / (ka - k)
        if abs(tmax_single - 2.5) > 1e-9:
            raise ValueError('ka derivation does not reproduce Tmax.')
    return {'superposition_max_relative_difference': worst_super, 'superposition_passed': worst_super < 1e-9,
            'auc_trapezoid_vs_exact_max_relative_difference': worst_auc, 'auc_passed': worst_auc < 1e-6,
            'tmax_grid_vs_closed_form_max_difference_h': worst_tmax, 'tmax_passed': worst_tmax <= GRID_H}


def run_check(drug='pomalidomide'):
    plan = load_plan()
    label = load_label(drug)
    sets = parameter_sets(label)
    tmax_lo, tmax_hi = label['values']['tmax_h']['range']
    primary_tmax = (tmax_lo + tmax_hi) / 2
    results = {}
    for name in plan['parameter_sets']['order_of_preference']:
        pset = sets[name]
        primary = check_set(pset, label, primary_tmax)
        sensitivity = [check_set(pset, label, t) for t in (tmax_lo, tmax_hi)]
        results[name] = {'cl_f_l_h': pset['cl_f_l_h'], 'v_f_l': pset['v_f_l'], 'provenance': pset['provenance'],
                         'primary': primary,
                         'sensitivity': [{'tmax_used_for_ka_h': s['tmax_used_for_ka_h'], 'ka_per_h': s['ka_per_h'],
                                          'checks': {c: s['checks'][c]['result'] for c in PASS_FAIL},
                                          'cmax_ng_ml': s['steady_state']['cmax_ng_ml'],
                                          'passes_c1_to_c4': s['passes_c1_to_c4']} for s in sensitivity]}
    selected = next((n for n in plan['parameter_sets']['order_of_preference'] if results[n]['primary']['passes_c1_to_c4']), None)
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'label_extract_sha256': LABEL_PATHS[drug][1],
              'label_source': {k: label['source'][k] for k in ('dailymed_set_id', 'revised', 'file_reviewed')},
              'drug': drug, 'target_population': plan['inputs']['target_population'],
              'regimen': {'dose_mg': label['regimen']['dose_mg'], 'interval_h': label['regimen']['interval_h'],
                          'evaluated_at': 'steady state'},
              'tolerance': list(TOLERANCE), 'which_checks_are_informative': plan['checks']['which_checks_are_informative'],
              'numerical_checks': numerical_checks(sets, label),
              'parameter_sets': results,
              'decision': {'selected_set': selected, 'eligible': selected is not None,
                           'selected_sensitivity_all_pass': (all(s['passes_c1_to_c4'] for s in results[selected]['sensitivity'])
                                                             if selected else None),
                           'rule': plan['decision_rule']['selection']},
              'not_this': copy.deepcopy(plan['not_this']),
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_label_exposure_commands(app):
    @app.cli.command('label-exposure-consistency')
    @click.option('--drug', default='pomalidomide', show_default=True)
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(drug, output):
        """Check a label-based exposure curve against its own label (Phase 3.1c). Not validation."""
        try:
            report = run_check(drug)
        except (ValueError, OSError, KeyError) as exc:
            raise click.ClickException(str(exc)) from exc
        payload = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
        if output:
            with output.open('x', encoding='utf-8') as handle:
                handle.write(payload)
            click.echo(f'Saved report: {output}\nReport SHA256: {report["report_sha256"]}')
        else:
            click.echo(payload, nl=False)
