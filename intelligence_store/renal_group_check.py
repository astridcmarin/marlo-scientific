"""Patient Lab 2.0g: aggregate consistency check of the Hughes model against renal-group data.

Executes the locked plan in hughes_renal_group_check_plan_v1.json: simulate the CC-5013-PK-001
design (single 25 mg dose, reported group sizes and creatinine-clearance ranges) many times under
the Hughes model with its between-subject variability, and ask whether each observed group mean
falls within the simulated range. Exploratory; not validation and not an acceptance decision.
"""
import copy
import hashlib
import json
import math
import random
from pathlib import Path

import click

from .patient_state import digest
from .pk_parameter_reference import load_parameter_extract, EXTRACT_SHA256
from .covariate_estimation import load_variability_extract, VARIABILITY_SHA256

SCHEMA_VERSION = 'hughes-renal-group-check-report-v1'
METHOD_VERSION = 'hughes-renal-group-check-v1.0'
ROOT = Path(__file__).resolve().parent.parent
PLAN_PATH = Path(__file__).parent / 'data' / 'hughes_renal_group_check_plan_v1.json'
PLAN_SHA256 = '8f733d98aa4e155dd8ab50d97c00d54d481ac09daa04dd6d3dd6c450e863ca97'
GROUPS = ('normal', 'mild', 'moderate', 'severe')
EVIDENCE_GROUP = {'normal': 'normal', 'mild': 'mild', 'moderate': 'moderate', 'severe': 'severe_without_dialysis'}
PERCENTILES = (5, 50, 95)


