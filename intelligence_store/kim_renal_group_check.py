"""Patient Lab 2.1c: aggregate consistency check of the Kim 2026 model against renal-group data.

Executes the locked plan in kim_renal_group_check_plan_v1.json. The renal study (CC-5013-PK-001)
reports creatinine-clearance ranges only, while Kim needs CKD-EPI 2021 eGFR and Du Bois BSA, so each
virtual subject gets assumed demographics and a serum creatinine back-solved from Cockcroft-Gault;
eGFR and BSA then follow from the same subject. Exploratory; not validation and not an acceptance decision.
"""
import copy
import json
import math
import random
from pathlib import Path

import click

from .patient_state import digest
from .covariate_estimation import (CREATININE_UMOL_PER_MG_DL, CG_FEMALE_FACTOR, REGISTRY_SHA256,
                                   body_surface_area_du_bois, cockcroft_gault, egfr_ckd_epi_2021,
                                   ideal_body_weight_devine)
from .kim_model import EXTRACT_SHA256, FORM_ASSESSMENT_SHA256, disposition_rates, load_extract, typical_parameters
from .renal_group_check import GROUPS, _classify, _pinned, _summary, load_observed

SCHEMA_VERSION = 'kim-renal-group-check-report-v1'
METHOD_VERSION = 'kim-renal-group-check-v1.0'
PLAN_PATH = Path(__file__).parent / 'data' / 'kim_renal_group_check_plan_v1.json'
PLAN_SHA256 = 'a15179d0d7b366b59841a7333adc4547a7bbded4610f43b59488d8598a206bb8'
SCENARIO_KEYS = ('crcl_ml_min', 'cockcroft_gault_weight_basis', 'age_years', 'male_fraction', 'weight_kg',
                 'height_cm', 'cl_form')
BACKSOLVE_TOLERANCE = 1e-9


def load_plan(path=PLAN_PATH):
    return _pinned(path, PLAN_SHA256, 'Analysis plan')


def scenario_settings(plan, name):
    """Primary settings overridden only by the keys a sensitivity scenario lists."""
    primary = plan['scenarios']['primary']
    spec = plan['scenarios'][name]
    return {key: copy.deepcopy(spec.get(key, primary[key])) for key in SCENARIO_KEYS}


def dosing_weight(basis, weight, height, sex):
    if basis == 'total_body_weight':
        return weight
    if basis == 'ideal_body_weight_devine':
        return ideal_body_weight_devine(height, sex)
    raise ValueError(f'Unsupported weight basis in plan: {basis}')


def backsolve_serum_creatinine(crcl, age, weight_for_cg, sex):
    """Serum creatinine (umol/L) at which Cockcroft-Gault returns `crcl`; checked by recomputation."""
    scr_mg_dl = (140.0 - age) * weight_for_cg * (CG_FEMALE_FACTOR if sex == 'FEMALE' else 1.0) / (72.0 * crcl)
    scr = scr_mg_dl * CREATININE_UMOL_PER_MG_DL
    recomputed = cockcroft_gault(age, weight_for_cg, scr, sex)
    if abs(recomputed - crcl) > BACKSOLVE_TOLERANCE * crcl:
        raise ValueError('Cockcroft-Gault back-solve did not reproduce the drawn creatinine clearance.')
    return scr


def draw_subject(rng, settings, group):
    """One virtual subject, drawing in the plan's fixed order: crcl, age, sex, weight, height, z_cl, z_v1."""
    lo, hi = settings['crcl_ml_min'][group]
    crcl = rng.uniform(lo, hi)
    age = rng.uniform(*settings['age_years'])
    sex = 'MALE' if rng.random() < settings['male_fraction'] else 'FEMALE'
    weight = rng.uniform(*settings['weight_kg'])
    height = rng.uniform(*settings['height_cm'][sex])
    z_cl, z_v1 = rng.gauss(0, 1), rng.gauss(0, 1)
    scr = backsolve_serum_creatinine(crcl, age, dosing_weight(settings['cockcroft_gault_weight_basis'], weight, height, sex), sex)
    return {'crcl': crcl, 'age': age, 'sex': sex, 'weight': weight, 'height': height, 'scr_umol_l': scr,
            'egfr': egfr_ckd_epi_2021(age, scr, sex), 'bsa': body_surface_area_du_bois(weight, height),
            'z_cl': z_cl, 'z_v1': z_v1}


def subject_exposure(subject, cl_form, dose_mg, omega_sd, extract):
    params = typical_parameters(subject['egfr'], subject['bsa'], cl_form, extract)
    params['unbound_clearance_l_h'] *= math.exp(omega_sd['cl'] * subject['z_cl'])
    params['unbound_central_volume_l'] *= math.exp(omega_sd['v1'] * subject['z_v1'])
    total_cl = params['unbound_clearance_l_h'] * params['fraction_unbound']
    _, beta = disposition_rates(params)
    return 1000.0 * dose_mg / total_cl, math.log(2) / beta


def _distribution(values):
    ordered = sorted(values)
    return {'min': ordered[0], 'median': _summary(ordered)['p50'], 'max': ordered[-1]}


