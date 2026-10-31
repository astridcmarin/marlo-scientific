"""Lenalidomide renal recheck: Hughes 2019 and Kim 2026 against CC-5013-PK-001 with study-matched virtual subjects.

Executes lenalidomide_renal_recheck_plan_v1.json (locked at commit d163781, before computation). Compared with the
v1 checks, only the construction of virtual subjects changes: sex counts, age and weight ranges and measured
creatinine clearance come from Chen et al. 2007 Table I, and clearance ranges from the 2008 label, both pinned in the
reconciliation v3 file. Same observed means, classification rule and trial size. Exploratory; not validation.
"""
import copy
import json
import math
import random
from pathlib import Path

import click

from .covariate_estimation import (VARIABILITY_SHA256, body_surface_area_du_bois, egfr_ckd_epi_2021,
                                   fat_free_mass_janmahasatian, load_variability_extract)
from .kim_model import EXTRACT_SHA256 as KIM_SHA256, disposition_rates, load_extract, typical_parameters
from .kim_renal_group_check import backsolve_serum_creatinine
from .patient_state import digest
from .pk_parameter_reference import EXTRACT_SHA256 as HUGHES_SHA256, load_parameter_extract
from .renal_group_check import GROUPS, _classify, _pinned, _summary, load_observed

ROOT = Path(__file__).resolve().parent.parent
PLAN_PATH = Path(__file__).parent / 'data' / 'lenalidomide_renal_recheck_plan_v1.json'
PLAN_SHA256 = '1766ddb3c353602a6892f69b6308155acbfd531d3971dd54d0656ea5dcee0a42'
REPORT_PATH = ROOT / 'docs' / 'verification' / 'lenalidomide_renal_recheck_v1.json'
SCHEMA_VERSION = 'lenalidomide-renal-recheck-report-v1'
METHOD_VERSION = 'lenalidomide-renal-recheck-v1.0'
HEIGHTS = {'primary': {'MALE': (165, 185), 'FEMALE': (152, 172)}, 'shorter': {'MALE': (155, 175), 'FEMALE': (142, 162)}}
RANGE_KEY = {'normal': 'normal_healthy', 'mild': 'mild', 'moderate': 'moderate', 'severe': 'severe'}
V1_PRIMARY = {'lenalidomide_hughes_2019': {'mild': 'consistent', 'moderate': 'model_under_predicts', 'severe': 'model_under_predicts'},
              'lenalidomide_kim_2026': {'mild': 'consistent', 'moderate': 'consistent', 'severe': 'model_under_predicts'}}
V1_REPORTS = {'lenalidomide_hughes_2019': 'docs/verification/hughes_renal_group_check_v1.json',
              'lenalidomide_kim_2026': 'docs/verification/kim_renal_group_check_v1.json'}


def load_plan(path=PLAN_PATH):
    return _pinned(path, PLAN_SHA256, 'Recheck plan')


def load_demographics(plan):
    src = plan['demographic_source']
    rec = _pinned(ROOT / src['file'], src['sha256'], 'Reconciliation v3')
    t1, ranges = rec['sources']['chen_2007']['table_I_demographics'], rec['sources']['label_2008']['study_crcl_ranges_ml_min']
    lock = src['values_at_lock']
    if ranges != lock['observed_crcl_ranges']:
        raise ValueError('Observed clearance ranges differ from the values recorded when the plan was locked.')
    out = {}
    for g in GROUPS:
        if t1[g] != lock['table_I'][g]:
            raise ValueError('Table I differs from the values recorded when the plan was locked.')
        out[g] = dict(t1[g], crcl_range=ranges[RANGE_KEY[g]])
    return out


def _crcl(rng, d, uniform):
    lo, hi = d['crcl_range']
    if uniform:
        return rng.uniform(lo, hi)
    while True:
        x = rng.gauss(d['crcl_ml_min_mean'], d['crcl_sd'])
        if lo <= x <= hi:
            return x


def draw_group(rng, d, scenario):
    """Subjects of one group: exact sex counts; per subject crcl, age, weight, height, z1, z2 (plan order)."""
    sexes = ['FEMALE'] * d['female_male'][0] + ['MALE'] * d['female_male'][1]
    heights = HEIGHTS['shorter' if scenario == 'sensitivity_shorter' else 'primary']
    out = []
    for sex in sexes:
        crcl = _crcl(rng, d, scenario == 'sensitivity_uniform_crcl')
        age = rng.uniform(*d['age_range'])
        weight = rng.uniform(*d['weight_kg_range'])
        height = rng.uniform(*heights[sex])
        z1, z2 = rng.gauss(0, 1), rng.gauss(0, 1)
        out.append({'sex': sex, 'crcl': crcl, 'age': age, 'weight': weight, 'height': height, 'z1': z1, 'z2': z2})
    return out


def hughes_auc(s, p, chol, dose):
    l11, l21, l22 = chol
    ffm = fat_free_mass_janmahasatian(s['weight'], s['height'], s['sex'])
    eta_cl = l11 * s['z1']
    cl = (p['apparent_clearance'] * (ffm / p['reference_ffm']) ** p['ffm_clearance_exponent']
          * (s['crcl'] / p['reference_crcl']) ** p['crcl_exponent'] * math.exp(eta_cl))
    return 1000.0 * dose / cl, {'ffm': ffm}


