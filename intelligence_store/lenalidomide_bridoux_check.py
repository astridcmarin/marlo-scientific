"""Lenalidomide Hughes 2019 and Kim 2026 against Bridoux 2016 (myeloma with renal impairment): the locked check (2.1h).

Stage 1 (4 November 2026): the observed design, read from the methods and Table 1 only, pinned here before any
exposure value is used. Stage 2 adds the observed exposure values and the virtual trial under the plan locked on
31 October 2026 (lenalidomide_bridoux_check_plan_v1.json). The stage 1 file records one deviation: part of the
Results text was seen while locating Table 1 (see its 'deviation' entry).
"""
import hashlib
import json
from pathlib import Path

DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'lenalidomide_bridoux_check_plan_v1.json'
DESIGN_PATH = DATA / 'lenalidomide_bridoux_design_v1.json'
DESIGN_SHA256 = '1af2d005528a18088382225482a3eaa32ac3c68f4f6529c5ee7958e8c1605eac'
OBSERVED_PATH = DATA / 'lenalidomide_bridoux_observed_v1.json'
OBSERVED_SHA256 = 'b757b38d84788fe7587d7b7a5a737d464928a0b24f7eead517a74b732845b89e'
# v2 adds Cmax and t1/2 from the same Table 2 for the Digital human 1.1d time-course check; the 2.1h check uses v1.
OBSERVED_V2_PATH = DATA / 'lenalidomide_bridoux_observed_v2.json'
OBSERVED_V2_SHA256 = 'cc8c41123d6305dd3ab783ae53e87d0ab8c15f32f04b21cc45d4c9a2bc4de8ee'


def load_design(path=DESIGN_PATH):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != DESIGN_SHA256:
        raise ValueError('Bridoux observed-design file is missing or changed.')
    data = json.loads(raw)
    if data.get('schema_version') != 'observed-design-v1':
        raise ValueError('Unsupported observed-design schema.')
    return data


def load_observed(path=OBSERVED_PATH):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != OBSERVED_SHA256:
        raise ValueError('Bridoux observed-exposure file is missing or changed.')
    data = json.loads(raw)
    if data.get('schema_version') != 'observed-group-exposure-v1':
        raise ValueError('Unsupported observed-exposure schema.')
    return data



def load_observed_v2(path=OBSERVED_V2_PATH):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != OBSERVED_V2_SHA256:
        raise ValueError('Bridoux observed-exposure file v2 is missing or changed.')
    data = json.loads(raw)
    if data.get('schema_version') != 'observed-group-exposure-v1':
        raise ValueError('Unsupported observed-exposure schema.')
    return data

# ---------------------------------------------------------------- the virtual trial (stage 2, after both files above)
import copy  # noqa: E402
import math  # noqa: E402
import random  # noqa: E402

from .covariate_estimation import (VARIABILITY_SHA256, body_surface_area_du_bois, egfr_ckd_epi_2021,  # noqa: E402
                                   ideal_body_weight_devine, load_variability_extract)
from .kim_model import EXTRACT_SHA256 as KIM_SHA256, load_extract, typical_parameters  # noqa: E402
from .kim_renal_group_check import backsolve_serum_creatinine  # noqa: E402
from .patient_state import digest  # noqa: E402
from .pk_parameter_reference import EXTRACT_SHA256 as HUGHES_SHA256, load_parameter_extract  # noqa: E402
from .renal_group_check import _classify, _summary  # noqa: E402
from .renal_group_recheck import hughes_auc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PLAN_SHA256 = '7cf4070eb2d979404e8bba5650817b3b93a28bc41438654c7aaa66cafa10e329'
REPORT_PATH = ROOT / 'docs' / 'verification' / 'lenalidomide_bridoux_check_v1.json'
SCHEMA_VERSION = 'lenalidomide-bridoux-check-report-v1'
METHOD_VERSION = 'lenalidomide-bridoux-check-v1.0'
SIMULATED = ('normal', 'mild', 'moderate', 'severe')
# The plan's fallback when the study reports no range: uniform over (or truncation to) the group definition.
GROUP_RANGE = {'normal': (80.0, 140.0), 'mild': (50.0, 80.0), 'moderate': (30.0, 50.0), 'severe': (10.0, 30.0)}
WEIGHT_FALLBACK = (55.0, 95.0)
HEIGHTS = {'primary': {'MALE': (165, 185), 'FEMALE': (152, 172)}, 'shorter': {'MALE': (155, 175), 'FEMALE': (142, 162)}}
MODELS = ('lenalidomide_hughes_2019', 'lenalidomide_kim_2026')
STEADY_STATE_NOTE = ('AUC24 on day 5 is taken as the steady-state AUC over 24 h, dose per 24 h / CL/F (exact for linear '
                     'kinetics at steady state). With the observed half-lives (3-10 h), the dose given on day 5 is at least '
                     'the third dose 48 h apart (severe) or the fifth 24 h apart (others); the shortfall from steady state '
                     'is below 0.01% for a one-compartment terminal phase.')


