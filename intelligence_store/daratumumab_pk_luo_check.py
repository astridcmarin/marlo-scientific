"""Simulation 3.2b: locked external consistency check of the Luo 2021 daratumumab model against the intravenous
first-dose data of SIRIUS (8 mg/kg) and GEN501 Part 2 (16 mg/kg) reported by Clemens 2017.

Executes daratumumab_pk_luo_check_plan_v1.json (pinned; locked in commit 817f8e2 before any concentration was
computed). Exploratory; not validation, not an acceptance decision and not a dosing tool.
"""
import copy
import hashlib
import json
import math
import random
from pathlib import Path

import click

from . import daratumumab_pk_luo as model
from .patient_state import digest
from .renal_group_check import _percentile

SCHEMA_VERSION = 'daratumumab-pk-luo-check-report-v1'
METHOD_VERSION = 'daratumumab-pk-luo-check-v1.0'
ROOT = Path(__file__).resolve().parent.parent
PLAN_PATH = Path(__file__).parent / 'data' / 'daratumumab_pk_luo_check_plan_v1.json'
PLAN_SHA256 = 'de2682e493f8012975d568dbf0999cb09085fb64d82e08356f31e40092effc30'
PLAN_COMMIT = '817f8e2'
OBSERVED_SHA256 = '2872913fd369aea906fc4a11623755d8ff3722c75de0d1fbe55e567992632ed0'
REPORT_PATH = ROOT / 'docs' / 'verification' / 'daratumumab_pk_luo_check_v1.json'
PERCENTILES = (5, 50, 95)
P_IGG = 427 / 742
P_MALE = 421 / 742
DESCRIPTIVE_PATIENTS = 2000
DESCRIPTIVE_SEED_OFFSET = 1000

SCENARIOS = {
    'primary': {},
    'omega_equals_cv': {'omega': 'cv'},
    'igg_0_40': {'p_igg': 0.40},
    'igg_0_75': {'p_igg': 0.75},
    'covariate_spread': {'spread': True},
    'sex_factor_on_females': {'sex_factor_on': 'female'},
    'infusion_3h': {'first_h': 3.0, 'later_h': 3.0},
    'kdes_zero': {'kdes_zero': True},
}
# (endpoint id, study, dose mg/kg, metric, n, observed key path)
ENDPOINTS = (
    ('sirius_8.cmax', 'sirius_8', 8.0, 'cmax', 18, ('sirius_8_mg_kg_first_full_infusion', 'cmax_ug_ml'), 'primary'),
    ('sirius_8.auc_inf', 'sirius_8', 8.0, 'auc_inf', 15, ('sirius_8_mg_kg_first_full_infusion', 'auc_inf_ug_h_ml'), 'primary'),
    ('gen501_16.cmax', 'gen501_16', 16.0, 'cmax', 40, ('gen501_part2_first_full_infusion', '16_mg_kg', 'cmax_ug_ml'), 'primary'),
    ('gen501_16.auc_0_7d', 'gen501_16', 16.0, 'auc_0_7d', 20, ('gen501_part2_first_full_infusion', '16_mg_kg', 'auc_0_7d_ug_h_ml'), 'primary'),
    ('gen501_8.cmax', 'gen501_8', 8.0, 'cmax', 28, ('gen501_part2_first_full_infusion', '8_mg_kg', 'cmax_ug_ml'), 'secondary'),
)
GROUPS = {'sirius_8': (8.0, 18), 'gen501_16': (16.0, 40), 'gen501_8': (8.0, 28)}


