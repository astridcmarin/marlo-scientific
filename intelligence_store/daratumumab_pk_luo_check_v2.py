"""Simulation 3.2c: second locked check of the Luo 2021 daratumumab model, with study demographics.

Executes daratumumab_pk_luo_check_plan_v2.json (pinned; locked in commit cae3463 before computing). Identical to the
v1 check (daratumumab_pk_luo_check.py, unchanged) except that each study's virtual patients take that study's
demographics from Clemens 2017 ESM Table 2 instead of the model's reference values. No descriptive endpoints.
Exploratory; not validation, not an acceptance decision and not a dosing tool.
"""
import copy
import json
import math
import random
from pathlib import Path

import click

from . import daratumumab_pk_luo as model
from . import daratumumab_pk_luo_check as v1
from .patient_state import digest

SCHEMA_VERSION = 'daratumumab-pk-luo-check-report-v2'
METHOD_VERSION = 'daratumumab-pk-luo-check-v2.0'
PLAN_PATH = Path(__file__).parent / 'data' / 'daratumumab_pk_luo_check_plan_v2.json'
PLAN_SHA256 = '52952fd5d3347d22a2d1b5691be0c63c51ef1f5fd47cc1fda28ab3aba55d73db'
PLAN_COMMIT = 'cae3463'
SUPPLEMENT_SHA256 = '4bf5724fe66bb10d921ce8c8a70eb0bf4f52498f7a5e30272e458a1ce0b6a6cb'
REPORT_PATH = v1.ROOT / 'docs' / 'verification' / 'daratumumab_pk_luo_check_v2.json'
STUDY_OF_GROUP = {'sirius_8': 'SIRIUS', 'gen501_16': 'GEN501', 'gen501_8': 'GEN501'}


def load_plan(path=PLAN_PATH):
    return v1._pinned(path, PLAN_SHA256, 'Analysis plan v2')


def load_inputs(plan):
    extract, observed = v1.load_inputs(plan)
    if plan['data']['supplement']['sha256'] != SUPPLEMENT_SHA256:
        raise ValueError('Plan and check module pin different supplement data.')
    supplement = v1._pinned(v1.ROOT / plan['data']['supplement']['path'], plan['data']['supplement']['sha256'], 'Supplement')
    return extract, observed, supplement


def study_covariates(supplement):
    out = {}
    table = supplement['baseline_supplemental_table_2']
    for study in ('SIRIUS', 'GEN501'):
        row = table[study]
        out[study] = {'weight': row['weight_kg']['median'], 'albumin': row['albumin_g_l']['median'],
                      'albumin_range': row['albumin_g_l']['range'],
                      'p_igg': row['igg_myeloma'][0] / row['igg_myeloma'][1], 'p_male': row['male'][0] / row['male'][1]}
    return out


def draw_patient(rng, extract, settings, om, cov):
    """As v1.draw_patient (same random numbers in the same order), with the study's covariates."""
    u_igg, u_male = rng.random(), rng.random()
    z_wt, z_alb = rng.gauss(0, 1), rng.gauss(0, 1)
    z = [rng.gauss(0, 1) for _ in range(4)]
    igg = u_igg < settings.get('p_igg', cov['p_igg'])
    male = u_male < cov['p_male']
    weight, albumin = cov['weight'], cov['albumin']
    if settings.get('spread'):
        lo, hi = cov['albumin_range']
        weight = cov['weight'] * math.exp(math.sqrt(math.log(1 + 0.2 ** 2)) * z_wt)
        albumin = min(hi, max(lo, cov['albumin'] + 5.0 * z_alb))
    p = model.typical_parameters(extract, weight, albumin, igg, male, settings.get('sex_factor_on', 'male'))
    p['cl'] *= math.exp(om['cl'] * z[0])
    p['v1'] *= math.exp(om['v1'] * z[1])
    p['vmax'] *= math.exp(om['vmax'] * z[2])
    p['kdes'] = 0.0 if settings.get('kdes_zero') else p['kdes'] * math.exp(om['kdes'] * z[3])
    return p, weight


