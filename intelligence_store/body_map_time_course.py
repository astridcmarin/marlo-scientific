"""Digital human 1.1d: drug movement over time on the body map, and its locked consistency check.

One compartment with first-order absorption, on the body map's own clearance (the 2.0a pathway model, intact-nephron
reading) at each creatinine clearance. Volume and absorption rate are fixed from the CC-5013-PK-001 normal group, as
lenalidomide_body_map_time_course_plan_v1.json (locked before this module was written) prescribes. Renal and non-renal
elimination share the curve, so the cumulative urine amount ends at the fraction excreted unchanged that the map shows.

Every observed value used in the check was seen before the plan, so the check is a consistency check, not validation.
Typical values only; not a prediction for a patient.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

from scipy.stats import t as student_t

from .lenalidomide_bridoux_check import (DESIGN_SHA256 as BRIDOUX_DESIGN_SHA256, OBSERVED_V2_SHA256 as BRIDOUX_OBSERVED_SHA256,
                                         load_design as load_bridoux_design, load_observed_v2 as load_bridoux_observed)
from .lenalidomide_renal_pathways import calibrate, load_evidence, pathways
from .patient_renal_pathways import CALIBRATION_CRCL, FU, READING
from .patient_state import digest

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'lenalidomide_body_map_time_course_plan_v1.json'
PLAN_SHA256 = 'a92c4d1c88186cc0a6509e2ee5ab6a93efe64d81ec42cc9c07792913570751cc'
REPORT_PATH = ROOT / 'docs' / 'verification' / 'lenalidomide_body_map_time_course_check_v1.json'
SCHEMA_VERSION = 'lenalidomide-body-map-time-course-check-v1'
METHOD_VERSION = 'lenalidomide-body-map-time-course-v1.0'
GROUPS = ('normal', 'mild', 'moderate', 'severe')
CHECKED = ('mild', 'moderate', 'severe')
TMAX_TARGET_H = 1.0          # EMA 2013 Table 3, normal group median tmax (read from the extract and checked below)
RK4_STEP_H = 0.01


class TimeCourseError(ValueError):
    pass


def _pinned(path, sha256, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise TimeCourseError(f'{label} is missing or changed.')
    return json.loads(raw)


def load_plan():
    plan = _pinned(PLAN_PATH, PLAN_SHA256, 'Time-course check plan')
    if plan['status'] != 'locked_before_computation':
        raise TimeCourseError('The time-course check plan is not locked.')
    return plan


def _inputs(plan):
    ema = _pinned(ROOT / plan['pinned_inputs']['ema_2013_extract']['file'], plan['pinned_inputs']['ema_2013_extract']['sha256'], 'EMA 2013 extract')
    rec = _pinned(ROOT / plan['pinned_inputs']['chen_2007_demographics']['file'], plan['pinned_inputs']['chen_2007_demographics']['sha256'], 'Reconciliation v3')
    return ema, rec['sources']['chen_2007']['table_I_demographics']


# ---------------------------------------------------------------- the model
def clearances(crcl, cal=None):
    """Total, renal and non-renal clearance (L/h) from the pathway model, as the body map view computes them."""
    cal = cal or calibrate(load_evidence(), CALIBRATION_CRCL, FU)
    p = pathways(cal, crcl, READING)
    to_l_h = 60.0 / 1000.0
    return {'total': p['total_ml_min'] * to_l_h, 'renal': p['renal_ml_min'] * to_l_h, 'non_renal': p['non_renal_ml_min'] * to_l_h,
            'fe': p['fe']}


def tmax(ka, ke):
    return math.log(ka / ke) / (ka - ke)


def solve_ka(ke, target=TMAX_TARGET_H):
    """The absorption rate (faster than elimination) at which the curve peaks at `target` hours."""
    lo, hi = ke * 1.000001, 200.0
    if not tmax(hi, ke) < target < tmax(lo, ke):
        raise TimeCourseError('No absorption rate gives the target tmax.')
    for _ in range(200):
        mid = (lo + hi) / 2
        if tmax(mid, ke) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def parameters(volume_l, cal=None):
    """Fixed volume and absorption rate (calibrated once, at the pathway model's calibration point)."""
    ke_cal = clearances(CALIBRATION_CRCL, cal)['total'] / volume_l
    return {'volume_l': volume_l, 'ka_per_h': solve_ka(ke_cal), 'ke_at_calibration_per_h': ke_cal}


def concentration(t_h, dose_mg, ka, ke, volume_l):
    """ng/mL after one oral dose at time 0 (Bateman)."""
    if t_h <= 0:
        return 0.0
    return 1000.0 * dose_mg * ka / (volume_l * (ka - ke)) * (math.exp(-ke * t_h) - math.exp(-ka * t_h))


def amounts(t_h, dose_mg, ka, ke, cl):
    """mg in the gut, in the body (plasma compartment), out in urine and out by other routes at time t after one dose."""
    if t_h <= 0:
        return {'gut': dose_mg, 'body': 0.0, 'urine': 0.0, 'non_renal': 0.0}
    gut = dose_mg * math.exp(-ka * t_h)
    body = dose_mg * ka / (ka - ke) * (math.exp(-ke * t_h) - math.exp(-ka * t_h))
    out = dose_mg - gut - body
    return {'gut': gut, 'body': body, 'urine': out * cl['renal'] / cl['total'], 'non_renal': out * cl['non_renal'] / cl['total']}


def time_course(crcl, dose_mg=25.0, hours=48.0, step_h=0.25, volume_l=None, plan=None):
    """The curve and the running amounts the body map draws (typical values; one dose)."""
    plan = plan or load_plan()
    ema, _ = _inputs(plan)
    volume = volume_l or ema['table_3_geometric_means']['vz_f']['normal']['geometric_mean']
    cal = calibrate(load_evidence(), CALIBRATION_CRCL, FU)
    par, cl = parameters(volume, cal), clearances(crcl, cal)
    ke = cl['total'] / volume
    n = int(round(hours / step_h))
    rows = []
    for i in range(n + 1):
        t = i * step_h
        a = amounts(t, dose_mg, par['ka_per_h'], ke, cl)
        rows.append({'t_h': t, 'plasma_ng_ml': concentration(t, dose_mg, par['ka_per_h'], ke, volume),
                     'pct_dose': {k: 100.0 * v / dose_mg for k, v in a.items()},
                     'rate_mg_h': {'renal': cl['renal'] * concentration(t, dose_mg, par['ka_per_h'], ke, volume) / 1000.0,
                                   'non_renal': cl['non_renal'] * concentration(t, dose_mg, par['ka_per_h'], ke, volume) / 1000.0}})
    return {'crcl_ml_min': crcl, 'dose_mg': dose_mg, 'volume_l': volume, 'ka_per_h': par['ka_per_h'], 'ke_per_h': ke,
            'half_life_h': math.log(2) / ke, 'tmax_h': tmax(par['ka_per_h'], ke),
            'cmax_ng_ml': concentration(tmax(par['ka_per_h'], ke), dose_mg, par['ka_per_h'], ke, volume),
            'fraction_excreted_unchanged': cl['fe'], 'rows': rows}


# ---------------------------------------------------------------- checks
def _ci90(gm, cv_pct, n):
    s = math.sqrt(math.log(1 + (cv_pct / 100.0) ** 2))
    half = student_t.ppf(0.95, n - 1) * s / math.sqrt(n)
    return [gm * math.exp(-half), gm * math.exp(half)]


def _classify(value, ci):
    if value < ci[0]:
        return 'model_under_predicts'
    if value > ci[1]:
        return 'model_over_predicts'
    return 'consistent'


def _row(endpoint, model, gm, cv, n):
    ci = _ci90(gm, cv, n)
    return {'endpoint': endpoint, 'model': model, 'observed_gm': gm, 'observed_gcv_pct': cv, 'n': n, 'observed_ci90': ci,
            'classification': _classify(model, ci), 'model_over_observed': model / gm}


def _rk4_check(dose, ka, ke, volume):
    """Largest relative difference between the closed form and RK4 from 0.25 to 48 h."""
    gut, body, t, worst = dose, 0.0, 0.0, 0.0
    f = lambda g, b: (-ka * g, ka * g - ke * b)
    steps = int(round(48.0 / RK4_STEP_H))
    for i in range(1, steps + 1):
        k1 = f(gut, body); k2 = f(gut + RK4_STEP_H / 2 * k1[0], body + RK4_STEP_H / 2 * k1[1])
        k3 = f(gut + RK4_STEP_H / 2 * k2[0], body + RK4_STEP_H / 2 * k2[1]); k4 = f(gut + RK4_STEP_H * k3[0], body + RK4_STEP_H * k3[1])
        gut += RK4_STEP_H / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]); body += RK4_STEP_H / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
        t = i * RK4_STEP_H
        if t >= 0.25 and i % 25 == 0:
            exact = concentration(t, dose, ka, ke, volume)
            worst = max(worst, abs(1000.0 * body / volume - exact) / exact)
    return worst