def load_plan(path=PLAN_PATH):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError('Bridoux check plan is missing or changed.')
    plan = json.loads(raw)
    if plan.get('status') != 'locked_before_observed_values':
        raise ValueError('The Bridoux check plan is not locked.')
    return plan


def demographics(design):
    g = design['design']['per_group']
    return {k: {'female_male': [g['male_female'][k][1], g['male_female'][k][0]],
                'age_range': g['age_median_range_years'][k][1:],
                'crcl_mean_sd': g['crcl_mean_sd_ml_min'][k], 'crcl_range': GROUP_RANGE[k]} for k in SIMULATED}


def _crcl(rng, d, uniform):
    lo, hi = d['crcl_range']
    if uniform:
        return rng.uniform(lo, hi)
    mean, sd = d['crcl_mean_sd']
    while True:
        x = rng.gauss(mean, sd)
        if lo <= x <= hi:
            return x


def draw_group(rng, d, scenario):
    """Exact sex counts (women first); per subject in the plan's order: crcl, age, weight, height, z1, z2."""
    sexes = ['FEMALE'] * d['female_male'][0] + ['MALE'] * d['female_male'][1]
    heights = HEIGHTS['shorter' if scenario == 'sensitivity_shorter' else 'primary']
    out = []
    for sex in sexes:
        crcl = _crcl(rng, d, scenario == 'sensitivity_uniform_crcl')
        age = rng.uniform(*d['age_range'])
        weight = rng.uniform(*WEIGHT_FALLBACK)
        height = rng.uniform(*heights[sex])
        z1, z2 = rng.gauss(0, 1), rng.gauss(0, 1)
        out.append({'sex': sex, 'crcl': crcl, 'age': age, 'weight': weight, 'height': height, 'z1': z1, 'z2': z2})
    return out


def kim_auc(s, extract, cl_form, sd, dose, ideal_weight_basis=False):
    weight_for_cg = ideal_body_weight_devine(s['height'], s['sex']) if ideal_weight_basis else s['weight']
    scr = backsolve_serum_creatinine(s['crcl'], s['age'], weight_for_cg, s['sex'])
    egfr, bsa = egfr_ckd_epi_2021(s['age'], scr, s['sex']), body_surface_area_du_bois(s['weight'], s['height'])
    params = typical_parameters(egfr, bsa, cl_form, extract)
    total_cl = params['unbound_clearance_l_h'] * math.exp(sd['cl'] * s['z1']) * params['fraction_unbound']
    return 1000.0 * dose / total_cl, {'scr_umol_l': scr, 'egfr': egfr, 'bsa': bsa}


def _gm(values):
    return math.exp(math.fsum(math.log(v) for v in values) / len(values))


def _dist(values):
    s = sorted(values)
    return {'min': s[0], 'median': _summary(s)['p50'], 'max': s[-1]}