def simulate_scenario(extract, covariates, settings, trials, seed):
    om = v1._omegas(extract, settings.get('omega', 'exact'))
    first_h = settings.get('first_h', 7.0)
    rng = random.Random(seed)
    means = {e[0]: [] for e in v1.ENDPOINTS}
    for _ in range(trials):
        for group, (dose, n) in v1.GROUPS.items():
            cov = covariates[STUDY_OF_GROUP[group]]
            vals = {'cmax': [], 'auc_inf': [], 'auc_0_7d': []}
            for i in range(n):
                p, wt = draw_patient(rng, extract, settings, om, cov)
                if group == 'sirius_8':
                    r = v1.first_dose(p, wt, dose, first_h, auc_inf=i < 15)
                    if i < 15:
                        vals['auc_inf'].append(r['auc_inf'])
                elif group == 'gen501_16':
                    r = v1.first_dose(p, wt, dose, first_h, horizon_h=168.0)
                    if i < 20:
                        vals['auc_0_7d'].append(r['auc_0_7d'])
                else:
                    r = v1.first_dose(p, wt, dose, first_h)
                vals['cmax'].append(r['cmax'])
            for eid, g, _, metric, *_ in v1.ENDPOINTS:
                if g == group:
                    means[eid].append(math.fsum(vals[metric]) / len(vals[metric]))
    return means


def run_check(trials=None):
    plan = load_plan()
    extract, observed, supplement = load_inputs(plan)
    if list(v1.SCENARIOS) != plan['comparison']['scenarios']:
        raise ValueError('Scenario list differs from the plan.')
    covariates = study_covariates(supplement)
    trials = trials or plan['simulation']['virtual_trials']
    seed = plan['simulation']['seed']
    checks = v1.numerical_checks(extract)
    if not (checks['mass_balance_pass'] and checks['step_halving_pass'] and checks['linear_auc_pass']):
        raise ValueError('Numerical checks failed; no comparison was run.')
    scenarios = {}
    for index, (name, settings) in enumerate(v1.SCENARIOS.items()):
        means = simulate_scenario(extract, covariates, settings, trials, seed + index)
        rows = []
        for eid, group, dose, metric, n, path, kind in v1.ENDPOINTS:
            obs = v1.observed_value(observed, path)
            sim = v1._summary(means[eid])
            rows.append({'endpoint': eid, 'kind': kind, 'dose_mg_kg': dose, 'n': n, 'observed_mean': obs['mean'], 'observed_sd': obs['sd'],
                         'simulated_group_mean': sim, 'classification': v1._classify(obs['mean'], sim),
                         'observed_over_median': obs['mean'] / sim['p50']})
        scenarios[name] = {'settings': settings, 'endpoints': rows}
    by_endpoint = {}
    for eid, *_, kind in v1.ENDPOINTS:
        per = {name: next(r for r in s['endpoints'] if r['endpoint'] == eid)['classification'] for name, s in scenarios.items()}
        by_endpoint[eid] = {'kind': kind, 'primary': per['primary'], 'across_scenarios': sorted(set(per.values())),
                            'robust': len(set(per.values())) == 1, 'by_scenario': per}
    primary_ok = all(v['primary'] == 'consistent' for v in by_endpoint.values() if v['kind'] == 'primary')
    primary_robust = all(v['robust'] for v in by_endpoint.values() if v['kind'] == 'primary')
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'model_version': model.MODEL_VERSION,
              'plan_version': plan['plan_version'], 'plan_sha256': PLAN_SHA256, 'plan_locked_in_commit': PLAN_COMMIT,
              'v1_plan_sha256': v1.PLAN_SHA256, 'model_extract_sha256': plan['data']['model_extract']['sha256'],
              'observed_sha256': plan['data']['observed']['sha256'], 'supplement_sha256': plan['data']['supplement']['sha256'],
              'trials': trials, 'seed': seed, 'study_covariates': covariates,
              'classification': plan['classification'], 'independence': plan['independence'], 'not_this': copy.deepcopy(plan['not_this']),
              'numerical_checks': checks, 'classification_by_endpoint': by_endpoint,
              'decision': {'consistent_with_first_dose_iv_exposure': primary_ok, 'robust': primary_robust,
                           'registration_may_be_proposed': primary_ok and primary_robust},
              'scenarios': scenarios, 'known_differences': copy.deepcopy(plan['known_differences']),
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_daratumumab_pk_luo_check_v2_commands(app):
    @app.cli.command('daratumumab-pk-luo-check-v2')
    @click.option('--trials', type=click.IntRange(10, 100000), help='Override the plan (for quick looks only).')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(trials, output):
        """Run the second locked Luo 2021 daratumumab check, with study demographics (Simulation 3.2c)."""
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