def kim_auc(s, extract, cl_form, sd, dose):
    scr = backsolve_serum_creatinine(s['crcl'], s['age'], s['weight'], s['sex'])
    egfr, bsa = egfr_ckd_epi_2021(s['age'], scr, s['sex']), body_surface_area_du_bois(s['weight'], s['height'])
    params = typical_parameters(egfr, bsa, cl_form, extract)
    total_cl = params['unbound_clearance_l_h'] * math.exp(sd['cl'] * s['z1']) * params['fraction_unbound']
    return 1000.0 * dose / total_cl, {'scr_umol_l': scr, 'egfr': egfr, 'bsa': bsa}


def _dist(values):
    s = sorted(values)
    return {'min': s[0], 'median': _summary(s)['p50'], 'max': s[-1]}


def simulate(plan, scenario, models, demo, observed, trials, seed):
    rng = random.Random(seed)
    dose = plan['virtual_trial']['dose_mg']
    hp = {k: v['value'] for k, v in load_parameter_extract()['parameters'].items()}
    om = load_variability_extract()['random_effects']['omega_matrix']
    l11 = math.sqrt(om[0][0]); l21 = om[0][1] / l11; l22 = math.sqrt(om[1][1] - l21 ** 2)
    kx = load_extract()
    ksd = {'cl': kx['random_effects']['reported']['cl_pct_cv'] / 100.0}
    ranges = kx['study_population']['ranges_table1']
    cl_form = 'exponential' if scenario == 'sensitivity_kim_exponential' else 'linear_multiplicative'
    means = {m: {g: [] for g in GROUPS} for m in models}
    cov = {m: {g: {} for g in GROUPS} for m in models}
    for _ in range(trials):
        for g in GROUPS:
            subjects = draw_group(rng, demo[g], scenario)
            for m in models:
                aucs = []
                for s in subjects:
                    auc, c = hughes_auc(s, hp, (l11, l21, l22), dose) if m == 'lenalidomide_hughes_2019' else kim_auc(s, kx, cl_form, ksd, dose)
                    aucs.append(auc)
                    for k, v in c.items():
                        cov[m][g].setdefault(k, []).append(v)
                means[m][g].append(math.fsum(aucs) / len(aucs))
    out = {}
    for m in models:
        rows = []
        for g in GROUPS:
            obs = observed[g]
            auc = _summary(means[m][g])
            row = {'group': g, 'n': obs['n'], 'auc_infinity': {'observed_mean': obs['auc_infinity_mean'], 'simulated_group_mean': auc,
                   'classification': _classify(obs['auc_infinity_mean'], auc), 'observed_over_median': obs['auc_infinity_mean'] / auc['p50']},
                   'constructed_covariates': {k: _dist(v) for k, v in cov[m][g].items()}}
            if m == 'lenalidomide_kim_2026':
                eg = cov[m][g]['egfr']
                row['constructed_covariates']['fraction_egfr_outside_kim_range'] = sum(
                    not ranges['egfr_ml_min_1_73m2'][0] <= v <= ranges['egfr_ml_min_1_73m2'][1] for v in eg) / len(eg)
            if g != 'normal':
                r = _summary([a / b for a, b in zip(means[m][g], means[m]['normal'])])
                o = obs['auc_infinity_mean'] / observed['normal']['auc_infinity_mean']
                row['auc_ratio_to_normal'] = {'observed': o, 'simulated': r, 'classification': _classify(o, r), 'observed_over_median': o / r['p50']}
            rows.append(row)
        out[m] = rows
    return out


def run_check(trials=None, seed=None):
    plan = load_plan()
    demo = load_demographics(plan)
    observed = load_observed({'observed_data': plan['observed_data']})
    trials = trials or plan['virtual_trial']['trials']
    seed = plan['virtual_trial']['seed'] if seed is None else seed
    scenarios = {}
    for i, name in enumerate(plan['scenarios']):
        models = ('lenalidomide_kim_2026',) if name == 'sensitivity_kim_exponential' else tuple(V1_PRIMARY)
        scenarios[name] = simulate(plan, name, models, demo, observed, trials, seed + i)
    result = {}
    for m in V1_PRIMARY:
        primary = {r['group']: r['auc_ratio_to_normal']['classification'] for r in scenarios['primary'][m] if 'auc_ratio_to_normal' in r}
        across = {g: sorted({next(r for r in s[m] if r['group'] == g)['auc_ratio_to_normal']['classification']
                             for s in scenarios.values() if m in s}) for g in primary}
        result[m] = {'primary': primary, 'across_scenarios': across, 'v1_primary': V1_PRIMARY[m], 'v1_report': V1_REPORTS[m],
                     'change_from_v1': {g: ('unchanged' if primary[g] == V1_PRIMARY[m][g] else 'changed') for g in primary}}
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'plan_locked_at_commit': 'd163781', 'observed_data_sha256': plan['observed_data']['sha256'],
              'demographic_source_sha256': plan['demographic_source']['sha256'], 'hughes_extract_sha256': HUGHES_SHA256,
              'hughes_variability_sha256': VARIABILITY_SHA256, 'kim_extract_sha256': KIM_SHA256, 'trials': trials, 'seed': seed,
              'classification': plan['classification'], 'result_by_model': result, 'scenarios': scenarios,
              'decision_rule': plan['decision_rule']['summary'], 'not_this': copy.deepcopy(plan['not_this']),
              'known_differences': copy.deepcopy(plan['known_differences']), 'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_renal_recheck_commands(app):
    @app.cli.command('lenalidomide-renal-recheck')
    @click.option('--trials', type=click.IntRange(100, 100000), help='Override the plan (for quick looks only).')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(trials, output):
        """Run the locked lenalidomide renal recheck (Hughes and Kim, study-matched subjects). Exploratory; not validation."""
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