def simulate(scenario, models, demo, observed, trials, seed):
    rng = random.Random(seed)
    hp = {k: v['value'] for k, v in load_parameter_extract()['parameters'].items()}
    om = load_variability_extract()['random_effects']['omega_matrix']
    l11 = math.sqrt(om[0][0]); l21 = om[0][1] / l11; l22 = math.sqrt(om[1][1] - l21 ** 2)
    kx = load_extract()
    ksd = {'cl': kx['random_effects']['reported']['cl_pct_cv'] / 100.0}
    egfr_range = kx['study_population']['ranges_table1']['egfr_ml_min_1_73m2']
    cl_form = 'exponential' if scenario == 'sensitivity_kim_exponential' else 'linear_multiplicative'
    ideal = scenario == 'sensitivity_ideal_weight_basis'
    obs = observed['groups']
    dn = {m: {g: [] for g in SIMULATED} for m in models}
    cov = {m: {g: {} for g in SIMULATED} for m in models}
    for _ in range(trials):
        for g in SIMULATED:
            subjects = draw_group(rng, demo[g], scenario)
            dose = obs[g]['dose_mg_per_24h']
            for m in models:
                aucs = []
                for s in subjects:
                    if m == 'lenalidomide_hughes_2019':
                        auc, c = hughes_auc(s, hp, (l11, l21, l22), dose)
                    else:
                        auc, c = kim_auc(s, kx, cl_form, ksd, dose, ideal)
                    aucs.append(auc)
                    for k, v in c.items():
                        cov[m][g].setdefault(k, []).append(v)
                dn[m][g].append(_gm(aucs) / dose)
    out = {}
    for m in models:
        rows = []
        for g in SIMULATED:
            o_dn = obs[g]['auc24_gm'] / obs[g]['dose_mg_per_24h']
            sim = _summary(dn[m][g])
            row = {'group': g, 'n': obs[g]['n'], 'dose_mg_per_24h': obs[g]['dose_mg_per_24h'],
                   'dose_normalised_auc24': {'observed_gm_per_mg': o_dn, 'simulated_gm_per_mg': sim,
                                             'classification': _classify(o_dn, sim), 'observed_over_median': o_dn / sim['p50']},
                   'constructed_covariates': {k: _dist(v) for k, v in cov[m][g].items()}}
            if m == 'lenalidomide_kim_2026':
                eg = cov[m][g]['egfr']
                row['constructed_covariates']['fraction_egfr_outside_kim_range'] = sum(
                    not egfr_range[0] <= v <= egfr_range[1] for v in eg) / len(eg)
            if g != 'normal':
                ratio = _summary([a / b for a, b in zip(dn[m][g], dn[m]['normal'])])
                o = o_dn / (obs['normal']['auc24_gm'] / obs['normal']['dose_mg_per_24h'])
                row['dose_normalised_ratio_to_normal'] = {'observed': o, 'simulated': ratio, 'classification': _classify(o, ratio),
                                                          'observed_over_median': o / ratio['p50']}
            rows.append(row)
        out[m] = rows
    return out


def run_check(trials=None, seed=None):
    plan, design, observed = load_plan(), load_design(), load_observed()
    ref = plan['pinned_inputs']['recheck_report']
    raw = (ROOT / ref['file']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref['sha256']:
        raise ValueError('The 2.1e recheck report pinned by the plan is missing or changed.')
    recheck = {m: v['primary'] for m, v in json.loads(raw)['result_by_model'].items()}
    if observed['design_file']['sha256'] != DESIGN_SHA256:
        raise ValueError('The observed values do not point at the pinned design file.')
    demo = demographics(design)
    trials = trials or plan['virtual_trial']['trials']
    seed = plan['virtual_trial']['seed'] if seed is None else seed
    scenarios = {}
    for i, name in enumerate(plan['scenarios']):
        models = ('lenalidomide_kim_2026',) if name in ('sensitivity_kim_exponential', 'sensitivity_ideal_weight_basis') else MODELS
        scenarios[name] = simulate(name, models, demo, observed, trials, seed + i)
    result = {}
    for m in MODELS:
        primary = {r['group']: r['dose_normalised_ratio_to_normal']['classification'] for r in scenarios['primary'][m]
                   if 'dose_normalised_ratio_to_normal' in r}
        across = {g: sorted({next(r for r in s[m] if r['group'] == g)['dose_normalised_ratio_to_normal']['classification']
                             for s in scenarios.values() if m in s}) for g in primary}
        result[m] = {'primary': primary, 'robust_across_scenarios': {g: len(v) == 1 for g, v in across.items()},
                     'across_scenarios': across, 'recheck_2_1e_primary': recheck[m],
                     'same_as_recheck': {g: primary[g] == recheck[m][g] for g in primary}}
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'design_sha256': DESIGN_SHA256, 'observed_sha256': OBSERVED_SHA256,
              'hughes_extract_sha256': HUGHES_SHA256, 'hughes_variability_sha256': VARIABILITY_SHA256, 'kim_extract_sha256': KIM_SHA256,
              'trials': trials, 'seed': seed, 'classification': plan['classification'],
              'classification_rule': plan['classification_rule'],
              'endpoint': 'Dose-normalised AUC24 (geometric mean per mg of daily dose), each impaired group relative to normal.',
              'steady_state_note': STEADY_STATE_NOTE,
              'fallbacks_applied': design['fallbacks_triggered_by_the_locked_plan'],
              'deviation_recorded_at_stage_1': design['deviation']['what'],
              'esrd_observed_not_simulated': observed['groups']['esrd'],
              'result_by_model': result, 'scenarios': scenarios, 'decision_rule': plan['decision_rule']['summary'],
              'known_differences': copy.deepcopy(plan['known_differences']), 'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report
