"""Simulation 3.0g: the Kuan 2012 bortezomib PK model (saturable return from a peripheral compartment) against Ogawa 2008.

The constant-clearance PK component used by the platelet tool over-predicts day 1 exposure in Ogawa 2008 and
under-predicts the rise from day 1 to day 11 (Simulation 3.0f). Kuan et al. (PAGE 2012) explained that rise with
saturable distribution: drug moves into a deep peripheral compartment freely, but returns through a saturable step.
This module implements that model as transcribed (bortezomib_pk_kuan_2012_extract_v1.json) and runs the comparison
fixed in advance (bortezomib_pk_kuan_check_plan_v1.json), with the same NCA emulation and classification as 3.0f.
No parameter is estimated or tuned.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

import click

from .bortezomib_pk_ogawa_check import (OBSERVED_SHA256, _ci, _classify, load_observed, nca)
from .patient_state import digest

DATA = Path(__file__).parent / 'data'
EXTRACT_PATH = DATA / 'bortezomib_pk_kuan_2012_extract_v1.json'
EXTRACT_SHA256 = '9d42fd996826f4b33156834cb1c5067e0610cc878b846918ac7337a92d608c59'
PLAN_PATH = DATA / 'bortezomib_pk_kuan_check_plan_v1.json'
PLAN_SHA256 = '509ce058748422ae7195c1f1eff59c1822592ddad5142bb74b5093adaf28f9ef'
REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'bortezomib_pk_kuan_check_v1.json'
SCHEMA_VERSION = 'bortezomib-pk-kuan-check-report-v1'
METHOD_VERSION = 'bortezomib-pk-kuan-v1.0'
READINGS = ('A_rate_constant', 'B_clearance')
DOSE_TIMES_H = (0.0, 72.0, 168.0, 240.0)
DAY11_H = 240.0
STEP_H = 0.001
NCA_READINGS = (('linear', 3), ('linear', 4), ('linear_up_log_down', 3), ('linear_up_log_down', 4))


def _load(path, expected, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'{label} is missing or changed; nothing was computed.')
    return json.loads(raw)


def load_extract(path=EXTRACT_PATH):
    return _load(path, EXTRACT_SHA256, 'Kuan 2012 model extract')


def load_plan(path=PLAN_PATH):
    return _load(path, PLAN_SHA256, 'Kuan check plan')


def parameters(extract, parameter_set):
    key = {'table2_posterior_mean': 'table2_posterior_mean', 'table3_posterior_median': 'table3_posterior_median'}[parameter_set]
    p = extract['parameters'][key]
    return {'CL': p['CL_l_h'], 'V1': p['V1_l'], 'Q2': p['Q2_l_h'], 'Q3': p['Q3_l_h'], 'V2': p['V2_l'], 'V3': p['V3_l'],
            'Km': p['Km_ng_ml'], 'Vm': extract['parameters']['Vm_fixed']['value']}


def _derivatives(a, p, reading, return_override=None):
    """Amounts in mg; concentrations in ng/mL = 1000 x mg / L."""
    a1, a2, a3 = a
    c2 = 1000.0 * a2 / p['V2']
    if return_override is not None:              # linear reference: constant rate constant k21 (1/h)
        back = return_override * a2
    elif reading == 'A_rate_constant':           # Vm/(Km + C2) is a rate constant (1/h)
        back = p['Vm'] / (p['Km'] + c2) * a2
    elif reading == 'B_clearance':               # Vm/(Km + C2) is a clearance (L/h); flux = CL21 x C2 (ng/mL x L = ug)
        back = p['Vm'] / (p['Km'] + c2) * c2 / 1000.0
    else:
        raise ValueError('Unknown reading of the saturable term.')
    elim = p['CL'] / p['V1'] * a1
    to2 = p['Q2'] / p['V1'] * a1
    to3 = p['Q3'] / p['V1'] * a1
    from3 = p['Q3'] / p['V3'] * a3
    return (-elim - to2 - to3 + back + from3, to2 - back, to3 - from3), elim


def simulate(p, dose_mg, read_times_h, reading='A_rate_constant', step_h=STEP_H, return_override=None,
             dose_times_h=DOSE_TIMES_H):
    """Fourth-order Runge-Kutta from t = 0 with boluses at dose_times_h; returns central concentrations at read_times_h
    and the amount balance at the end."""
    targets = sorted(set(read_times_h) | set(dose_times_h))
    a, eliminated, t, dosed = [0.0, 0.0, 0.0], 0.0, 0.0, 0.0
    out = {}
    for target in targets:
        span = target - t
        if span > 0:
            n = max(1, math.ceil(span / step_h - 1e-9))
            h = span / n
            for _ in range(n):
                k1, e1 = _derivatives(a, p, reading, return_override)
                y = [a[i] + h / 2 * k1[i] for i in range(3)]
                k2, e2 = _derivatives(y, p, reading, return_override)
                y = [a[i] + h / 2 * k2[i] for i in range(3)]
                k3, e3 = _derivatives(y, p, reading, return_override)
                y = [a[i] + h * k3[i] for i in range(3)]
                k4, e4 = _derivatives(y, p, reading, return_override)
                a = [a[i] + h / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]) for i in range(3)]
                eliminated += h / 6 * (e1 + 2 * e2 + 2 * e3 + e4)
            t = target
        if target in dose_times_h:
            a[0] += dose_mg
            dosed += dose_mg
        if target in read_times_h:
            out[target] = 1000.0 * a[0] / p['V1']
    balance = abs(sum(a) + eliminated - dosed) / dosed if dosed else 0.0
    return out, balance


def profiles(p, dose_mg, sampling_times_h, reading, step_h=STEP_H):
    """Day 1 samples after t = 0 and day 11 samples after t = 240 h (a sample at the dose time is taken after the dose)."""
    eps = 1e-9
    day1 = [t for t in sampling_times_h]
    day11 = [DAY11_H + t for t in sampling_times_h]
    conc, balance = simulate(p, dose_mg, set(day1) | set(day11), reading, step_h)
    return {'day1_ng_ml': [conc[t] for t in day1], 'day11_ng_ml': [conc[t] for t in day11], 'amount_balance': balance}


def numerical_checks(extract):
    """The three checks fixed in the plan."""
    p = parameters(extract, 'table2_posterior_mean')
    times = [0.0833333333333, 0.25, 0.5, 1, 2, 4, 6, 8, 12, 24, 48]
    # 1. Linear reference: constant return rate constant k21 = Q2/V2 makes Peripheral 2 an ordinary linear compartment.
    k21 = p['Q2'] / p['V2']
    rk, _ = simulate(p, 2.0, times, step_h=STEP_H, return_override=k21, dose_times_h=(0.0,))
    exact = _exact_linear(p, 2.0, times, k21)
    linear_max_rel = max(abs(rk[t] - exact[t]) / exact[t] for t in times)
    # 2. Step halving on the primary condition.
    plan = load_plan()
    dose = 1.3 * plan['body_size']['primary_bsa_m2']
    full = profiles(p, dose, times, 'A_rate_constant', STEP_H)
    half = profiles(p, dose, times, 'A_rate_constant', STEP_H / 2)
    auc = lambda prof: nca(times, prof, 'linear', 3)['auc_ng_h_ml']
    step_rel = max(abs(auc(full[d]) - auc(half[d])) / auc(half[d]) for d in ('day1_ng_ml', 'day11_ng_ml'))
    return {'linear_reference_max_relative_difference': linear_max_rel, 'linear_reference_passed': linear_max_rel < 1e-3,
            'step_halving_max_relative_auc_change': step_rel, 'step_halving_passed': step_rel < 1e-3,
            'amount_balance_relative': max(full['amount_balance'], half['amount_balance']),
            'amount_balance_passed': max(full['amount_balance'], half['amount_balance']) < 1e-9}


def _exact_linear(p, dose_mg, times, k21):
    """Closed-form linear three-compartment bolus response (eigen-decomposition of the 3x3 rate matrix)."""
    k10, k12, k13 = p['CL'] / p['V1'], p['Q2'] / p['V1'], p['Q3'] / p['V1']
    k31 = p['Q3'] / p['V3']
    # Characteristic polynomial of the central-compartment response: roots by Cardano (all real, negative).
    a2 = k10 + k12 + k13 + k21 + k31
    a1 = k10 * k21 + k10 * k31 + k12 * k31 + k13 * k21 + k21 * k31
    a0 = k10 * k21 * k31
    m = (3 * a1 - a2 ** 2) / 3
    n = (2 * a2 ** 3 - 9 * a2 * a1 + 27 * a0) / 27
    q = math.sqrt(-m / 3)
    theta = math.acos(-n / (2 * q ** 3)) / 3
    roots = [2 * q * math.cos(theta + 2 * math.pi * j / 3) - a2 / 3 for j in range(3)]
    lams = [-r for r in roots]
    out = {}
    for t in times:
        total = 0.0
        for i, li in enumerate(lams):
            others = [lams[j] for j in range(3) if j != i]
            coef = (k21 - li) * (k31 - li) / ((others[0] - li) * (others[1] - li))
            total += coef * math.exp(-li * t)
        out[t] = 1000.0 * dose_mg / p['V1'] * total
    return out


def run_check():
    plan = load_plan()
    extract = load_extract()
    observed = load_observed()
    times = observed['design']['sampling_times_h']
    bsas = [plan['body_size']['primary_bsa_m2']] + list(plan['body_size']['sensitivity_bsa_m2'])
    sets = [plan['parameter_sets']['primary'], plan['parameter_sets']['sensitivity']]
    conditions = []
    for reading in READINGS:
        for pset in sets:
            p = parameters(extract, pset)
            for bsa in bsas:
                rows = []
                for dose_key, obs in observed['table3']['dose_levels'].items():
                    dose_mg_m2 = float(dose_key)
                    prof = profiles(p, dose_mg_m2 * bsa, times, reading)
                    endpoints_by_reading = []
                    for rule, points in NCA_READINGS:
                        d1 = nca(times, prof['day1_ng_ml'], rule, points)
                        d11 = nca(times, prof['day11_ng_ml'], rule, points)
                        values = {'auc_day1': d1['auc_ng_h_ml'], 'auc_day11': d11['auc_ng_h_ml'],
                                  'auc_ratio_day11_over_day1': d11['auc_ng_h_ml'] / d1['auc_ng_h_ml'],
                                  'c0_day1': d1['c0_ng_ml'], 'c0_day11': d11['c0_ng_ml'],
                                  'half_life_day1': d1['half_life_h'], 'half_life_day11': d11['half_life_h']}
                        obs_map = {'auc_day1': (obs['AUC_ng_h_ml']['day1'], obs['n_day1']),
                                   'auc_day11': (obs['AUC_ng_h_ml']['day11'], obs['n_day11']),
                                   'auc_ratio_day11_over_day1': (obs['AUC_ratio_day11_over_day1'], obs['n_day11']),
                                   'c0_day1': (obs['C0_ng_ml']['day1'], obs['n_day1']),
                                   'c0_day11': (obs['C0_ng_ml']['day11'], obs['n_day11'])}
                        endpoints = {}
                        for name, ((mean, sd), n) in obs_map.items():
                            interval = _ci(mean, sd, n)
                            endpoints[name] = {'model': values[name], 'observed_mean': mean, 'interval_95': interval,
                                               'ratio_to_observed': values[name] / mean,
                                               'classification': _classify(values[name], interval)}
                        endpoints['half_life_day1'] = {'model': values['half_life_day1'], 'observed_mean': obs['half_life_h']['day1'][0]}
                        endpoints['half_life_day11'] = {'model': values['half_life_day11'], 'observed_mean': obs['half_life_h']['day11'][0]}
                        endpoints_by_reading.append({'auc_rule': rule, 'terminal_points': points, 'endpoints': endpoints})
                    rows.append({'dose_mg_m2': dose_mg_m2, 'dose_mg': dose_mg_m2 * bsa, 'nca_readings': endpoints_by_reading,
                                 'amount_balance': prof['amount_balance']})
                conditions.append({'reading': reading, 'parameter_set': pset, 'bsa_m2': bsa, 'rows': rows})
    primary = next(c for c in conditions if c['reading'] == 'A_rate_constant' and c['parameter_set'] == sets[0]
                   and c['bsa_m2'] == bsas[0])
    lead = next(r for r in primary['rows'] if r['dose_mg_m2'] == 1.3)['nca_readings'][0]['endpoints']
    primary_names = ('auc_day1', 'auc_day11', 'auc_ratio_day11_over_day1')
    primary_result = {k: lead[k]['classification'] for k in primary_names}
    robustness = {}
    for name in primary_names:
        classes = {next(r for r in c['rows'] if r['dose_mg_m2'] == 1.3)['nca_readings'][i]['endpoints'][name]['classification']
                   for c in conditions if c['reading'] == 'A_rate_constant' for i in range(len(NCA_READINGS))}
        robustness[name] = sorted(classes)
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'extract_sha256': EXTRACT_SHA256, 'observed_sha256': OBSERVED_SHA256,
              'classification': plan['classification'], 'numerical_checks': numerical_checks(extract),
              'primary_condition': {'reading': 'A_rate_constant', 'parameter_set': sets[0], 'bsa_m2': bsas[0],
                                    'nca': {'auc_rule': 'linear', 'terminal_points': 3}},
              'result_at_1_3_mg_m2': primary_result,
              'reading_a_classifications_across_parameter_sets_bsa_and_nca': robustness,
              'decision': {'resolves_3_0f_findings_at_1_3_mg_m2': all(v == 'consistent' for v in primary_result.values()),
                           'robust_under_reading_a': all(len(v) == 1 for v in robustness.values())},
              'conditions': conditions,
              'not_this': copy.deepcopy(plan['not_this']), 'known_differences': copy.deepcopy(plan['known_differences']),
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_bortezomib_pk_kuan_commands(app):
    @app.cli.command('bortezomib-pk-kuan-check')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(output):
        """Run the locked Kuan 2012 vs Ogawa 2008 check (Simulation 3.0g). Exploratory; not validation."""
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