def simulate_scenario(plan, settings, observed, extract, trials, seed):
    dose = plan['virtual_trial']['dose_mg']
    ranges = extract['study_population']['ranges_table1']
    omega_sd = {'cl': extract['random_effects']['reported']['cl_pct_cv'] / 100.0,
                'v1': extract['random_effects']['reported']['v1_pct_cv'] / 100.0}
    rng = random.Random(seed)
    auc_means = {g: [] for g in GROUPS}
    half_means = {g: [] for g in GROUPS}
    covariates = {g: {'scr_umol_l': [], 'egfr': [], 'bsa': []} for g in GROUPS}
    for _ in range(trials):
        for group in GROUPS:
            aucs, halves = [], []
            for _ in range(observed[group]['n']):
                subject = draw_subject(rng, settings, group)
                auc, half = subject_exposure(subject, settings['cl_form'], dose, omega_sd, extract)
                aucs.append(auc)
                halves.append(half)
                for key in covariates[group]:
                    covariates[group][key].append(subject[key])
            auc_means[group].append(math.fsum(aucs) / len(aucs))
            half_means[group].append(math.fsum(halves) / len(halves))
    rows = []
    for group in GROUPS:
        obs = observed[group]
        auc, half = _summary(auc_means[group]), _summary(half_means[group])
        egfrs, bsas = covariates[group]['egfr'], covariates[group]['bsa']
        row = {'group': group, 'n': obs['n'], 'crcl_range_simulated': settings['crcl_ml_min'][group],
               'constructed_covariates': {
                   'serum_creatinine_umol_l': _distribution(covariates[group]['scr_umol_l']),
                   'egfr_ml_min_1_73m2': _distribution(egfrs), 'bsa_m2': _distribution(bsas),
                   'fraction_egfr_outside_kim_range': sum(not ranges['egfr_ml_min_1_73m2'][0] <= v <= ranges['egfr_ml_min_1_73m2'][1] for v in egfrs) / len(egfrs),
                   'fraction_bsa_outside_kim_range': sum(not ranges['bsa_m2'][0] <= v <= ranges['bsa_m2'][1] for v in bsas) / len(bsas)},
               'auc_infinity': {'observed_mean': obs['auc_infinity_mean'], 'simulated_group_mean': auc,
                                'classification': _classify(obs['auc_infinity_mean'], auc),
                                'observed_over_median': obs['auc_infinity_mean'] / auc['p50']},
               'half_life': {'observed_mean': obs['half_life_mean'], 'simulated_group_mean': half,
                             'observed_over_median': obs['half_life_mean'] / half['p50']}}
        if group != 'normal':
            ratio = _summary([a / b for a, b in zip(auc_means[group], auc_means['normal'])])
            observed_ratio = obs['auc_infinity_mean'] / observed['normal']['auc_infinity_mean']
            row['auc_ratio_to_normal'] = {'observed': observed_ratio, 'simulated': ratio,
                                          'classification': _classify(observed_ratio, ratio),
                                          'observed_over_median': observed_ratio / ratio['p50']}
        rows.append(row)
    return rows


def run_check(trials=None, seed=None):
    plan = load_plan()
    observed = load_observed(plan)
    extract = load_extract()
    trials = trials or plan['virtual_trial']['trials']
    seed = plan['virtual_trial']['seed'] if seed is None else seed
    scenarios = {}
    for index, name in enumerate(plan['scenarios']):
        settings = scenario_settings(plan, name)
        scenarios[name] = {'settings': settings,
                           'groups': simulate_scenario(plan, settings, observed, extract, trials, seed + index)}
    primary = scenarios['primary']['groups']
    headline = {row['group']: row['auc_ratio_to_normal']['classification'] for row in primary if 'auc_ratio_to_normal' in row}
    robust = {g: sorted({next(r for r in s['groups'] if r['group'] == g)['auc_ratio_to_normal']['classification']
                         for s in scenarios.values()}) for g in headline}
    absolute = {row['group']: row['auc_infinity']['classification'] for row in primary}
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION,
              'plan_version': plan['plan_version'], 'plan_sha256': PLAN_SHA256,
              'observed_data_sha256': plan['observed_data']['sha256'], 'kim_extract_sha256': EXTRACT_SHA256,
              'kim_form_assessment_sha256': FORM_ASSESSMENT_SHA256, 'formula_registry_sha256': REGISTRY_SHA256,
              'trials': trials, 'seed': seed, 'classification': plan['classification'],
              'not_this': copy.deepcopy(plan['not_this']),
              'primary_endpoint_by_group': headline, 'classification_across_scenarios': robust,
              'secondary_absolute_auc_by_group': absolute, 'scenarios': scenarios,
              'known_differences': copy.deepcopy(plan['known_differences']),
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_kim_renal_group_check_commands(app):
    @app.cli.command('kim-renal-group-check')
    @click.option('--trials', type=click.IntRange(100, 100000), help='Override the plan (for quick looks only).')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(trials, output):
        """Run the locked Kim renal-group consistency check. Exploratory; not validation."""
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
