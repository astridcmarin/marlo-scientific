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
