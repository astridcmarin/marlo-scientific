"""Simulation 3.2a: locked external consistency check of the Gupta 2017 ixazomib model against the dedicated renal
(NCT01830816) and hepatic (NCT01912222) impairment studies.

Executes ixazomib_pk_gupta_check_plan_v1_1.json (pinned): plan v1.0 (locked in commit 982044c before any
concentration was computed) plus amendment 1 (commit 63c97f1, before any group result): simulated patients with fewer
than 3 quantifiable samples are not PK-evaluable and are replaced.
Virtual trials with the studies' designs and group sizes are simulated under the model's between-patient
variability; each observed group geometric mean (and impaired/normal ratio) is compared with the 5th-95th percentile
of the simulated values. Exploratory; not validation, not an acceptance decision and not a dosing tool.
"""
import copy
import hashlib
import json
import math
import random
from pathlib import Path

import click

from . import ixazomib_pk_gupta as model
from .patient_state import digest
from .renal_group_check import _percentile

SCHEMA_VERSION = 'ixazomib-pk-gupta-check-report-v1'
METHOD_VERSION = 'ixazomib-pk-gupta-check-v1.0'
ROOT = Path(__file__).resolve().parent.parent
PLAN_PATH = Path(__file__).parent / 'data' / 'ixazomib_pk_gupta_check_plan_v1_1.json'
PLAN_SHA256 = '2c91074731f5cecefa6c84fea915aa7aff28e5f8fb58e0e3e37f857e1dc9e4c4'
PLAN_COMMITS = {'v1.0': '982044c', 'amendment_1': '63c97f1'}
# Plan v1.0, superseded by v1.1 (amendment 1) and kept unchanged for traceability.
PLAN_V1_0_SHA256 = '9b8ef3d87dc78b5242f1008c41f4fe0fab39c97aa098786304e5d8de703bae51'
MIN_QUANTIFIABLE = 3
REPORT_PATH = ROOT / 'docs' / 'verification' / 'ixazomib_pk_gupta_check_v1.json'
LLOQ = 0.5
PERCENTILES = (5, 50, 95)

# (study, group, observed key, dose mg, n for Cmax, n for AUC)
GROUPS = (
    ('renal', 'normal', 3.0, 18, 15),
    ('renal', 'severe_ri', 3.0, 14, 10),
    ('renal', 'esrd', 3.0, 6, 6),
    ('hepatic', 'normal', 4.0, 12, 12),
    ('hepatic', 'moderate', 2.3, 13, 10),
    ('hepatic', 'severe', 1.5, 18, 11),
)
RATIOS = (('renal', 'severe_ri'), ('renal', 'esrd'), ('hepatic', 'moderate'), ('hepatic', 'severe'))
SCENARIOS = {
    'primary': {},
    'omega_equals_cv': {'omega': 'cv'},
    'f_capped_at_1': {'cap_f': True},
    'bsa_1_5': {'bsa': 1.5},
    'bsa_2_25': {'bsa': 2.25},
    'auc_linear_up_log_down': {'auc_rule': 'linear_up_log_down'},
}


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
    observed = _pinned(ROOT / plan['data']['observed']['path'], plan['data']['observed']['sha256'], 'Observed data')
    return extract, observed


def sampling_times(observed, study, group):
    design = observed['studies'][study]['design']
    times = list(design['sampling_times_h'])
    if study == 'renal' and group == 'esrd':
        times = sorted(times + design['extra_sampling_times_esrd_h'])
    return times


def pk_evaluable(conc):
    return sum(c >= LLOQ for c in conc) >= MIN_QUANTIFIABLE


def nca(times_h, conc, rule='linear'):
    """Cmax over the samples; AUC0-last from (0, 0) to the last sample at or above the LLOQ."""
    last = max((i for i, c in enumerate(conc) if c >= LLOQ), default=None)
    if last is None:
        raise ValueError('No quantifiable concentration.')
    t = [0.0] + list(times_h[:last + 1])
    c = [0.0] + list(conc[:last + 1])
    auc = 0.0
    for i in range(1, len(t)):
        dt, a, b = t[i] - t[i - 1], c[i - 1], c[i]
        if rule == 'linear_up_log_down' and 0 < b < a:
            auc += dt * (a - b) / math.log(a / b)
        elif rule in ('linear', 'linear_up_log_down'):
            auc += dt * (a + b) / 2.0
        else:
            raise ValueError('Unknown AUC rule.')
    return {'cmax': max(conc), 'auc_last': auc, 't_last': t[-1]}


