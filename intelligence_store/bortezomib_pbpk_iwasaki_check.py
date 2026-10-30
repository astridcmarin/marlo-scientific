"""Simulation 3.0k: the Iwasaki 2020 PBPK model against Ogawa 2008 and CAN-1004 (plan locked in commit 2b39d8f).

Runs the transcribed model (bortezomib_pbpk_iwasaki.derivatives, Table 2 parameters) with the dosing, body sizes,
NCA emulation, numerical checks and classification fixed in bortezomib_pbpk_iwasaki_check_plan_v1.json. No parameter
is estimated or tuned. The dose input (IV bolus into systemic plasma) is an assumption recorded in the plan.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

import click

from . import bortezomib_pbpk_iwasaki as model
from .bortezomib_pk_can1004_check import OBSERVED_SHA256 as CAN1004_SHA256, load_observed as load_can1004
from .bortezomib_pk_ogawa_check import OBSERVED_SHA256 as OGAWA_SHA256, _ci, _classify, load_observed as load_ogawa, nca
from .patient_state import digest

DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'bortezomib_pbpk_iwasaki_check_plan_v1.json'
PLAN_SHA256 = '185b1417b40eee9499338c9d20f85279dde0a9121c30b7853cfe88c0c4b60b73'
REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'bortezomib_pbpk_iwasaki_check_v1.json'
SCHEMA_VERSION = 'bortezomib-pbpk-iwasaki-check-report-v1'
METHOD_VERSION = 'bortezomib-pbpk-iwasaki-check-v1.0'
DOSE_TIMES_H = (0.0, 72.0, 168.0, 240.0)
DAY11_H = 240.0
STEP_H = 0.00025
NCA_READINGS = (('linear', 3), ('linear', 4), ('linear_up_log_down', 3), ('linear_up_log_down', 4))
BMAX_SENSITIVITY_FACTOR = 1.4
BODY = {'ogawa': {'weight_kg': 58.0, 'height_cm': 160.0}, 'can1004': {'weight_kg': 75.0, 'height_cm': 170.0}}
BODY_FACTORS = (0.9, 1.1)


def load_plan(path=PLAN_PATH):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError('Iwasaki check plan is missing or changed; nothing was computed.')
    return json.loads(raw)


def bsa_du_bois(weight_kg, height_cm):
    return 0.007184 * weight_kg ** 0.425 * height_cm ** 0.725


def dose_ug_per_kg(dose_mg_m2, study, factor=1.0):
    b = BODY[study]
    return dose_mg_m2 * 1000.0 * bsa_du_bois(b['weight_kg'], b['height_cm']) / b['weight_kg'] * factor


def _rhs_factory(p):
    """Equations (1)-(6) with constants folded in (same algebra as bortezomib_pbpk_iwasaki.derivatives, which the
    tests compare against). State order: Cp, Crbc, Cperi, Chp, Chrbc, Ch."""
    qp, qr = p['Qh'] * (1.0 - p['Hct']), p['Qh'] * p['Hct']
    vs, vr, vpe, vhp, vhr, vh = p['Vsys'], p['Vrbc'], p['Vperi'], p['Vhp'], p['Vhrbc'], p['Vh']
    clp, ps, fup, ful = p['CLperi'], p['PSliv'], p['fu_p'], p['fu_liver']
    kon, koff, bmax, conv = p['Kon'], p['Koff'], p['Bmax'], 1000.0 / p['MW']
    met = ful * sum(p[f] for f in model.FM) * p['CLint']

    def rhs(cp, crbc, cperi, chp, chrbc, ch):
        bs = kon * (bmax * vr - vr * crbc * conv) * fup * cp - koff * vr * crbc
        bh = kon * (bmax * vhr - vhr * chrbc * conv) * fup * chp - koff * vhr * chrbc
        m = met * ch
        return ((-qp * cp + qp * chp - clp * cp + clp * cperi - bs) / vs,
                (-qr * crbc + qr * chrbc + bs) / vr,
                (clp * cp - clp * cperi) / vpe,
                (qp * cp - qp * chp - ps * fup * chp + ps * ful * ch - bh) / vhp,
                (qr * crbc - qr * chrbc + bh) / vhr,
                (ps * fup * chp - ps * ful * ch - m) / vh,
                m)
    return rhs


def simulate(p, dose_ug_kg, read_times_h, dose_times_h=DOSE_TIMES_H, step_h=STEP_H):
    """RK4 from t = 0, boluses into systemic plasma at dose_times_h. A sample at a dose time is taken before the dose.
    Returns plasma concentrations (ng/mL) at read_times_h, red-cell site occupancy at each dose time and at the end,
    and the relative mass-balance error."""
    rhs = _rhs_factory(p)
    vol = [p['Vsys'], p['Vrbc'], p['Vperi'], p['Vhp'], p['Vhrbc'], p['Vh']]
    y = [0.0] * 6
    t, metabolised, dosed = 0.0, 0.0, 0.0
    out, occupancy, auc_since_dose, auc_by_interval = {}, {}, 0.0, {}
    capacity_ng_ml = p['Bmax'] * p['MW'] / 1000.0
    events = sorted(set(read_times_h) | set(dose_times_h))
    for target in events:
        span = target - t
        if span > 0:
            n = max(1, math.ceil(span / step_h - 1e-9))
            h = span / n
            for _ in range(n):
                k1 = rhs(*y)
                y2 = [y[i] + 0.5 * h * k1[i] for i in range(6)]
                k2 = rhs(*y2)
                y3 = [y[i] + 0.5 * h * k2[i] for i in range(6)]
                k3 = rhs(*y3)
                y4 = [y[i] + h * k3[i] for i in range(6)]
                k4 = rhs(*y4)
                before = y[0]
                y = [y[i] + h / 6.0 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]) for i in range(6)]
                auc_since_dose += h * (before + y[0]) / 2.0
                metabolised += h / 6.0 * (k1[6] + 2 * k2[6] + 2 * k3[6] + k4[6])
            t = target
        if target in read_times_h:
            out[target] = y[0]
        if target in dose_times_h:
            if dosed:
                auc_by_interval[f'to_{target:g}h'] = auc_since_dose
            auc_since_dose = 0.0
            occupancy[target] = y[1] / capacity_ng_ml
            y[0] += dose_ug_kg / p['Vsys']
            dosed += dose_ug_kg
    amount = sum(y[i] * vol[i] for i in range(6))
    occupancy['end'] = y[1] / capacity_ng_ml
    auc_by_interval[f'last_dose_to_{t:g}h'] = auc_since_dose
    return {'conc': out, 'occupancy_before_dose': occupancy, 'plasma_auc_by_interval_ng_h_ml': auc_by_interval, 'amount_in_body': amount, 'metabolised': metabolised,
            'mass_balance_error': abs(amount + metabolised - dosed) / dosed if dosed else 0.0}


def closed_form_auc_without_binding(p, dose_ug_kg):
    """Plasma AUC to infinity of the linear system with Kon = 0 (red-cell compartments stay empty)."""
    qp = p['Qh'] * (1.0 - p['Hct'])
    k = p['fu_liver'] * sum(p[f] for f in model.FM) * p['CLint']
    ps, fup, ful = p['PSliv'], p['fu_p'], p['fu_liver']
    # Integrals of equations 4 and 6 over all time: AUC_h = ps fup AUC_hp / (ps ful + k);
    # qp AUC_p = AUC_hp (qp + ps fup - ps ful ps fup / (ps ful + k)); equation 1: dose = qp AUC_p - qp AUC_hp.
    g = qp + ps * fup - ps * ful * ps * fup / (ps * ful + k)
    return dose_ug_kg / (qp - qp * qp / g)


def _profiles(p, dose_ug_kg, times, last_dose_h=DAY11_H, step_h=STEP_H):
    day1 = list(times)
    day11 = [last_dose_h + s for s in times]
    sim = simulate(p, dose_ug_kg, set(day1) | set(day11), step_h=step_h)
    return {'day1_ng_ml': [sim['conc'][s] for s in day1], 'day11_ng_ml': [sim['conc'][s] for s in day11],
            'red_cell_occupancy_before_dose': {str(k): v for k, v in sim['occupancy_before_dose'].items()},
            'plasma_auc_by_interval_ng_h_ml': sim['plasma_auc_by_interval_ng_h_ml'],
            'mass_balance_error': sim['mass_balance_error']}


def _endpoint(value, mean, sd, n):
    interval = _ci(mean, sd, n)
    return {'model_emulated': value, 'observed_mean': mean, 'observed_sd': sd, 'n': n, 'interval_95': interval,
            'ratio_model_to_observed': value / mean, 'classification': _classify(value, interval)}


def ogawa_endpoints(prof, obs, times, reading):
    d1 = nca(times, prof['day1_ng_ml'], *reading)
    d11 = nca(times, prof['day11_ng_ml'], *reading)
    n1, n11 = obs['n_day1'], obs['n_day11']
    e = {'auc_day1': _endpoint(d1['auc_ng_h_ml'], *obs['AUC_ng_h_ml']['day1'], n1),
         'auc_day11': _endpoint(d11['auc_ng_h_ml'], *obs['AUC_ng_h_ml']['day11'], n11),
         'auc_ratio_day11_over_day1': _endpoint(d11['auc_ng_h_ml'] / d1['auc_ng_h_ml'], *obs['AUC_ratio_day11_over_day1'], n11),
         'c0_day1': _endpoint(d1['c0_ng_ml'], *obs['C0_ng_ml']['day1'], n1),
         'c0_day11': _endpoint(d11['c0_ng_ml'], *obs['C0_ng_ml']['day11'], n11)}
    e['half_life_day1'] = {'model_emulated': d1['half_life_h'], 'observed_mean': obs['half_life_h']['day1'][0], 'classification': None}
    e['half_life_day11'] = {'model_emulated': d11['half_life_h'], 'observed_mean': obs['half_life_h']['day11'][0], 'classification': None}
    return e


def can1004_endpoints(prof, iv, n, times, reading):
    d1 = nca(times, prof['day1_ng_ml'], *reading)
    d11 = nca(times, prof['day11_ng_ml'], *reading)
    e = {'auc_last_day1': _endpoint(d1['auc_to_last_ng_h_ml'], *iv['auc_last_ng_h_ml']['day1'], n['day1']),
         'auc_last_day11': _endpoint(d11['auc_to_last_ng_h_ml'], *iv['auc_last_ng_h_ml']['day11'], n['day11']),
         'auc_inf_day1': _endpoint(d1['auc_ng_h_ml'], *iv['auc_inf_ng_h_ml']['day1'], n['day1']),
         'auc_inf_day11': _endpoint(d11['auc_ng_h_ml'], *iv['auc_inf_ng_h_ml']['day11'], n['day11']),
         'c0_day1': _endpoint(d1['c0_ng_ml'], *iv['c0_ng_ml']['day1'], n['day1']),
         'c0_day11': _endpoint(d11['c0_ng_ml'], *iv['c0_ng_ml']['day11'], n['day11'])}
    e['ratio_of_means_auc_last_day11_over_day1'] = {
        'model_emulated': d11['auc_to_last_ng_h_ml'] / d1['auc_to_last_ng_h_ml'],
        'observed': iv['auc_last_ng_h_ml']['day11'][0] / iv['auc_last_ng_h_ml']['day1'][0], 'classification': None}
    e['half_life_day1'] = {'model_emulated': d1['half_life_h'], 'observed_mean': iv['half_life_h']['day1'][0], 'classification': None}
    e['half_life_day11'] = {'model_emulated': d11['half_life_h'], 'observed_mean': iv['half_life_h']['day11'][0], 'classification': None}
    return e


OGAWA_PRIMARY = ('auc_day1', 'auc_day11', 'auc_ratio_day11_over_day1')
CAN1004_PRIMARY = ('auc_last_day1', 'auc_last_day11')


def numerical_checks(p):
    """Plan check 3: with Kon = 0 the plasma AUC after one dose, integrated by the solver to 2,000 h, matches the closed
    form. (A first implementation integrated a 0.5 h grid of concentrations by trapezoids; that quadrature overstated
    the fast initial phase by 2.3% and failed. It was replaced by the solver's own integral, step 0.00025 h, before
    this report was committed; recorded under 'correction'.)"""
    dose = dose_ug_per_kg(1.3, 'ogawa')
    sim = simulate(dict(p, Kon=0.0), dose, {2000.0}, dose_times_h=(0.0,))
    auc = sim['plasma_auc_by_interval_ng_h_ml']['last_dose_to_2000h']
    exact = closed_form_auc_without_binding(p, dose)
    return {'closed_form_without_binding': {
        'simulated_auc_0_2000h': auc, 'closed_form_auc_inf': exact, 'relative_difference': abs(auc - exact) / exact,
        'tail_at_2000h_ng_ml': sim['conc'][2000.0], 'passed': abs(auc - exact) / exact < 0.005, 'horizon_h': 2000.0,
        'correction': 'First run: 0.5 h trapezoid of sampled concentrations gave 178.17 vs 174.25 (2.3%, failed) because '
                      'of quadrature error in the check itself; the solver integral is used instead. No model value or '
                      'endpoint depended on that quadrature.'}}


def run_check():
    plan = load_plan()
    extract = model.load_extract()
    p = model.parameters(extract)
    ogawa = load_ogawa()
    can = load_can1004()
    o_times = ogawa['design']['sampling_times_h']
    c_times = can['design']['pk_sampling_times_after_dose_h']
    iv, n_iv = can['table7']['iv'], can['table7']['iv_n']
    conditions = [('primary', p, 1.0)] + [(f'body_size_x{f}', p, f) for f in BODY_FACTORS] + \
                 [('bmax_x1.4', dict(p, Bmax=p['Bmax'] * BMAX_SENSITIVITY_FACTOR), 1.0)]
    results = {'ogawa': {}, 'can1004': {}}
    balance = []
    for name, params, factor in conditions:
        doses = ('0.7', '1.0', '1.3') if name == 'primary' else ('1.3',)
        for d in doses:
            prof = _profiles(params, dose_ug_per_kg(float(d), 'ogawa', factor), o_times)
            balance.append(prof['mass_balance_error'])
            obs = ogawa['table3']['dose_levels'][d]
            results['ogawa'].setdefault(name, {})[d] = {
                'dose_ug_kg': dose_ug_per_kg(float(d), 'ogawa', factor), 'profile': prof,
                'readings': [{'auc_rule': r[0], 'terminal_points': r[1], 'endpoints': ogawa_endpoints(prof, obs, o_times, r)}
                             for r in NCA_READINGS]}
        prof = _profiles(params, dose_ug_per_kg(1.3, 'can1004', factor), c_times)
        balance.append(prof['mass_balance_error'])
        results['can1004'][name] = {'dose_ug_kg': dose_ug_per_kg(1.3, 'can1004', factor), 'profile': prof,
                                    'readings': [{'auc_rule': r[0], 'terminal_points': r[1],
                                                  'endpoints': can1004_endpoints(prof, iv, n_iv, c_times, r)} for r in NCA_READINGS]}
    # step halving, primary condition at 1.3 mg/m2, Ogawa
    half = _profiles(p, dose_ug_per_kg(1.3, 'ogawa'), o_times, step_h=STEP_H / 2)
    base = results['ogawa']['primary']['1.3']['readings'][0]['endpoints']
    half_e = ogawa_endpoints(half, ogawa['table3']['dose_levels']['1.3'], o_times, NCA_READINGS[0])
    step_change = max(abs(half_e[k]['model_emulated'] - base[k]['model_emulated']) / base[k]['model_emulated']
                      for k in ('auc_day1', 'auc_day11'))
    numerics = numerical_checks(p)
    numerics['mass_balance_max_relative_error'] = max(balance)
    numerics['mass_balance_passed'] = max(balance) < 1e-6
    numerics['step_halving_max_auc_change'] = step_change
    numerics['step_halving_passed'] = step_change < 0.001

    def classes(study, name, keys, dose='1.3'):
        node = results[study][name][dose] if study == 'ogawa' else results[study][name]
        return {k: node['readings'][0]['endpoints'][k]['classification'] for k in keys}

    prim_o = classes('ogawa', 'primary', OGAWA_PRIMARY)
    prim_c = classes('can1004', 'primary', CAN1004_PRIMARY)
    robust = {}
    for study, keys in (('ogawa', OGAWA_PRIMARY), ('can1004', CAN1004_PRIMARY)):
        for k in keys:
            seen = set()
            for name, _, _ in conditions:
                node = results[study][name]['1.3'] if study == 'ogawa' else results[study][name]
                if name == 'primary':
                    seen |= {r['endpoints'][k]['classification'] for r in node['readings']}
                else:
                    seen.add(node['readings'][0]['endpoints'][k]['classification'])
            robust[f'{study}:{k}'] = sorted(seen)
    consistent_o = all(v == 'consistent' for v in prim_o.values())
    consistent_c = all(v == 'consistent' for v in prim_c.values())
    report = {
        'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
        'plan_sha256': PLAN_SHA256, 'model_extract_sha256': model.EXTRACT_SHA256,
        'observed_sha256': {'ogawa': OGAWA_SHA256, 'can1004': CAN1004_SHA256},
        'classification': plan['classification'], 'independence': plan['independence'],
        'dose_input_assumption': plan['model']['dose_input'],
        'body_size': {s: dict(BODY[s], bsa_m2=bsa_du_bois(**BODY[s]), dose_ug_kg_at_1_3=dose_ug_per_kg(1.3, s)) for s in BODY},
        'numerical_checks': numerics,
        'results': results,
        'classifications_across_sensitivities': robust,
        'decision': {
            'primary_condition': plan['decision_rule']['primary_condition'],
            'ogawa_primary': prim_o, 'can1004_primary': prim_c,
            'consistent_with_ogawa': consistent_o, 'consistent_with_can1004': consistent_c,
            'resolves_3_0f_and_3_0h_findings': consistent_o and consistent_c,
            'robust': all(len(v) == 1 for v in robust.values()),
            'rule': plan['decision_rule']['summary']},
        'not_this': copy.deepcopy(plan['not_this']), 'known_differences': copy.deepcopy(plan['known_differences']),
        'clinical_prediction_validated': False,
    }
    report['report_sha256'] = digest(report)
    return report


def register_bortezomib_pbpk_iwasaki_check_commands(app):
    @app.cli.command('bortezomib-pbpk-iwasaki-check')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(output):
        """Check the Iwasaki 2020 PBPK model against Ogawa 2008 and CAN-1004 (Simulation 3.0k). Not validation."""
        try:
            report = run_check()
        except (ValueError, OSError, KeyError) as exc:
            raise click.ClickException(str(exc)) from exc
        payload = json.dumps(report, indent=1, ensure_ascii=False, allow_nan=False) + '\n'
        if output:
            with output.open('x', encoding='utf-8') as handle:
                handle.write(payload)
            click.echo(f'Saved report: {output}\nReport SHA256: {report["report_sha256"]}')
        else:
            click.echo(payload, nl=False)