def _day5_cmax(regimen_times_h, dose_mg, ka, ke, volume, window_h):
    """Peak after the dose given on day 5 (t = 96 h), by superposition of the doses actually given."""
    start, best = 96.0, 0.0
    steps = int(round(window_h / 0.01))
    for i in range(steps + 1):
        t = start + i * 0.01
        best = max(best, math.fsum(concentration(t - d, dose_mg, ka, ke, volume) for d in regimen_times_h if d <= t))
    return best


def run_check():
    plan = load_plan()
    ema, chen = _inputs(plan)
    t3 = ema['table_3_geometric_means']
    if t3['tmax_median_range_h']['normal'][0] != TMAX_TARGET_H:
        raise TimeCourseError('The normal group median tmax differs from the value the plan names.')
    volume = t3['vz_f']['normal']['geometric_mean']
    cal = calibrate(load_evidence(), CALIBRATION_CRCL, FU)
    par = parameters(volume, cal)
    ka = par['ka_per_h']
    dose = ema['design']['dose_mg']
    n = {g: ema['groups'][g]['n'] for g in GROUPS}

    primary, numerics = {}, {}
    for g in GROUPS:
        crcl = chen[g]['crcl_ml_min_mean']
        cl = clearances(crcl, cal)
        ke = cl['total'] / volume
        cmax = concentration(tmax(ka, ke), dose, ka, ke, volume)
        rows = [_row('cmax_ng_ml', cmax, t3['cmax'][g]['geometric_mean'], t3['cmax'][g]['cv_pct'], n[g]),
                _row('terminal_half_life_h', math.log(2) / ke, t3['terminal_half_life'][g]['geometric_mean'],
                     t3['terminal_half_life'][g]['cv_pct'], n[g]),
                _row('auc_infinity_ng_h_ml', 1000.0 * dose / cl['total'], t3['auc_infinity'][g]['geometric_mean'],
                     t3['auc_infinity'][g]['cv_pct'], n[g])]
        for r in rows:
            r['role'] = ('classified' if g in CHECKED and r['endpoint'] != 'auc_infinity_ng_h_ml'
                         else 'reported_calibration_group' if g == 'normal' else 'reported_follows_from_clearance')
        primary[g] = {'crcl_ml_min': crcl, 'model_tmax_h': tmax(ka, ke), 'rows': rows}
        a_end = amounts(120.0, dose, ka, ke, cl)
        numerics[g] = {'rk4_max_relative_difference': _rk4_check(dose, ka, ke, volume),
                       'mass_balance_max_relative_error': max(abs(math.fsum(amounts(t, dose, ka, ke, cl).values()) - dose) / dose
                                                              for t in [0.25 * i for i in range(1, 193)]),
                       'urine_at_120h_over_fe': a_end['urine'] / dose / cl['fe']}
    calib_tmax = tmax(ka, par['ke_at_calibration_per_h'])

    bd, bo = load_bridoux_design(), load_bridoux_observed()
    regimens = {'normal': ([24.0 * i for i in range(5)], 24.0), 'mild': ([24.0 * i for i in range(5)], 24.0),
                'moderate': ([24.0 * i for i in range(5)], 24.0), 'severe': ([0.0, 48.0, 96.0], 48.0)}
    secondary = {}
    for g in GROUPS:
        crcl = bd['design']['per_group']['crcl_mean_sd_ml_min'][g][0]
        cl = clearances(crcl, cal)
        ke = cl['total'] / volume
        o = bo['groups'][g]
        times, window = regimens[g]
        dose_g = {'normal': 25.0, 'mild': 25.0, 'moderate': 10.0, 'severe': 15.0}[g]
        rows = [_row('day5_cmax_ng_ml', _day5_cmax(times, dose_g, ka, ke, volume, window), o['cmax_gm_ng_ml'], o['cmax_gcv_pct'], o['n']),
                _row('terminal_half_life_h', math.log(2) / ke, o['t_half_gm_h'], o['t_half_gcv_pct'], o['n'])]
        for r in rows:
            r['role'] = 'classified_secondary_not_blind' if g in CHECKED else 'reported_reference_group'
        secondary[g] = {'crcl_ml_min_cockcroft_gault': crcl, 'dose_mg': dose_g, 'rows': rows}

    checks = {'closed_form_vs_rk4_pass': all(v['rk4_max_relative_difference'] < 1e-3 for v in numerics.values()),
              'mass_balance_pass': all(v['mass_balance_max_relative_error'] < 1e-9 for v in numerics.values()),
              'urine_total_equals_fe_pass': all(abs(v['urine_at_120h_over_fe'] - 1) < 5e-3 for v in numerics.values()),
              'calibration_tmax_pass': abs(calib_tmax - TMAX_TARGET_H) < 0.01}
    if not all(checks.values()):
        raise TimeCourseError(f'Numerical checks failed: {checks}')

    def summary(block):
        return {g: {r['endpoint']: r['classification'] for r in block[g]['rows'] if r['role'].startswith('classified')}
                for g in CHECKED}

    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'bridoux_design_sha256': BRIDOUX_DESIGN_SHA256, 'bridoux_observed_sha256': BRIDOUX_OBSERVED_SHA256,
              'classification': plan['classification'], 'classification_rule': plan['classification_rule'],
              'parameters': {'volume_l': volume, 'ka_per_h': ka, 'ke_at_calibration_per_h': par['ke_at_calibration_per_h'],
                             'tmax_at_calibration_h': calib_tmax, 'calibration_crcl_ml_min': CALIBRATION_CRCL, 'dose_mg': dose},
              'primary': primary, 'secondary': secondary,
              'result': {'primary': summary(primary), 'secondary_not_blind': summary(secondary)},
              'numerical_checks': dict(checks, per_group=numerics),
              'decision_rule': plan['decision_rule']['summary'], 'known_limitations': copy.deepcopy(plan['known_limitations']),
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