def _pinned(path, sha, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError(f'{label} is missing or changed; no check was run.')
    return json.loads(raw)


def load_plan(path=PLAN_PATH):
    return _pinned(path, PLAN_SHA256, 'Analysis plan')


def load_observed(plan):
    evidence = _pinned(ROOT / plan['observed_data']['file'], plan['observed_data']['sha256'], 'Renal group evidence')
    by_name = {g['group']: g for g in evidence['groups']}
    observed = {}
    for group in GROUPS:
        row = by_name[EVIDENCE_GROUP[group]]
        m = row['measurements']
        observed[group] = {'n': row['n'], 'auc_infinity_mean': m['auc_infinity']['mean'], 'auc_infinity_sd': m['auc_infinity']['sd'],
                           'half_life_mean': m['terminal_half_life']['mean'], 'half_life_sd': m['terminal_half_life']['sd'],
                           'source_crcl_range': row['crcl_range']}
    return observed


def _percentile(values, q):
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q / 100.0
    lo = math.floor(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def _summary(values):
    return {f'p{q:02d}': _percentile(values, q) for q in PERCENTILES}


def _classify(observed, summary):
    if observed > summary['p95']:
        return 'model_under_predicts'
    if observed < summary['p05']:
        return 'model_over_predicts'
    return 'consistent'


def _scenario(plan, name):
    primary = plan['scenarios']['primary']
    spec = plan['scenarios'][name]
    return {'crcl_ml_min': spec.get('crcl_ml_min', primary['crcl_ml_min']), 'ffm_kg': spec.get('ffm_kg', primary['ffm_kg'])}


def simulate_scenario(plan, scenario, observed, parameters, omega, trials, seed):
    p = {k: v['value'] for k, v in parameters.items()}
    l11 = math.sqrt(omega[0][0])
    l21 = omega[0][1] / l11
    l22 = math.sqrt(omega[1][1] - l21 ** 2)
    dose = plan['virtual_trial']['dose_mg']
    rng = random.Random(seed)
    auc_means = {g: [] for g in GROUPS}
    half_means = {g: [] for g in GROUPS}
    for _ in range(trials):
        for group in GROUPS:
            lo, hi = scenario['crcl_ml_min'][group]
            f_lo, f_hi = scenario['ffm_kg']
            aucs, halves = [], []
            for _ in range(observed[group]['n']):
                crcl = rng.uniform(lo, hi)
                ffm = rng.uniform(f_lo, f_hi)
                z1, z2 = rng.gauss(0, 1), rng.gauss(0, 1)
                eta_cl, eta_v = l11 * z1, l21 * z1 + l22 * z2
                cl = (p['apparent_clearance'] * (ffm / p['reference_ffm']) ** p['ffm_clearance_exponent']
                      * (crcl / p['reference_crcl']) ** p['crcl_exponent'] * math.exp(eta_cl))
                v = p['apparent_volume'] * (ffm / p['reference_ffm']) ** p['ffm_volume_exponent'] * math.exp(eta_v)
                aucs.append(1000.0 * dose / cl)
                halves.append(math.log(2) * v / cl)
            auc_means[group].append(math.fsum(aucs) / len(aucs))
            half_means[group].append(math.fsum(halves) / len(halves))
    rows = []
    for group in GROUPS:
        obs = observed[group]
        auc = _summary(auc_means[group])
        half = _summary(half_means[group])
        row = {'group': group, 'n': obs['n'], 'crcl_range_simulated': scenario['crcl_ml_min'][group],
               'auc_infinity': {'observed_mean': obs['auc_infinity_mean'], 'simulated_group_mean': auc,
                                'classification': _classify(obs['auc_infinity_mean'], auc),
                                'observed_over_median': obs['auc_infinity_mean'] / auc['p50']},
               'half_life': {'observed_mean': obs['half_life_mean'], 'simulated_group_mean': half,
                             'observed_over_median': obs['half_life_mean'] / half['p50']}}
        if group != 'normal':
            ratios = [a / b for a, b in zip(auc_means[group], auc_means['normal'])]
            ratio = _summary(ratios)
            observed_ratio = obs['auc_infinity_mean'] / observed['normal']['auc_infinity_mean']
            row['auc_ratio_to_normal'] = {'observed': observed_ratio, 'simulated': ratio,
                                          'classification': _classify(observed_ratio, ratio),
                                          'observed_over_median': observed_ratio / ratio['p50']}
        rows.append(row)
    return rows


def run_check(trials=None, seed=None):
    plan = load_plan()
    observed = load_observed(plan)
    parameters = load_parameter_extract()['parameters']
    omega = load_variability_extract()['random_effects']['omega_matrix']
    trials = trials or plan['virtual_trial']['trials']
    seed = plan['virtual_trial']['seed'] if seed is None else seed
    scenarios = {}
    for index, name in enumerate(plan['scenarios']):
        scenarios[name] = {'settings': _scenario(plan, name),
                           'groups': simulate_scenario(plan, _scenario(plan, name), observed, parameters, omega, trials, seed + index)}
    primary = scenarios['primary']['groups']
    headline = {row['group']: row['auc_ratio_to_normal']['classification'] for row in primary if 'auc_ratio_to_normal' in row}
    robust = {g: sorted({next(r for r in s['groups'] if r['group'] == g)['auc_ratio_to_normal']['classification']
                         for s in scenarios.values()}) for g in headline}
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION,
              'plan_version': plan['plan_version'], 'plan_sha256': PLAN_SHA256,
              'observed_data_sha256': plan['observed_data']['sha256'], 'parameter_extract_sha256': EXTRACT_SHA256,
              'variability_extract_sha256': VARIABILITY_SHA256, 'trials': trials, 'seed': seed,
              'classification': plan['classification'], 'not_this': copy.deepcopy(plan['not_this']),
              'primary_endpoint_by_group': headline, 'classification_across_scenarios': robust,
              'scenarios': scenarios, 'known_differences': copy.deepcopy(plan['known_differences']),
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_renal_group_check_commands(app):
    @app.cli.command('hughes-renal-group-check')
    @click.option('--trials', type=click.IntRange(100, 100000), help='Override the plan (for quick looks only).')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(trials, output):
        """Run the locked Hughes renal-group consistency check. Exploratory; not validation."""
        try:
            report = run_check(trials=trials)
        except (ValueError, OSError, KeyError) as exc:
            raise click.ClickException(str(exc)) from exc
        payload = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
        if output:
            with output.open('x', encoding='utf-8') as handle:
                handle.write(payload)
            click.echo(f'Saved report: {output}\nReport SHA256: {report["report_sha256"]}')
        else:
            click.echo(payload, nl=False)