def _pinned(path, sha, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError(f'{label} is missing or changed; no check was run.')
    return json.loads(raw)


def load_plan(path=PLAN_PATH):
    return _pinned(path, PLAN_SHA256, 'Analysis plan')


def load_inputs(plan):
    extract = _pinned(ROOT / plan['data']['model_extract']['path'], plan['data']['model_extract']['sha256'], 'Model extract')
    if plan['data']['model_extract']['sha256'] != model.EXTRACT_SHA256:
        raise ValueError('Plan and model module pin different extracts.')
    if plan['data']['observed']['sha256'] != OBSERVED_SHA256:
        raise ValueError('Plan and check module pin different observed data.')
    observed = _pinned(ROOT / plan['data']['observed']['path'], plan['data']['observed']['sha256'], 'Observed data')
    return extract, observed


def observed_value(observed, path):
    node = observed
    for key in path:
        node = node[key]
    return node


def _omegas(extract, how):
    re_ = extract['parameters']['random_effects']
    cvs = {k: re_[f'iiv_{k}_cv_percent'] / 100.0 for k in ('cl', 'v1', 'vmax', 'kdes')}
    return cvs if how == 'cv' else {k: math.sqrt(math.log(1 + cv * cv)) for k, cv in cvs.items()}


def draw_patient(rng, extract, settings, om):
    """One virtual patient. Every random number is drawn in the same order in every scenario."""
    u_igg, u_male = rng.random(), rng.random()
    z_wt, z_alb = rng.gauss(0, 1), rng.gauss(0, 1)
    z = [rng.gauss(0, 1) for _ in range(4)]
    igg = u_igg < settings.get('p_igg', P_IGG)
    male = u_male < P_MALE
    weight, albumin = model.REFERENCE_WEIGHT_KG, model.REFERENCE_ALBUMIN_G_L
    if settings.get('spread'):
        weight = model.REFERENCE_WEIGHT_KG * math.exp(math.sqrt(math.log(1 + 0.2 ** 2)) * z_wt)
        albumin = min(55.0, max(20.0, 37.0 + 5.0 * z_alb))
    p = model.typical_parameters(extract, weight, albumin, igg, male, settings.get('sex_factor_on', 'male'))
    p['cl'] *= math.exp(om['cl'] * z[0])
    p['v1'] *= math.exp(om['v1'] * z[1])
    p['vmax'] *= math.exp(om['vmax'] * z[2])
    p['kdes'] = 0.0 if settings.get('kdes_zero') else p['kdes'] * math.exp(om['kdes'] * z[3])
    return p, weight


def first_dose(p, weight, dose_mg_kg, duration_h, auc_inf=False, horizon_h=None):
    eoi = duration_h
    outs = [eoi, eoi + 2.0] + ([horizon_h] if horizon_h else [])
    r = model.simulate(p, [(0.0, dose_mg_kg * weight, duration_h)], outs, until_fraction_of_max=0.001 if auc_inf else None)
    res = {'cmax': max(r['at'][eoi]['conc'], r['at'][eoi + 2.0]['conc'])}
    if horizon_h:
        res['auc_0_7d'] = r['at'][horizon_h]['auc']
    if auc_inf:
        res['auc_inf'] = r['auc_infinity']
        res['tail_fraction'] = r['tail_fraction']
    return res


def simulate_scenario(extract, settings, trials, seed):
    om = _omegas(extract, settings.get('omega', 'exact'))
    first_h = settings.get('first_h', 7.0)
    rng = random.Random(seed)
    means = {e[0]: [] for e in ENDPOINTS}
    max_tail = 0.0
    for _ in range(trials):
        for group, (dose, n) in GROUPS.items():
            vals = {'cmax': [], 'auc_inf': [], 'auc_0_7d': []}
            for i in range(n):
                p, wt = draw_patient(rng, extract, settings, om)
                if group == 'sirius_8':
                    r = first_dose(p, wt, dose, first_h, auc_inf=i < 15)
                    if i < 15:
                        vals['auc_inf'].append(r['auc_inf'])
                        max_tail = max(max_tail, r['tail_fraction'])
                elif group == 'gen501_16':
                    r = first_dose(p, wt, dose, first_h, horizon_h=168.0)
                    if i < 20:
                        vals['auc_0_7d'].append(r['auc_0_7d'])
                else:
                    r = first_dose(p, wt, dose, first_h)
                vals['cmax'].append(r['cmax'])
            for eid, g, _, metric, *_ in ENDPOINTS:
                if g == group:
                    means[eid].append(math.fsum(vals[metric]) / len(vals[metric]))
    return means, {'max_auc_inf_tail_fraction': max_tail}


def _summary(values):
    return {f'p{q:02d}': _percentile(values, q) for q in PERCENTILES}


def _classify(observed, s):
    if observed > s['p95']:
        return 'model_under_predicts'
    if observed < s['p05']:
        return 'model_over_predicts'
    return 'consistent'


def numerical_checks(extract):
    p = model.typical_parameters(extract)
    wt = model.REFERENCE_WEIGHT_KG
    balance = []
    for dose in (8.0, 16.0):
        for t_end in (168.0, 1000.0):
            r = model.simulate(p, [(0.0, dose * wt, 7.0)], [7.0, t_end])
            total = r['amount_central_mg'] + r['amount_peripheral_mg'] + r['removed_linear_mg'] + r['removed_saturable_mg']
            balance.append(abs(total - dose * wt) / (dose * wt))

    def endpoints(fine, coarse):
        a = model.simulate(p, [(0.0, 8 * wt, 7.0)], [7.0, 9.0], fine, coarse, until_fraction_of_max=0.001)
        b = model.simulate(p, [(0.0, 16 * wt, 7.0)], [7.0, 9.0, 168.0], fine, coarse)
        return [max(a['at'][7.0]['conc'], a['at'][9.0]['conc']), a['auc_infinity'],
                max(b['at'][7.0]['conc'], b['at'][9.0]['conc']), b['at'][168.0]['auc']]
    base, half = endpoints(0.05, 1.0), endpoints(0.025, 0.5)
    halving = max(abs(x - y) / y for x, y in zip(base, half))
    q = dict(p, vmax=0.0)
    lin = model.simulate(q, [(0.0, 8 * wt, 7.0)], [7.0], until_fraction_of_max=0.001)
    lin_ratio = lin['auc_infinity'] / (8 * wt / p['cl'])
    return {'mass_balance_max_relative_error': max(balance), 'mass_balance_pass': max(balance) <= 1e-6,
            'step_halving_max_relative_change': halving, 'step_halving_pass': halving < 1e-3,
            'linear_auc_inf_over_dose_over_cl': lin_ratio, 'linear_auc_pass': abs(lin_ratio - 1) <= 5e-3}


def descriptive(extract, observed, seed):
    p0 = model.typical_parameters(extract)
    wt = model.REFERENCE_WEIGHT_KG
    share = {}
    for dose in (8.0, 16.0):
        r = model.simulate(p0, [(0.0, dose * wt, 7.0)], [7.0, 168.0])
        share[f'{int(dose)}_mg_kg'] = r['removed_saturable_mg'] / (r['removed_saturable_mg'] + r['removed_linear_mg'])
    om = _omegas(extract, 'exact')
    rng = random.Random(seed)
    weekly = [(168.0 * k, None, 7.0 if k == 0 else 4.0) for k in range(9)]
    vals = {'eoi1': [], 'trough9': [], 'eoi9': [], 'p1_cmax': [], 'p1_auc_inf': []}
    for _ in range(DESCRIPTIVE_PATIENTS):
        p, w = draw_patient(rng, extract, {}, om)
        inf = [(s, 16.0 * w, d) for s, _, d in weekly]
        r = model.simulate(p, inf, [7.0, 1344.0, 1348.0])
        vals['eoi1'].append(r['at'][7.0]['conc'])
        vals['trough9'].append(r['at'][1344.0]['conc'])
        vals['eoi9'].append(r['at'][1348.0]['conc'])
        p, w = draw_patient(rng, extract, {}, om)
        r1 = first_dose(p, w, 16.0, 7.0, auc_inf=True)
        vals['p1_cmax'].append(r1['cmax'])
        vals['p1_auc_inf'].append(r1['auc_inf'])

    def row(key, obs):
        m = math.fsum(vals[key]) / len(vals[key])
        sd = math.sqrt(math.fsum((v - m) ** 2 for v in vals[key]) / (len(vals[key]) - 1))
        return {'observed_mean': obs['mean'], 'observed_sd': obs.get('sd'), 'observed_n': obs.get('n'),
                'simulated_mean': m, 'simulated_sd': sd, 'observed_over_simulated_mean': obs['mean'] / m}
    s16 = observed['sirius_16_mg_kg_text']
    p1 = observed['gen501_part1_16_mg_kg']['first_full_infusion']
    return {'saturable_share_of_elimination_first_week_typical_patient': share,
            'simulated_patients': DESCRIPTIVE_PATIENTS, 'seed': seed,
            'regimen_sirius_16': 'Weekly 16 mg/kg infusions at 0, 168, ..., 1344 h (7 h first, 4 h later); trough at 1344 h before the ninth infusion; EOI of the ninth at 1348 h.',
            'sirius_16_eoi_first': row('eoi1', s16['eoi_first_infusion_ug_ml']),
            'sirius_16_trough_before_ninth': row('trough9', s16['trough_end_of_weekly_dosing_ug_ml']),
            'sirius_16_eoi_ninth': row('eoi9', s16['eoi_ninth_infusion_ug_ml']),
            'gen501_part1_16_first_cmax': row('p1_cmax', p1['cmax_ug_ml']),
            'gen501_part1_16_first_auc_inf': row('p1_auc_inf', p1['auc_inf_ug_h_ml'])}


def run_check(trials=None):
    plan = load_plan()
    extract, observed = load_inputs(plan)
    if list(SCENARIOS) != plan['comparison']['scenarios']:
        raise ValueError('Scenario list differs from the plan.')
    trials = trials or plan['simulation']['virtual_trials']
    seed = plan['simulation']['seed']
    checks = numerical_checks(extract)
    if not (checks['mass_balance_pass'] and checks['step_halving_pass'] and checks['linear_auc_pass']):
        raise ValueError('Numerical checks failed; no comparison was run.')
    scenarios = {}
    for index, (name, settings) in enumerate(SCENARIOS.items()):
        means, info = simulate_scenario(extract, settings, trials, seed + index)
        rows = []
        for eid, group, dose, metric, n, path, kind in ENDPOINTS:
            obs = observed_value(observed, path)
            sim = _summary(means[eid])
            rows.append({'endpoint': eid, 'kind': kind, 'dose_mg_kg': dose, 'n': n, 'observed_mean': obs['mean'], 'observed_sd': obs['sd'],
                         'simulated_group_mean': sim, 'classification': _classify(obs['mean'], sim),
                         'observed_over_median': obs['mean'] / sim['p50']})
        scenarios[name] = {'settings': settings, 'endpoints': rows, **info}
    by_endpoint = {}
    for eid, *_, kind in ENDPOINTS:
        per = {name: next(r for r in s['endpoints'] if r['endpoint'] == eid)['classification'] for name, s in scenarios.items()}
        by_endpoint[eid] = {'kind': kind, 'primary': per['primary'], 'across_scenarios': sorted(set(per.values())),
                            'robust': len(set(per.values())) == 1, 'by_scenario': per}
    primary_ok = all(v['primary'] == 'consistent' for v in by_endpoint.values() if v['kind'] == 'primary')
    primary_robust = all(v['robust'] for v in by_endpoint.values() if v['kind'] == 'primary')
    decision = {'consistent_with_first_dose_iv_exposure': primary_ok, 'robust': primary_robust,
                'registration_may_be_proposed': primary_ok and primary_robust}
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'model_version': model.MODEL_VERSION,
              'plan_version': plan['plan_version'], 'plan_sha256': PLAN_SHA256, 'plan_locked_in_commit': PLAN_COMMIT,
              'model_extract_sha256': plan['data']['model_extract']['sha256'], 'observed_sha256': plan['data']['observed']['sha256'],
              'trials': trials, 'seed': seed, 'covariate_probabilities_primary': {'igg': P_IGG, 'male': P_MALE},
              'classification': plan['classification'], 'independence': plan['independence'], 'not_this': copy.deepcopy(plan['not_this']),
              'numerical_checks': checks, 'classification_by_endpoint': by_endpoint, 'decision': decision, 'scenarios': scenarios,
              'descriptive': descriptive(extract, observed, seed + DESCRIPTIVE_SEED_OFFSET),
              'known_differences': copy.deepcopy(plan['known_differences']), 'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_daratumumab_pk_luo_check_commands(app):
    @app.cli.command('daratumumab-pk-luo-check')
    @click.option('--trials', type=click.IntRange(10, 100000), help='Override the plan (for quick looks only).')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(trials, output):
        """Run the locked Luo 2021 daratumumab consistency check (Simulation 3.2b). Exploratory; not validation."""
        try:
            report = run_check(trials=trials)
        except (ValueError, OSError, KeyError) as exc:
            raise click.ClickException(str(exc)) from exc
        payload = json.dumps(report, indent=1, ensure_ascii=False, allow_nan=False) + '\n'
        if output:
            with output.open('x', encoding='utf-8') as handle:
                handle.write(payload)
            click.echo(f'Saved report: {output}\nReport SHA256: {report["report_sha256"]}')
        else:
            click.echo(payload, nl=False)