# ================================================================ version 2: two compartments (plan v2, locked 4 November)
PLAN_V2_PATH = DATA / 'lenalidomide_body_map_time_course_plan_v2.json'
PLAN_V2_SHA256 = '4c7b429e5d01da3eb31e0f86f2647af5d6adea116f6b7cd7fb78181b93ad6a1e'
REPORT_V2_PATH = ROOT / 'docs' / 'verification' / 'lenalidomide_body_map_time_course_check_v2.json'
SCHEMA_V2_VERSION = 'lenalidomide-body-map-time-course-check-v2'
METHOD_V2_VERSION = 'lenalidomide-body-map-time-course-v2.0'
BSA_SENSITIVITY_M2 = 1.9


def load_plan_v2():
    plan = _pinned(PLAN_V2_PATH, PLAN_V2_SHA256, 'Time-course check plan v2')
    if plan['status'] != 'locked_before_computation':
        raise TimeCourseError('The time-course check plan v2 is not locked.')
    return plan


def distribution_v2(scenario='primary'):
    """Kim 2026 central and peripheral volumes, intercompartmental clearance and absorption, on the total scale."""
    from .kim_model import load_extract
    k = {n: v['value'] for n, v in load_extract()['parameters'].items()}
    fu = k['fraction_unbound']
    v1 = k['unbound_central_volume_l']
    if scenario == 'sensitivity_bsa_1_9':
        v1 = v1 * math.exp(k['v1_bsa_coefficient'] * (BSA_SENSITIVITY_M2 - k['reference_bsa']))
    return {'vc_l': v1 * fu, 'vp_l': k['unbound_peripheral_volume_l'] * fu,
            'q_l_h': k['unbound_intercompartmental_clearance_l_h'] * fu, 'ka_per_h': k['absorption_rate_h'], 'fu': fu}