def _omegas(extract, how):
    re_ = extract['parameters']['random_effects']
    cvs = {k: re_[f'iiv_{k}_cv_percent']['value'] / 100.0 for k in ('cl', 'f', 'v4')}
    if how == 'cv':
        return cvs
    return {k: math.sqrt(math.log(1.0 + cv * cv)) for k, cv in cvs.items()}


def _gm(values):
    return math.exp(math.fsum(math.log(v) for v in values) / len(values))


def _gcv(values):
    logs = [math.log(v) for v in values]
    m = math.fsum(logs) / len(logs)
    s2 = math.fsum((x - m) ** 2 for x in logs) / (len(logs) - 1)
    return 100.0 * math.sqrt(math.exp(s2) - 1.0)


def _summary(values):
    return {f'p{q:02d}': _percentile(values, q) for q in PERCENTILES}


def _classify(observed, s):
    if observed > s['p95']:
        return 'model_under_predicts'
    if observed < s['p05']:
        return 'model_over_predicts'
    return 'consistent'


def simulate_scenario(extract, observed, settings, trials, seed):
    typical = model.typical_parameters(extract, settings.get('bsa', model.REFERENCE_BSA_M2))
    om = _omegas(extract, settings.get('omega', 'exact'))
    rho = extract['parameters']['random_effects']['correlation_log_cl_log_f']['value']
    rule = settings.get('auc_rule', 'linear')
    rng = random.Random(seed)
    times = {(s, g): sampling_times(observed, s, g) for s, g, *_ in GROUPS}
    gm = {(s, g): {'cmax': [], 'auc_last': []} for s, g, *_ in GROUPS}
    gcv = {(s, g): [] for s, g, *_ in GROUPS}
    f_above_1 = patients = 0
    replaced = {(s, g): 0 for s, g, *_ in GROUPS}
    for _ in range(trials):
        for study, group, dose, n_cmax, n_auc in GROUPS:
            cmaxes, aucs = [], []
            while len(cmaxes) < n_cmax:
                z1, z2, z3 = rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)
                p = dict(typical)
                p['cl'] = typical['cl'] * math.exp(om['cl'] * z1)
                p['f'] = typical['f'] * math.exp(om['f'] * (rho * z1 + math.sqrt(1 - rho * rho) * z2))
                p['v4'] = typical['v4'] * math.exp(om['v4'] * z3)
                patients += 1
                f_above_1 += p['f'] > 1.0
                if settings.get('cap_f'):
                    p['f'] = min(p['f'], 1.0)
                conc = model.concentration(times[(study, group)], dose, p)
                if not pk_evaluable(conc):
                    replaced[(study, group)] += 1
                    continue
                res = nca(times[(study, group)], conc, rule)
                if len(cmaxes) < n_auc:
                    aucs.append(res['auc_last'] / dose)
                cmaxes.append(res['cmax'] / dose)
            gm[(study, group)]['cmax'].append(_gm(cmaxes))
            gm[(study, group)]['auc_last'].append(_gm(aucs))
            gcv[(study, group)].append(_gcv(aucs))
    return gm, gcv, {'share_f_above_1': f_above_1 / patients, 'patients_drawn': patients,
                     'replaced_not_pk_evaluable': {f'{s}.{g}': n for (s, g), n in replaced.items()}}


def _observed(observed):
    out = {}
    for study, group, dose, *_ in GROUPS:
        row = observed['studies'][study]['table2']['groups'][group]
        out[(study, group)] = {'dose_mg': dose, 'cmax': row['cmax_ng_ml']['gm'], 'auc_last': row['auc_last_ng_h_ml']['gm'],
                               'auc_cv_percent': row['auc_last_ng_h_ml']['cv_percent']}
    return out


