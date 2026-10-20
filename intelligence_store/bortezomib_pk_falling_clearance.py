"""Simulation 3.0i: the bortezomib PK component with a clearance that falls over repeated doses.

Two outside studies (Ogawa 2008, 3.0f; CAN-1004, 3.0h) show exposure rising more from day 1 to day 11 than the
constant-clearance model (3.0b) allows. The likely reason is target-mediated disposition: bortezomib binds the
proteasome in red cells and tissues, so after the first dose much of it is taken up and apparent clearance is high;
as the binding sites fill, apparent clearance falls.

This module imitates that effect without modelling binding. The 3.0b structure and per-m2 parameters are kept, and
the elimination clearance falls from its first-dose value CL1 toward CL_low = CL1 x 6.60 / 17.9 (CAN-1004 day 11 /
day 1). Two forms are fixed in bortezomib_pk_falling_clearance_plan_v1.json (locked before computation):

  A_time        CL(t) = CL_low + (CL1 - CL_low) exp(-k t)              t: hours since the first dose
  B_prior_dose  CL(t) = CL_low + (CL1 - CL_low) exp(-k D_prior(t))     D_prior: mg/m2 given before the latest dose

Each form's single parameter k is calibrated to the CAN-1004 day 11 AUC to 72 h only, then the model is checked
against Ogawa 2008 with the same emulation and classification as 3.0f. Ogawa is never used in calibration.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

import click

from . import bortezomib_pk_can1004_check as can1004
from . import bortezomib_pk_ogawa_check as ogawa
from .bortezomib_pk import rate_constants
from .bortezomib_pk_ogawa_check import _ci, _classify, nca
from .bortezomib_platelet_evidence import EXTRACT_SHA256, load_model_extract
from .patient_state import digest

DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'bortezomib_pk_falling_clearance_plan_v1.json'
PLAN_SHA256 = 'aa07015b93c756656bb1c30b0719cb6fa84e6c4c24c95dbc030fe2d84d7e8abf'
REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'bortezomib_pk_falling_clearance_v1.json'
SCHEMA_VERSION = 'bortezomib-pk-falling-clearance-report-v1'
METHOD_VERSION = 'bortezomib-pk-falling-clearance-v1.0'
FORMS = ('A_time', 'B_prior_dose')
K_RANGE = {'A_time': (0.0, 10.0), 'B_prior_dose': (0.0, 100.0)}
K_UNITS = {'A_time': '1/h', 'B_prior_dose': 'm2/mg'}
DOSE_TIMES_H = (0.0, 72.0, 168.0, 240.0)
DAY11_H = 240.0
STEP_H = 0.001
CALIBRATION_DOSE_MG_M2 = 1.3
TOLERANCE = 1e-6
K_LIMIT = 1e6  # k large enough that clearance is CL_low (A: from the first minutes; B: from the second dose)


def load_plan(path=PLAN_PATH):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError('Falling-clearance plan is missing or changed; nothing was run.')
    return json.loads(raw)


def parameters(extract=None, observed_can1004=None):
    """Per-m2 rate constants of 3.0b plus CL1 and CL_low (from the CAN-1004 clearance ratio)."""
    k = rate_constants(extract)
    cl = (observed_can1004 or can1004.load_observed())['table7']['iv']['cl_l_h']
    ratio = cl['day11'][0] / cl['day1'][0]
    return dict(k, cl1_l_h_m2=k['cl_l_h_m2'], cl_low_l_h_m2=k['cl_l_h_m2'] * ratio, clearance_ratio=ratio)


def clearance(form, k, p, t_h, dose_mg_m2, dose_times_h=DOSE_TIMES_H):
    """Elimination clearance (L/h/m2) at time t for the given form and parameter k."""
    span = p['cl1_l_h_m2'] - p['cl_low_l_h_m2']
    if form == 'A_time':
        return p['cl_low_l_h_m2'] + span * math.exp(-k * t_h)
    if form == 'B_prior_dose':
        given = sum(1 for s in dose_times_h if s <= t_h)
        return p['cl_low_l_h_m2'] + span * math.exp(-k * max(0, given - 1) * dose_mg_m2)
    raise ValueError('Unknown form.')


def simulate(form, k, p, dose_mg_m2, read_times_h, step_h=STEP_H, dose_times_h=DOSE_TIMES_H):
    """RK4 on amounts (mg/m2). A sample at a dose time is read before that dose (pre-dose sample).

    Returns concentrations (ng/mL) at read_times_h and the relative amount balance at the end.
    """
    v1, k12, k21, k13, k31 = p['v1_l_m2'], p['k12'], p['k21'], p['k13'], p['k31']
    reads = set(read_times_h)
    doses = set(dose_times_h)
    a1 = a2 = a3 = eliminated = dosed = t = 0.0
    out = {}
    for target in sorted(reads | doses):
        span = target - t
        if span > 0:
            n = max(1, math.ceil(span / step_h - 1e-9))
            h = span / n
            # Within one integration span no dose occurs, so for form B clearance is constant over the span.
            if form == 'B_prior_dose':
                cl_fixed = clearance(form, k, p, t, dose_mg_m2, dose_times_h)
            for i in range(n):
                t0 = t + i * h
                if form == 'B_prior_dose':
                    ke0 = ke_mid = ke1 = cl_fixed / v1
                else:
                    ke0 = clearance(form, k, p, t0, dose_mg_m2) / v1
                    ke_mid = clearance(form, k, p, t0 + h / 2, dose_mg_m2) / v1
                    ke1 = clearance(form, k, p, t0 + h, dose_mg_m2) / v1

                def f(x1, x2, x3, ke):
                    return ((-(ke + k12 + k13) * x1 + k21 * x2 + k31 * x3), k12 * x1 - k21 * x2, k13 * x1 - k31 * x3,
                            ke * x1)
                d1 = f(a1, a2, a3, ke0)
                d2 = f(a1 + h / 2 * d1[0], a2 + h / 2 * d1[1], a3 + h / 2 * d1[2], ke_mid)
                d3 = f(a1 + h / 2 * d2[0], a2 + h / 2 * d2[1], a3 + h / 2 * d2[2], ke_mid)
                d4 = f(a1 + h * d3[0], a2 + h * d3[1], a3 + h * d3[2], ke1)
                a1 += h / 6 * (d1[0] + 2 * d2[0] + 2 * d3[0] + d4[0])
                a2 += h / 6 * (d1[1] + 2 * d2[1] + 2 * d3[1] + d4[1])
                a3 += h / 6 * (d1[2] + 2 * d2[2] + 2 * d3[2] + d4[2])
                eliminated += h / 6 * (d1[3] + 2 * d2[3] + 2 * d3[3] + d4[3])
            t = target
        if target in reads:
            out[target] = 1000.0 * a1 / v1
        if target in doses:
            a1 += dose_mg_m2
            dosed += dose_mg_m2
    balance = abs(a1 + a2 + a3 + eliminated - dosed) / dosed if dosed else 0.0
    return out, balance


def profiles(form, k, p, dose_mg_m2, sampling_times_h, step_h=STEP_H):
    day1 = list(sampling_times_h)
    day11 = [DAY11_H + s for s in sampling_times_h]
    conc, balance = simulate(form, k, p, dose_mg_m2, day1 + day11, step_h)
    return {'day1_ng_ml': [conc[s] for s in day1], 'day11_ng_ml': [conc[s] for s in day11], 'amount_balance': balance}


def _can1004_day11_auc_last(form, k, p, times):
    prof = profiles(form, k, p, CALIBRATION_DOSE_MG_M2, times)
    return nca(times, prof['day11_ng_ml'], 'linear', 3)['auc_to_last_ng_h_ml']


def calibrate(form, p, observed_can1004):
    """Bisection on k so that the emulated CAN-1004 day 11 AUC to 72 h equals the observed mean."""
    times = observed_can1004['design']['pk_sampling_times_after_dose_h']
    target = observed_can1004['table7']['iv']['auc_last_ng_h_ml']['day11'][0]
    lo, hi = K_RANGE[form]
    f_lo = _can1004_day11_auc_last(form, lo, p, times) - target
    f_hi = _can1004_day11_auc_last(form, hi, p, times) - target
    base = {'form': form, 'target': 'CAN-1004 day 11 AUC to 72 h, linear trapezoidal', 'target_ng_h_ml': target,
            'k_units': K_UNITS[form], 'search_range': [lo, hi],
            'reachable_ng_h_ml': {'at_k_min': f_lo + target, 'at_k_max': f_hi + target,
                                  'limit_k_to_infinity': _can1004_day11_auc_last(form, K_LIMIT, p, times)}}
    if f_lo * f_hi > 0:
        return dict(base, calibratable=False, k=None, achieved_ng_h_ml=None, iterations=0,
                    reason='The target lies outside what the form can reach in the search range.')
    iterations, k, f_mid = 0, None, None
    while True:
        iterations += 1
        k = (lo + hi) / 2
        f_mid = _can1004_day11_auc_last(form, k, p, times) - target
        if abs(f_mid) / target < TOLERANCE or iterations >= 200:
            break
        if f_lo * f_mid < 0:
            hi = k
        else:
            lo, f_lo = k, f_mid
    return dict(base, calibratable=True, k=k, achieved_ng_h_ml=target + f_mid, iterations=iterations)


def numerical_checks(p, k_by_form, can_times, ogawa_times):
    """The three checks fixed in the plan, on both forms (each at its calibrated k)."""
    reference = {'can1004': can1004.model_profiles(can_times),
                 'ogawa_1_3': ogawa.model_profiles(1.3, ogawa_times)}
    linear = []
    for form in FORMS:
        for name, times, dose in (('can1004', can_times, 1.3), ('ogawa_1_3', ogawa_times, 1.3)):
            prof = profiles(form, 0.0, p, dose, times)
            ref = reference[name]
            linear += [abs(a - b) / b for key in ('day1_ng_ml', 'day11_ng_ml') for a, b in zip(prof[key], ref[key])]
    halving, balances = [], []
    for form in FORMS:
        # A form that could not be calibrated is checked at the top of its search range, where the conclusion was drawn.
        k = k_by_form[form] if k_by_form.get(form) is not None else K_RANGE[form][1]
        full = profiles(form, k, p, 1.3, ogawa_times)
        half = profiles(form, k, p, 1.3, ogawa_times, STEP_H / 2)
        for key in ('day1_ng_ml', 'day11_ng_ml'):
            a = nca(ogawa_times, full[key], 'linear', 3)['auc_ng_h_ml']
            b = nca(ogawa_times, half[key], 'linear', 3)['auc_ng_h_ml']
            halving.append(abs(a - b) / b)
        balances += [full['amount_balance'], half['amount_balance']]
    linear_max, halving_max, balance_max = max(linear), max(halving) if halving else None, max(balances) if balances else None
    return {'k0_matches_exact_solution_max_relative_difference': linear_max, 'k0_check_passed': linear_max < 1e-6,
            'step_halving_max_relative_auc_change': halving_max,
            'step_halving_passed': halving_max is not None and halving_max < 1e-6,
            'amount_balance_relative': balance_max, 'amount_balance_passed': balance_max is not None and balance_max < 1e-9}


def _ogawa_rows(form, k, p, observed, readings):
    times = observed['design']['sampling_times_h']
    rows = []
    for dose_key in ogawa.DOSE_LEVELS:
        obs = observed['table3']['dose_levels'][dose_key]
        prof = profiles(form, k, p, float(dose_key), times)
        n1, n11 = obs['n_day1'], obs['n_day11']
        targets = {'auc_day1': (obs['AUC_ng_h_ml']['day1'], n1), 'auc_day11': (obs['AUC_ng_h_ml']['day11'], n11),
                   'auc_ratio_day11_over_day1': (obs['AUC_ratio_day11_over_day1'], n11),
                   'c0_day1': (obs['C0_ng_ml']['day1'], n1), 'c0_day11': (obs['C0_ng_ml']['day11'], n11),
                   'half_life_day1': (obs['half_life_h']['day1'], n1), 'half_life_day11': (obs['half_life_h']['day11'], n11)}
        by_reading = []
        for r in readings:
            d1 = nca(times, prof['day1_ng_ml'], r['auc_rule'], r['terminal_points'])
            d11 = nca(times, prof['day11_ng_ml'], r['auc_rule'], r['terminal_points'])
            values = {'auc_day1': d1['auc_ng_h_ml'], 'auc_day11': d11['auc_ng_h_ml'],
                      'auc_ratio_day11_over_day1': d11['auc_ng_h_ml'] / d1['auc_ng_h_ml'],
                      'c0_day1': d1['c0_ng_ml'], 'c0_day11': d11['c0_ng_ml'],
                      'half_life_day1': d1['half_life_h'], 'half_life_day11': d11['half_life_h']}
            endpoints = {}
            for name, ((mean, sd), n) in targets.items():
                interval = _ci(mean, sd, n)
                endpoints[name] = {'model_emulated': values[name], 'observed_mean': mean, 'observed_sd': sd, 'n': n,
                                   'interval_95': interval, 'ratio_model_to_observed': values[name] / mean,
                                   'classification': None if name.startswith('half_life') else _classify(values[name], interval)}
            by_reading.append({'auc_rule': r['auc_rule'], 'terminal_points': r['terminal_points'], 'role': r['role'],
                               'endpoints': endpoints})
        classified = [n for n, e in by_reading[0]['endpoints'].items() if e['classification'] is not None]
        rows.append({'dose_mg_m2': float(dose_key), 'readings': by_reading,
                     'classifications_across_readings': {n: sorted({br['endpoints'][n]['classification'] for br in by_reading})
                                                         for n in classified}})
    return rows


def _can1004_diagnostics(form, k, p, observed_can1004):
    times = observed_can1004['design']['pk_sampling_times_after_dose_h']
    prof = profiles(form, k, p, CALIBRATION_DOSE_MG_M2, times)
    d1 = nca(times, prof['day1_ng_ml'], 'linear', 3)
    d11 = nca(times, prof['day11_ng_ml'], 'linear', 3)
    iv = observed_can1004['table7']['iv']
    return {'role': 'diagnostic only; the model was calibrated on this study',
            'auc_last_day1': {'model_emulated': d1['auc_to_last_ng_h_ml'], 'observed_mean': iv['auc_last_ng_h_ml']['day1'][0]},
            'auc_last_day11': {'model_emulated': d11['auc_to_last_ng_h_ml'], 'observed_mean': iv['auc_last_ng_h_ml']['day11'][0]},
            'auc_inf_day1': {'model_emulated': d1['auc_ng_h_ml'], 'observed_mean': iv['auc_inf_ng_h_ml']['day1'][0]},
            'auc_inf_day11': {'model_emulated': d11['auc_ng_h_ml'], 'observed_mean': iv['auc_inf_ng_h_ml']['day11'][0]},
            'half_life_day1': {'model_emulated': d1['half_life_h'], 'observed_mean': iv['half_life_h']['day1'][0]},
            'half_life_day11': {'model_emulated': d11['half_life_h'], 'observed_mean': iv['half_life_h']['day11'][0]}}


def run_check():
    plan = load_plan()
    extract = load_model_extract()
    obs_can = can1004.load_observed()
    obs_ogawa = ogawa.load_observed()
    p = parameters(extract, obs_can)
    can_times = obs_can['design']['pk_sampling_times_after_dose_h']
    ogawa_times = obs_ogawa['design']['sampling_times_h']
    readings = [dict(r, role='primary') for r in [ogawa.load_plan()['nca_emulation']['readings']['primary']]] + [
        dict(r, role='sensitivity') for r in ogawa.load_plan()['nca_emulation']['readings']['sensitivity']]
    constant = ogawa.run_check()
    constant_lead = next(r for r in constant['rows'] if r['dose_mg_m2'] == 1.3)['readings'][0]['endpoints']
    forms = {}
    for form in FORMS:
        cal = calibrate(form, p, obs_can)
        entry = {'equation': plan['model']['forms'][form]['equation'], 'calibration': cal}
        if cal['calibratable']:
            rows = _ogawa_rows(form, cal['k'], p, obs_ogawa, readings)
            lead = next(r for r in rows if r['dose_mg_m2'] == 1.3)
            primary = lead['readings'][0]['endpoints']['auc_ratio_day11_over_day1']
            entry.update({
                'clearance_l_h_m2_at_dose_times': {f'day {int(s // 24) + 1}': clearance(form, cal['k'], p, s + 1e-9, 1.3)
                                                    for s in DOSE_TIMES_H},
                'can1004_diagnostics': _can1004_diagnostics(form, cal['k'], p, obs_can),
                'ogawa_rows': rows,
                'decision': {'carries_rise_over_to_ogawa': primary['classification'] == 'consistent',
                             'primary_endpoint': {k: primary[k] for k in ('model_emulated', 'observed_mean', 'interval_95',
                                                                          'classification')},
                             'primary_robust_across_readings':
                                 len(lead['classifications_across_readings']['auc_ratio_day11_over_day1']) == 1}})
        else:
            entry['decision'] = {'carries_rise_over_to_ogawa': False, 'reason': 'not calibratable; not checked'}
        forms[form] = entry
    k_by_form = {f: forms[f]['calibration']['k'] for f in FORMS}
    post_hoc = []
    for form in FORMS:
        for k in (K_RANGE[form][1], K_LIMIT):
            prof = profiles(form, k, p, CALIBRATION_DOSE_MG_M2, can_times)
            post_hoc.append({'form': form, 'k': k,
                             'can1004_auc_last_day1_ng_h_ml': nca(can_times, prof['day1_ng_ml'], 'linear', 3)['auc_to_last_ng_h_ml'],
                             'can1004_auc_last_day11_ng_h_ml': nca(can_times, prof['day11_ng_ml'], 'linear', 3)['auc_to_last_ng_h_ml']})
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'model_extract_sha256': EXTRACT_SHA256,
              'can1004_observed_sha256': can1004.OBSERVED_SHA256, 'ogawa_observed_sha256': ogawa.OBSERVED_SHA256,
              'classification': plan['classification'],
              'parameters_per_m2': {'cl1_l_h_m2': p['cl1_l_h_m2'], 'cl_low_l_h_m2': p['cl_low_l_h_m2'],
                                    'clearance_ratio_from_can1004': p['clearance_ratio']},
              'numerical_checks': numerical_checks(p, k_by_form, can_times, ogawa_times),
              'forms': forms,
              'constant_clearance_at_1_3_mg_m2_for_comparison': {
                  n: {k: constant_lead[n][k] for k in ('model_emulated', 'observed_mean', 'classification')}
                  for n in ('auc_day1', 'auc_day11', 'auc_ratio_day11_over_day1')},
              'decision': {'forms_carrying_rise_over': [f for f in FORMS if forms[f]['decision']['carries_rise_over_to_ogawa']],
                           'rule': plan['decision_rule']['summary']},
              'post_hoc_not_in_plan': {
                  'status': 'Descriptive, computed after the locked result; not part of the decision and not a test.',
                  'why': 'To show where each form ends up at the top of its range and in the limit of large k.',
                  'can1004_at_range_top_and_limit': post_hoc,
                  'observed_can1004_auc_last_ng_h_ml': {'day1': obs_can['table7']['iv']['auc_last_ng_h_ml']['day1'][0],
                                                       'day11': obs_can['table7']['iv']['auc_last_ng_h_ml']['day11'][0]}},
              'not_this': copy.deepcopy(plan['not_this']),
              'known_differences_and_weaknesses': copy.deepcopy(plan['known_differences_and_weaknesses']),
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_bortezomib_pk_falling_clearance_commands(app):
    @app.cli.command('bortezomib-pk-falling-clearance')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(output):
        """Calibrate the falling-clearance forms on CAN-1004 and check them against Ogawa 2008 (Simulation 3.0i)."""
        try:
            report = run_check()
        except (ValueError, OSError, KeyError) as exc:
            raise click.ClickException(str(exc)) from exc
        payload = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
        if output:
            with output.open('x', encoding='utf-8') as handle:
                handle.write(payload)
            click.echo(f'Saved report: {output}\nReport SHA256: {report["report_sha256"]}')
        else:
            click.echo(payload, nl=False)