def concentration_v2(t_h, dose_mg, d, cl_l_h):
    from .kim_model import central_amount_unit_dose
    return 1000.0 * dose_mg * central_amount_unit_dose(t_h, d['ka_per_h'], cl_l_h, d['vc_l'], d['q_l_h'], d['vp_l']) / d['vc_l']


def beta_v2(d, cl_l_h):
    k10, k12, k21 = cl_l_h / d['vc_l'], d['q_l_h'] / d['vc_l'], d['q_l_h'] / d['vp_l']
    s = k10 + k12 + k21
    return (s - math.sqrt(s * s - 4 * k10 * k21)) / 2


def peak_v2(dose_mg, d, cl_l_h, start=0.0, window=12.0, events=None):
    """Cmax and tmax: a 0.01 h grid, then a golden-section refinement around the best point."""
    events = events or [(0.0, dose_mg)]
    f = lambda t: math.fsum(dd * concentration_v2(t - s, 1.0, d, cl_l_h) for s, dd in events if s <= t)
    grid = [start + 0.01 * i for i in range(1, int(window / 0.01) + 1)]
    t0 = max(grid, key=f)
    lo, hi = max(start, t0 - 0.01), t0 + 0.01
    g = (math.sqrt(5) - 1) / 2
    for _ in range(60):
        a, b = hi - g * (hi - lo), lo + g * (hi - lo)
        if f(a) > f(b):
            hi = b
        else:
            lo = a
    t = (lo + hi) / 2
    return f(t), t - start