def summarise_scenario(gm, gcv, obs):
    groups, ratios = [], []
    for study, group, dose, n_cmax, n_auc in GROUPS:
        row = {'study': study, 'group': group, 'dose_mg': dose, 'n_cmax': n_cmax, 'n_auc': n_auc}
        for ep in ('auc_last', 'cmax'):
            sim = _summary([v * dose for v in gm[(study, group)][ep]])
            o = obs[(study, group)][ep]
            row[ep] = {'observed_gm': o, 'simulated_group_gm': sim, 'classification': _classify(o, sim),
                       'observed_over_median': o / sim['p50']}
        row['auc_last']['simulated_geometric_cv_percent_median'] = _percentile(gcv[(study, group)], 50)
        row['auc_last']['observed_cv_percent'] = obs[(study, group)]['auc_cv_percent']
        groups.append(row)
    for study, group in RATIOS:
        row = {'study': study, 'group': group, 'versus': 'normal', 'dose_normalised': study == 'hepatic'}
        for ep in ('auc_last', 'cmax'):
            sim = _summary([a / b for a, b in zip(gm[(study, group)][ep], gm[(study, 'normal')][ep])])
            o = (obs[(study, group)][ep] / obs[(study, group)]['dose_mg']) / (obs[(study, 'normal')][ep] / obs[(study, 'normal')]['dose_mg'])
            row[ep] = {'observed_ratio': o, 'simulated_ratio': sim, 'classification': _classify(o, sim),
                       'observed_over_median': o / sim['p50']}
        ratios.append(row)
    between = _summary([a / b for a, b in zip(gm[('hepatic', 'normal')]['auc_last'], gm[('renal', 'normal')]['auc_last'])])
    o_between = (obs[('hepatic', 'normal')]['auc_last'] / 4.0) / (obs[('renal', 'normal')]['auc_last'] / 3.0)
    return {'groups': groups, 'ratios': ratios,
            'between_study_normal_groups': {'endpoint': 'dose-normalised AUC0-last, hepatic-study normal / renal-study normal',
                                            'observed_ratio': o_between, 'simulated_ratio': between,
                                            'classification': _classify(o_between, between)}}


def numerical_checks(extract):
    p = model.typical_parameters(extract)
    times = [0.5, 1, 1.5, 2, 3, 4, 8, 24, 48, 72, 96, 120, 144, 168, 240, 264, 336]
    closed = model.concentration(times, 3.0, p)
    rk = model.integrate(times, 3.0, p, step_h=0.001)
    rel = max(abs(a - b['conc']) / b['conc'] for a, b in zip(closed, rk))
    # AUC 0-20,000 h of the closed form: exact integral of each term.
    rates, coef = model.disposition_rates(p), model.impulse_coefficients(p)
    amount, ka, tl, T = p['f'] * 3000.0, p['ka'], p['tlag'], 20000.0
    tau = T - tl
    auc = amount * ka * math.fsum(a / (ka - lam) * ((1 - math.exp(-lam * tau)) / lam - (1 - math.exp(-ka * tau)) / ka)
                                  for a, lam in zip(coef, rates))
    auc_inf = model.auc_infinity(3.0, p)
    balance = []
    for r in model.integrate([24, 168, 336], 3.0, p, step_h=0.001):
        total = math.fsum(r['amounts']) + r['eliminated']
        balance.append(abs(total - amount) / amount)
    return {
        'closed_form_vs_runge_kutta_max_relative_difference': rel,
        'closed_form_vs_runge_kutta_pass': rel <= 1e-6,
        'auc_0_20000_h_over_f_dose_over_cl': auc / auc_inf,
        'auc_pass': abs(auc / auc_inf - 1) <= 1e-3,
        'mass_balance_max_relative_error': max(balance),
        'mass_balance_pass': max(balance) <= 1e-9,
        'disposition_rates_per_h': rates,
        'half_lives_h': [math.log(2) / r for r in rates],
    }


def descriptive(extract, observed):
    p = model.typical_parameters(extract)
    times = sampling_times(observed, 'renal', 'normal')
    res = nca(times, model.concentration(times, 3.0, p))
    inf = model.auc_infinity(3.0, p)
    return {'typical_patient_3_mg': {'auc_infinity_ng_h_ml': inf, 'auc_last_ng_h_ml': res['auc_last'], 'cmax_ng_ml': res['cmax'],
                                     'fraction_of_auc_infinity_in_auc_last': res['auc_last'] / inf,
                                     'terminal_half_life_days': math.log(2) / model.disposition_rates(p)[-1] / 24.0}}