def _rk4_v2(dose, d, cl):
    """RK4 of gut, central, peripheral and eliminated amounts; returns the worst concentration difference against the
    closed form (0.25-48 h), the worst mass-balance error and the eliminated fraction at 120 h."""
    ka, vc, vp, q = d['ka_per_h'], d['vc_l'], d['vp_l'], d['q_l_h']
    def f(x):
        g, c, p, e = x
        return (-ka * g, ka * g - (cl + q) * c / vc + q * p / vp, q * c / vc - q * p / vp, cl * c / vc)
    x, h, worst, mass = (dose, 0.0, 0.0, 0.0), RK4_STEP_H, 0.0, 0.0
    for i in range(1, int(round(120.0 / h)) + 1):
        k1 = f(x); k2 = f(tuple(a + h / 2 * b for a, b in zip(x, k1)))
        k3 = f(tuple(a + h / 2 * b for a, b in zip(x, k2))); k4 = f(tuple(a + h * b for a, b in zip(x, k3)))
        x = tuple(a + h / 6 * (b1 + 2 * b2 + 2 * b3 + b4) for a, b1, b2, b3, b4 in zip(x, k1, k2, k3, k4))
        t = i * h
        mass = max(mass, abs(math.fsum(x) - dose) / dose)
        if 0.25 <= t <= 48.0 and i % 25 == 0:
            exact = concentration_v2(t, dose, d, cl)
            worst = max(worst, abs(1000.0 * x[1] / vc - exact) / exact)
    return worst, mass, x[3] / dose


def _solve_ka_v2(d, cl, target=TMAX_TARGET_H):
    lo, hi = 0.05, 50.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if peak_v2(1.0, dict(d, ka_per_h=mid), cl)[1] > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _scenario_v2(name, ema, chen, bd, bo, cal):
    t3 = ema['table_3_geometric_means']
    dose = ema['design']['dose_mg']
    d = distribution_v2(name)
    if name == 'sensitivity_tmax_absorption':
        d['ka_per_h'] = _solve_ka_v2(d, clearances(CALIBRATION_CRCL, cal)['total'])
    primary, numerics = {}, {}
    for g in GROUPS:
        crcl = chen[g]['crcl_ml_min_mean']
        cl = clearances(crcl, cal)
        cmax, tm = peak_v2(dose, d, cl['total'])
        n = ema['groups'][g]['n']
        rows = [_row('cmax_ng_ml', cmax, t3['cmax'][g]['geometric_mean'], t3['cmax'][g]['cv_pct'], n),
                _row('terminal_half_life_h', math.log(2) / beta_v2(d, cl['total']), t3['terminal_half_life'][g]['geometric_mean'],
                     t3['terminal_half_life'][g]['cv_pct'], n),
                _row('auc_infinity_ng_h_ml', 1000.0 * dose / cl['total'], t3['auc_infinity'][g]['geometric_mean'],
                     t3['auc_infinity'][g]['cv_pct'], n)]
        for r in rows:
            r['role'] = 'reported_follows_from_clearance' if r['endpoint'] == 'auc_infinity_ng_h_ml' else 'classified'
        primary[g] = {'crcl_ml_min': crcl, 'model_tmax_h': tm, 'rows': rows}
        rk, mass, elim = _rk4_v2(dose, d, cl['total'])
        numerics[g] = {'rk4_max_relative_difference': rk, 'mass_balance_max_relative_error': mass,
                       'urine_at_120h_over_fe': elim * cl['renal'] / cl['total'] / cl['fe']}
    regimens = {'normal': ([24.0 * i for i in range(5)], 25.0, 24.0), 'mild': ([24.0 * i for i in range(5)], 25.0, 24.0),
                'moderate': ([24.0 * i for i in range(5)], 10.0, 24.0), 'severe': ([0.0, 48.0, 96.0], 15.0, 48.0)}
    secondary = {}
    for g in GROUPS:
        crcl = bd['design']['per_group']['crcl_mean_sd_ml_min'][g][0]
        cl = clearances(crcl, cal)
        times, dose_g, window = regimens[g]
        cmax, _ = peak_v2(dose_g, d, cl['total'], start=96.0, window=window, events=[(s, dose_g) for s in times])
        o = bo['groups'][g]
        rows = [_row('day5_cmax_ng_ml', cmax, o['cmax_gm_ng_ml'], o['cmax_gcv_pct'], o['n']),
                _row('terminal_half_life_h', math.log(2) / beta_v2(d, cl['total']), o['t_half_gm_h'], o['t_half_gcv_pct'], o['n'])]
        for r in rows:
            r['role'] = 'classified_secondary_not_blind' if g in CHECKED else 'reported_reference_group'
        secondary[g] = {'crcl_ml_min_cockcroft_gault': crcl, 'dose_mg': dose_g, 'rows': rows}
    checks = {'closed_form_vs_rk4_pass': all(v['rk4_max_relative_difference'] < 1e-3 for v in numerics.values()),
              'mass_balance_pass': all(v['mass_balance_max_relative_error'] < 1e-9 for v in numerics.values()),
              'urine_total_equals_fe_pass': all(abs(v['urine_at_120h_over_fe'] - 1) < 5e-3 for v in numerics.values())}
    return {'parameters': d, 'primary': primary, 'secondary': secondary, 'numerical_checks': dict(checks, per_group=numerics)}