def run_check(trials=None):
    plan = load_plan()
    extract, observed = load_inputs(plan)
    if list(SCENARIOS) != plan['comparison']['scenarios']:
        raise ValueError('Scenario list differs from the plan.')
    trials = trials or plan['simulation']['virtual_trials']
    seed = plan['simulation']['seed']
    obs = _observed(observed)
    checks = numerical_checks(extract)
    if not (checks['closed_form_vs_runge_kutta_pass'] and checks['auc_pass'] and checks['mass_balance_pass']):
        raise ValueError('Numerical checks failed; no comparison was run.')
    scenarios = {}
    for index, (name, settings) in enumerate(SCENARIOS.items()):
        gm, gcv, info = simulate_scenario(extract, observed, settings, trials, seed + index)
        scenarios[name] = dict(summarise_scenario(gm, gcv, obs), settings=settings, **info)
    primary = scenarios['primary']
    endpoints = [(f"{r['study']}.{r['group']}.{ep}", lambda s, r=r, ep=ep: next(x for x in s['groups'] if (x['study'], x['group']) == (r['study'], r['group']))[ep]['classification'])
                 for r in primary['groups'] for ep in ('auc_last', 'cmax')]
    endpoints += [(f"{r['study']}.{r['group']}_vs_normal.{ep}", lambda s, r=r, ep=ep: next(x for x in s['ratios'] if (x['study'], x['group']) == (r['study'], r['group']))[ep]['classification'])
                  for r in primary['ratios'] for ep in ('auc_last', 'cmax')]
    by_endpoint = {name: {'primary': get(primary), 'across_scenarios': sorted({get(s) for s in scenarios.values()})} for name, get in endpoints}
    for v in by_endpoint.values():
        v['robust'] = len(v['across_scenarios']) == 1
    normal_auc = {s: by_endpoint[f'{s}.normal.auc_last'] for s in ('renal', 'hepatic')}
    impairment = {f'{s}.{g}': ('exposure_increase_beyond_model_variability' if by_endpoint[f'{s}.{g}_vs_normal.auc_last']['primary'] == 'model_under_predicts'
                               else 'not_distinguishable_from_no_effect_at_this_group_size' if by_endpoint[f'{s}.{g}_vs_normal.auc_last']['primary'] == 'consistent'
                               else 'exposure_lower_than_model_variability')
                  for s, g in RATIOS}
    decision = {
        'normal_function': ('consistent_with_both_normal_groups' if all(v['primary'] == 'consistent' for v in normal_auc.values())
                            else 'consistent_with_one_normal_group' if any(v['primary'] == 'consistent' for v in normal_auc.values())
                            else 'not_consistent_with_either_normal_group'),
        'normal_function_robust': all(v['robust'] for v in normal_auc.values()),
        'impairment_auc_ratio': impairment,
        'registration_may_be_proposed': (all(v['primary'] == 'consistent' and v['robust'] for v in normal_auc.values())),
    }
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'model_version': model.MODEL_VERSION,
              'plan_version': plan['plan_version'], 'plan_sha256': PLAN_SHA256, 'plan_commits': PLAN_COMMITS,
              'amendments': copy.deepcopy(plan['amendments']),
              'model_extract_sha256': plan['data']['model_extract']['sha256'], 'observed_sha256': plan['data']['observed']['sha256'],
              'trials': trials, 'seed': seed, 'classification': plan['classification'], 'not_this': copy.deepcopy(plan['not_this']),
              'numerical_checks': checks, 'descriptive': descriptive(extract, observed),
              'classification_by_endpoint': by_endpoint, 'decision': decision, 'scenarios': scenarios,
              'known_differences': copy.deepcopy(plan['known_differences']), 'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_ixazomib_pk_gupta_check_commands(app):
    @app.cli.command('ixazomib-pk-gupta-check')
    @click.option('--trials', type=click.IntRange(100, 100000), help='Override the plan (for quick looks only).')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(trials, output):
        """Run the locked Gupta 2017 ixazomib consistency check (Simulation 3.2a). Exploratory; not validation."""
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