def run_check_v2():
    plan = load_plan_v2()
    ema, chen = _inputs(plan)
    if plan['model']['distribution_and_absorption']['central_volume_l']['total'] != round(distribution_v2()['vc_l'], 4):
        raise TimeCourseError('Kim central volume on the total scale differs from the value the plan names.')
    v1_ref = plan['pinned_inputs']['v1_report']
    v1 = _pinned(ROOT / v1_ref['file'], v1_ref['sha256'], 'Time-course check report v1')
    cal = calibrate(load_evidence(), CALIBRATION_CRCL, FU)
    bd, bo = load_bridoux_design(), load_bridoux_observed()
    scenarios = {name: _scenario_v2(name, ema, chen, bd, bo, cal) for name in plan['scenarios']}
    prim = scenarios['primary']
    if not all(v for k, v in prim['numerical_checks'].items() if k.endswith('_pass')):
        raise TimeCourseError(f"Numerical checks failed: {prim['numerical_checks']}")

    def cls(block, groups, endpoint):
        return {g: next(r['classification'] for r in block[g]['rows'] if r['endpoint'] == endpoint) for g in groups}

    side_by_side = {g: {ep: {'v1': next(r for r in v1['primary'][g]['rows'] if r['endpoint'] == ep)['classification'],
                             'v2': next(r for r in prim['primary'][g]['rows'] if r['endpoint'] == ep)['classification'],
                             'v1_model': next(r for r in v1['primary'][g]['rows'] if r['endpoint'] == ep)['model'],
                             'v2_model': next(r for r in prim['primary'][g]['rows'] if r['endpoint'] == ep)['model'],
                             'observed_gm': next(r for r in prim['primary'][g]['rows'] if r['endpoint'] == ep)['observed_gm']}
                        for ep in ('cmax_ng_ml', 'terminal_half_life_h')} for g in GROUPS}
    cmax_ok = sum(c == 'consistent' for c in cls(prim['primary'], GROUPS, 'cmax_ng_ml').values())
    half_v2 = sum(c == 'consistent' for c in cls(prim['primary'], CHECKED, 'terminal_half_life_h').values())
    half_v1 = sum(c == 'consistent' for c in cls(v1['primary'], CHECKED, 'terminal_half_life_h').values())
    shows = 'v2' if cmax_ok >= 3 and half_v2 >= half_v1 else 'v1'
    result = {name: {'primary_cmax': cls(s['primary'], GROUPS, 'cmax_ng_ml'),
                     'primary_half_life': cls(s['primary'], GROUPS, 'terminal_half_life_h'),
                     'secondary_cmax': cls(s['secondary'], CHECKED, 'day5_cmax_ng_ml'),
                     'secondary_half_life': cls(s['secondary'], CHECKED, 'terminal_half_life_h')} for name, s in scenarios.items()}
    report = {'schema_version': SCHEMA_V2_VERSION, 'method_version': METHOD_V2_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_V2_SHA256, 'v1_report_sha256': v1_ref['sha256'], 'classification': plan['classification'],
              'classification_rule': plan['classification_rule'], 'scenarios': scenarios, 'result': result,
              'side_by_side_primary': side_by_side,
              'display_decision': {'rule': plan['decision_rule']['which_version_the_body_map_shows'],
                                   'v2_cmax_consistent_groups': cmax_ok, 'v2_half_life_consistent_impaired': half_v2,
                                   'v1_half_life_consistent_impaired': half_v1, 'body_map_shows': shows},
              'decision_rule': plan['decision_rule']['scope'], 'known_limitations': copy.deepcopy(plan['known_limitations']),
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


# ---------------------------------------------------------------- Digital human 1.1e: the timeline the body map draws
REPORT_V1_SHA256 = 'c5b98b878bdb206e2ed46d8ea203a8950f3a8ac06e3a87372dd5c92d6cb4aaf7'
TIMELINE_VERSION = 'body-map-timeline-v1.1'
# v1.1 (10 November 2026, AI review F05): the observed share of the dose in urine is shown beside the model's, because it
# was not a check endpoint, and the gut share is labelled as a model construct.
EMA_2013_PATH = ROOT / 'intelligence_store' / 'data' / 'lenalidomide_renal_pk_ema_2013_v1.json'
EMA_2013_SHA256 = '04f2e629ded43713062e0d68d668939a4a2cecd5a9db7ce349874e81529f6501'
ENDPOINT_LABELS = {'cmax_ng_ml': 'Peak concentration', 'terminal_half_life_h': 'Half-life', 'auc_infinity_ng_h_ml': 'Exposure (AUC)'}
CLASS_TEXT = {'consistent': 'consistent with the study', 'model_under_predicts': 'too low', 'model_over_predicts': 'too high'}
GROUP_FOR_BAND = {'normal': 'normal', 'mild': 'mild', 'moderate': 'moderate', 'severe': 'severe'}


def timeline(crcl, band_id, dose_mg=25.0, hours=48.0, step_h=0.25):
    """The v1 time course for the body map's timeline (shown version, decided by the v2 rule on 4 November 2026), with
    the locked v1 check's classification for the band's study group beside it. One dose, typical values."""
    report = _pinned(REPORT_PATH, REPORT_V1_SHA256, 'Time-course check report v1')
    tc = time_course(crcl, dose_mg=dose_mg, hours=hours, step_h=step_h)
    group = GROUP_FOR_BAND[band_id]
    rows = report['primary'][group]['rows']
    check = [{'endpoint': ENDPOINT_LABELS[r['endpoint']], 'model': r['model'], 'observed_gm': r['observed_gm'],
              'observed_ci90': r['observed_ci90'], 'classification': r['classification'],
              'text': CLASS_TEXT[r['classification']], 'ratio': r['model_over_observed'],
              'role': 'calibration group (reported, not classified by the plan)' if r['role'] == 'reported_calibration_group' else 'classified'}
             for r in rows]
    peak_low = any(c['endpoint'] == 'Peak concentration' and c['classification'] == 'model_under_predicts' for c in check)
    ema = _pinned(EMA_2013_PATH, EMA_2013_SHA256, 'EMA 2013 extract')
    urine = ema['table_3_geometric_means']['urine_excretion_pct_dose'][group]
    observed_urine = {'group': group, 'model_pct': 100.0 * tc['fraction_excreted_unchanged'],
                      'observed_gm_pct': urine['geometric_mean'], 'observed_cv_pct': urine['cv_pct'],
                      'source': f"EMA 2013 (EMA/297642/2013), {ema['table_3_geometric_means']['location']}, CC-5013-PK-001, "
                                'geometric mean (CV%)',
                      'file': str(EMA_2013_PATH.relative_to(ROOT)), 'sha256': EMA_2013_SHA256, 'checked': False}
    urine_note = (f"The share ending in urine was not a check endpoint: the model gives {observed_urine['model_pct']:.0f}% of the dose, "
                  f"the study observed {urine['geometric_mean']}% (geometric mean, CV {urine['cv_pct']}%) in its {group} group.")
    view = {
        'timeline_version': TIMELINE_VERSION, 'method_version': METHOD_VERSION, 'crcl_ml_min': crcl, 'band': band_id,
        'study_group_checked': group, 'dose_mg': dose_mg, 'hours': hours, 'step_h': step_h,
        'summary': {k: tc[k] for k in ('volume_l', 'ka_per_h', 'ke_per_h', 'half_life_h', 'tmax_h', 'cmax_ng_ml',
                                         'fraction_excreted_unchanged')},
        'rows': [{'t_h': r['t_h'], 'plasma_ng_ml': r['plasma_ng_ml'], 'pct_dose': r['pct_dose']} for r in tc['rows']],
        'check': check, 'check_report': {'file': str(REPORT_PATH.relative_to(ROOT)), 'sha256': REPORT_V1_SHA256},
        'warning': (('Peak too low. The locked check found the model\'s peak below the study\'s in every group, '
                     'because one volume spreads the dose too widely just after absorption (v2, two compartments, was '
                     'tested and not adopted). Read the shape and the timing of elimination, not the height of the peak. '
                     if peak_low else '') + urine_note),
        'observed_urine': observed_urine,
        'limits': ['One 25 mg dose, typical values; no between-patient spread.',
                   'All of the dose is taken as absorbed (F = 1). In the moderate and severe bands the split between urine and '
                   'other routes depends on that (Simulation 2.0e).',
                   'Amounts in the body are one well-mixed space, not organ by organ.',
                   'The gut share is a model construct: it comes from an absorption rate chosen to reproduce the time of peak with '
                   'all of the dose absorbed, not from an observed amount.'] + report['known_limitations'][:1],
        'clinical_prediction_validated': False,
    }
    view['timeline_sha256'] = digest(view)
    return view
