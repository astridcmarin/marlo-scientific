"""Kim 2026 lenalidomide population PK model: covariates, exact two-compartment solution, typical-value run.

Kim et al. (Drug Des Devel Ther 2026;20:605741) modelled unbound and total lenalidomide in 30 Korean
multiple myeloma patients spanning eGFR 11-95 mL/min/1.73 m2. Parameters are on the UNBOUND scale;
total concentration = unbound / Fu. Covariates: CKD-EPI 2021 eGFR (indexed) and Du Bois BSA.

The printed CL/F equation's BSA term is ambiguous; the form is a declared argument with a recorded
assessment (kim_cl_equation_form_assessment_v1.json). Outputs are typical values for declared synthetic
covariates; not individual predictions and not dosing advice.
"""
import copy
import json
import math
from pathlib import Path

import click
from sqlalchemy.exc import SQLAlchemyError

from .patient_state import digest, validate_patient_state, SCHEMA_VERSION as STATE_SCHEMA
from .patient_state_revisions import read_revision
from .covariate_estimation import (CovariateEstimationError, _load_pinned, _step, _field_input, _range_status,
                                   load_formula_registry, body_surface_area_du_bois, egfr_ckd_epi_2021,
                                   REGISTRY_SHA256, CREATININE_UMOL_PER_MG_DL)
from .treatment_requests import validate_treatment_request, _read_json

DATA = Path(__file__).parent / 'data'
EXTRACT_PATH = DATA / 'kim_2026_model_extract_v1.json'
EXTRACT_SHA256 = 'c8d4c4bff1d84adae8016d0a1e6e864423b578d7564f2ffbf81c70501e0c25af'
FORM_ASSESSMENT_PATH = DATA / 'kim_cl_equation_form_assessment_v1.json'
FORM_ASSESSMENT_SHA256 = '1de6b91bd9e8f5d633182f8794defc3a85c47f668dfc15ea9bcfe3695bc95d5a'
FINDINGS_PATH = DATA / 'kim_applicability_findings_v1.json'
FINDINGS_SHA256 = 'deb1c48cf97a59d6bca251935cb1e57fb4a64c158810bf1583a78aeb157d9af9'
DOSE_EVIDENCE_PATH = DATA / 'lenalidomide_dose_proportionality_evidence_v1.json'
DOSE_EVIDENCE_SHA256 = 'ec140c8f5ea9fa5c348d1bbde535a7dfd19dacd17360b0eb3607798e9b5f2952'

ESTIMATE_SCHEMA = 'kim-covariate-estimate-v1'
RUN_SCHEMA = 'kim-educational-pk-v1'
METHOD_VERSION = 'kim-model-v1.0'
REQUIRED_FIELDS = ('age_years', 'biological_sex', 'weight', 'height', 'serum_creatinine')
CL_FORMS = ('linear_multiplicative', 'exponential', 'additive_as_printed')
STUDY_DOSES_MG = (5.0, 7.5, 10.0)
DISPLAY_STEP_H = 0.1
MAX_HORIZON_H = 72.0
MAX_EVENTS = 4
INTERVAL_H = 24.0
PREDICTION_TYPE = 'typical_value_for_declared_covariates'


def load_extract(path=EXTRACT_PATH):
    return _load_pinned(path, EXTRACT_SHA256, 'pk-model-extract-v1', 'Kim 2026 model extract')


def load_form_assessment(path=FORM_ASSESSMENT_PATH):
    return _load_pinned(path, FORM_ASSESSMENT_SHA256, 'covariate-method-assessment-v1', 'Kim CL equation-form assessment')


def load_applicability_findings(path=FINDINGS_PATH):
    return _load_pinned(path, FINDINGS_SHA256, 'model-applicability-findings-v1', 'Kim applicability findings')


def load_dose_proportionality_evidence(path=DOSE_EVIDENCE_PATH):
    return _load_pinned(path, DOSE_EVIDENCE_SHA256, 'pk-property-evidence-v1', 'Lenalidomide dose-proportionality evidence')


def primary_cl_form():
    return load_form_assessment()['decision']['primary_form']


# ------------------------------------------------------------------ parameters

def typical_parameters(egfr, bsa, cl_form, extract=None):
    """Typical unbound-scale parameters (random effects zero) for one covariate set and CL/F form."""
    if cl_form not in CL_FORMS:
        raise ValueError(f'cl_form must be one of {", ".join(CL_FORMS)}; there is no default.')
    p = {k: v['value'] for k, v in (extract or load_extract())['parameters'].items()}
    renal = math.exp(p['cl_egfr_coefficient'] * (egfr - p['reference_egfr']))
    body = bsa - p['reference_bsa']
    if cl_form == 'linear_multiplicative':
        cl = p['unbound_clearance_l_h'] * renal * (1 + p['cl_bsa_coefficient'] * body)
    elif cl_form == 'exponential':
        cl = p['unbound_clearance_l_h'] * renal * math.exp(p['cl_bsa_coefficient'] * body)
    else:
        cl = p['unbound_clearance_l_h'] * renal + p['cl_bsa_coefficient'] * body
    if not math.isfinite(cl) or cl <= 0:
        raise ValueError('CL/F is not positive for these covariates under this equation form.')
    v1 = p['unbound_central_volume_l'] * math.exp(p['v1_bsa_coefficient'] * body)
    return {'unbound_clearance_l_h': cl, 'unbound_central_volume_l': v1,
            'unbound_intercompartmental_clearance_l_h': p['unbound_intercompartmental_clearance_l_h'],
            'unbound_peripheral_volume_l': p['unbound_peripheral_volume_l'], 'absorption_rate_h': p['absorption_rate_h'],
            'fraction_unbound': p['fraction_unbound'], 'total_clearance_l_h': cl * p['fraction_unbound']}


# ------------------------------------------------------------------ exact solution

def _central_amount_exact(t, ka, k10, k12, k21):
    s = k10 + k12 + k21
    root = math.sqrt(s * s - 4 * k10 * k21)
    alpha, beta = (s + root) / 2, (s - root) / 2
    return ka * ((k21 - alpha) * math.exp(-alpha * t) / ((ka - alpha) * (beta - alpha))
                 + (k21 - beta) * math.exp(-beta * t) / ((ka - beta) * (alpha - beta))
                 + (k21 - ka) * math.exp(-ka * t) / ((alpha - ka) * (beta - ka)))


def central_amount_unit_dose(t, ka, cl, v1, q, v2):
    """Central amount (mg) after 1 mg oral dose; first-order absorption into a two-compartment system.

    Sum-of-exponentials solution. When ka nearly coincides with a disposition rate the expression is 0/0,
    so it is evaluated at ka(1 +/- 1e-4) and averaged (error of order 1e-8 relative).
    """
    if t <= 0:
        return 0.0
    k10, k12, k21 = cl / v1, q / v1, q / v2
    s = k10 + k12 + k21
    root = math.sqrt(s * s - 4 * k10 * k21)
    alpha, beta = (s + root) / 2, (s - root) / 2
    if min(abs(ka - alpha), abs(ka - beta)) < 1e-6 * ka:
        return 0.5 * (_central_amount_exact(t, ka * (1 + 1e-4), k10, k12, k21)
                      + _central_amount_exact(t, ka * (1 - 1e-4), k10, k12, k21))
    return _central_amount_exact(t, ka, k10, k12, k21)


def disposition_rates(params):
    k10 = params['unbound_clearance_l_h'] / params['unbound_central_volume_l']
    k12 = params['unbound_intercompartmental_clearance_l_h'] / params['unbound_central_volume_l']
    k21 = params['unbound_intercompartmental_clearance_l_h'] / params['unbound_peripheral_volume_l']
    s = k10 + k12 + k21
    root = math.sqrt(s * s - 4 * k10 * k21)
    return (s + root) / 2, (s - root) / 2


def concentration_curves(params, events, times):
    """Unbound and total concentrations (ng/mL) by superposition of unit-dose responses."""
    unit = [central_amount_unit_dose(t, params['absorption_rate_h'], params['unbound_clearance_l_h'],
                                     params['unbound_central_volume_l'],
                                     params['unbound_intercompartmental_clearance_l_h'],
                                     params['unbound_peripheral_volume_l']) for t in times]
    step = times[1] - times[0]
    unbound = []
    for i, _ in enumerate(times):
        amount = math.fsum(dose * unit[i - round(start / step)] for start, dose in events if i >= round(start / step))
        unbound.append(1000.0 * amount / params['unbound_central_volume_l'])
    total = [c / params['fraction_unbound'] for c in unbound]
    return unbound, total


# ------------------------------------------------------------------ covariates

def estimate_kim_covariates(state):
    """eGFR (CKD-EPI 2021) and BSA (Du Bois) from a synthetic patient state, with provenance and coverage."""
    try:
        canonical = validate_patient_state(state)
    except ValueError as exc:
        raise CovariateEstimationError(str(exc)) from exc
    registry = load_formula_registry()
    extract = load_extract()
    fields = canonical['fields']
    missing = [name for name in REQUIRED_FIELDS if fields[name]['value'] is None]
    report = {'schema_version': ESTIMATE_SCHEMA, 'method_version': METHOD_VERSION, 'model': 'lenalidomide_kim_2026',
              'purpose': 'synthetic_educational', 'state_schema_version': STATE_SCHEMA, 'state_sha256': digest(canonical),
              'registry_version': registry['registry_version'], 'registry_sha256': REGISTRY_SHA256,
              'extract_version': extract['extract_version'], 'extract_sha256': EXTRACT_SHA256,
              'status': 'missing_inputs' if missing else 'estimated', 'missing_fields': missing,
              'estimates': None, 'derivations': [], 'coverage_checks': [], 'warnings': [],
              'applicability_findings': [], 'findings_version': None,
              'simulation_status': 'not_run', 'ready_for_patient_simulation': False,
              'limitations': ['Estimates are calculations from declared synthetic inputs, not measurements.',
                              'eGFR here is the indexed CKD-EPI 2021 value the Kim model was fitted with; it is not creatinine clearance.',
                              'Reported study ranges are coverage context, not clinical thresholds.',
                              'No exposure, efficacy, toxicity or dosing output.']}
    if missing:
        report['report_sha256'] = digest(report)
        return report
    age, sex = fields['age_years']['value'], fields['biological_sex']['value']
    weight, height, scr = fields['weight']['value'], fields['height']['value'], fields['serum_creatinine']['value']
    egfr = egfr_ckd_epi_2021(age, scr, sex)
    bsa = body_surface_area_du_bois(weight, height)
    report['derivations'] = [
        _step('egfr_indexed', egfr, 'mL/min/1.73m2', 'egfr_ckd_epi_2021_creatinine', registry,
              {'age_years': _field_input(canonical, 'age_years'), 'serum_creatinine': _field_input(canonical, 'serum_creatinine'),
               'biological_sex': _field_input(canonical, 'biological_sex')},
              {'creatinine_umol_per_mg_dl': CREATININE_UMOL_PER_MG_DL}),
        _step('body_surface_area', bsa, 'm2', 'body_surface_area_du_bois', registry,
              {'weight': _field_input(canonical, 'weight'), 'height': _field_input(canonical, 'height')})]
    ranges = extract['study_population']['ranges_table1']
    checks = [('age_years', age, 'year', ranges['age_years'], 'estimator_input'),
              ('weight', weight, 'kg', ranges['weight_kg'], 'estimator_input'),
              ('height', height, 'cm', ranges['height_cm'], 'estimator_input'),
              ('serum_creatinine', scr, 'umol/L', [v * CREATININE_UMOL_PER_MG_DL for v in ranges['serum_creatinine_mg_dl']], 'estimator_input'),
              ('egfr_indexed', egfr, 'mL/min/1.73m2', ranges['egfr_ml_min_1_73m2'], 'model_covariate'),
              ('body_surface_area', bsa, 'm2', ranges['bsa_m2'], 'model_covariate')]
    for name, value, unit, bounds, role in checks:
        report['coverage_checks'].append({'field': name, 'role': role, 'value': value, 'unit': unit,
                                          'source_range': list(bounds), 'status': _range_status(value, bounds)})
    outside = [c['field'] for c in report['coverage_checks'] if c['status'] == 'outside_reported_range']
    if outside:
        report['warnings'].append('Outside the reported Kim 2026 study ranges: ' + ', '.join(outside) + '. Any model use would be extrapolation.')
    findings = load_applicability_findings()
    covariates = {'egfr_indexed': egfr, 'body_surface_area': bsa}
    for finding in findings['findings']:
        if covariates[finding['covariate']] < finding['applies_below']:
            report['warnings'].append(finding['warning'])
            report['applicability_findings'].append({'id': finding['id'], 'status': finding['status'],
                                                     'evidence_report': finding['evidence']['report']})
    report['findings_version'] = findings['findings_version']
    declared = fields['egfr_indexed']['value']
    if declared is not None and not math.isclose(declared, egfr, rel_tol=1e-9):
        report['warnings'].append(f'The state also declares egfr_indexed = {declared} mL/min/1.73m2; the CKD-EPI 2021 estimate differs and neither replaces the other.')
    report['warnings'].append('Kim 2026 was fitted in 30 Korean patients with multiple myeloma at steady state under fasting conditions; '
                              'other populations, conditions and albumin below 3 g/dL are not represented.')
    report['estimates'] = {'egfr_indexed': {'value': egfr, 'unit': 'mL/min/1.73m2', 'formula_id': 'egfr_ckd_epi_2021_creatinine'},
                           'body_surface_area': {'value': bsa, 'unit': 'm2', 'formula_id': 'body_surface_area_du_bois'}}
    report['report_sha256'] = digest(report)
    return report


# ------------------------------------------------------------------ typical-value run

def _events(request):
    canonical = validate_treatment_request(request)
    events = [(e['time']['value'], e['amount']['value']) for e in canonical['events']]
    horizon = canonical['horizon']['value']
    blockers = []
    if any(a not in STUDY_DOSES_MG for _, a in events):
        blockers.append({'code': 'amount_outside_study', 'message': 'Kim 2026 patients received 5, 7.5 or 10 mg; other amounts are not executed.'})
    if events[0][0] != 0 or any(b[0] - a[0] != INTERVAL_H for a, b in zip(events, events[1:])) or len(events) > MAX_EVENTS:
        blockers.append({'code': 'schedule_outside_execution_scope', 'message': 'Time zero, then exactly 24 h intervals, at most four events.'})
    if horizon > MAX_HORIZON_H or round(horizon / DISPLAY_STEP_H, 9) != round(horizon / DISPLAY_STEP_H):
        blockers.append({'code': 'horizon_outside_execution_scope', 'message': 'Horizon must be at most 72 h on the 0.1 h grid.'})
    return canonical, events, horizon, blockers


def calculate_kim_pk(revision_id, request, disease_code, cl_form):
    """Kim 2026 typical-value unbound and total curves for a saved synthetic revision."""
    if cl_form not in CL_FORMS:
        raise ValueError(f'cl_form must be one of {", ".join(CL_FORMS)}; there is no default.')
    revision = read_revision(revision_id)
    if revision is None:
        raise ValueError('Saved patient-state revision does not exist.')
    estimate = estimate_kim_covariates(copy.deepcopy(revision.payload['state']))
    if estimate['state_sha256'] != revision.state_sha256:
        raise ValueError('Estimate does not match the saved revision state; no calculation was generated.')
    assessment = load_form_assessment()
    canonical, events, horizon, blockers = _events(request)
    if disease_code != 'MM':
        blockers.append({'code': 'disease_context_outside_study', 'message': 'Kim 2026 enrolled only patients with multiple myeloma; declare MM to run this model.'})
    if estimate['status'] != 'estimated':
        blockers.append({'code': 'missing_estimator_inputs', 'message': 'Missing: ' + ', '.join(estimate['missing_fields'])})
    report = {'schema_version': RUN_SCHEMA, 'method_version': METHOD_VERSION, 'model': 'lenalidomide_kim_2026',
              'revision_id': revision_id, 'cl_form': cl_form,
              'cl_form_evidence': {'assessment_status': assessment['status'],
                                   'is_primary_form': cl_form == assessment['decision']['primary_form'],
                                   **copy.deepcopy(assessment['form_evidence'][cl_form])},
              'prediction_type': PREDICTION_TYPE, 'covariate_estimate': estimate,
              'covariate_estimate_sha256': estimate['report_sha256'], 'treatment_request': canonical,
              'declared_disease_code': disease_code, 'execution_blockers': blockers,
              'parameters': None, 'times_h': None, 'unbound_concentration_ng_ml': None, 'total_concentration_ng_ml': None,
              'clinical_prediction_validated': False, 'ready_for_patient_simulation': False,
              'limitations': ['Typical-value curve: random effects are zero; patients with identical covariates vary around it.',
                              'Unbound and total concentrations assume constant Fu = 0.614 (linear binding).',
                              'Initial amounts are zero before the first requested dose; Kim sampled at steady state.',
                              'Not an individual prediction, efficacy or toxicity estimate, or dose recommendation.']}
    if blockers:
        report['status'] = 'blocked'
        report['simulation_status'] = 'not_run'
    else:
        e = estimate['estimates']
        params = typical_parameters(e['egfr_indexed']['value'], e['body_surface_area']['value'], cl_form)
        times = [round(i * DISPLAY_STEP_H, 10) for i in range(round(horizon / DISPLAY_STEP_H) + 1)]
        unbound, total = concentration_curves(params, events, times)
        dose = math.fsum(a for _, a in events)
        alpha, beta = disposition_rates(params)
        report.update(status='completed', simulation_status='completed_educational_calculation', parameters=params,
                      times_h=times, unbound_concentration_ng_ml=unbound, total_concentration_ng_ml=total,
                      exposure={'total_auc_0_horizon_ng_h_ml': math.fsum((total[i] + total[i + 1]) / 2 * DISPLAY_STEP_H for i in range(len(total) - 1)),
                                'total_auc_0_infinity_ng_h_ml': 1000.0 * dose / params['total_clearance_l_h'],
                                'unbound_auc_0_infinity_ng_h_ml': 1000.0 * dose / params['unbound_clearance_l_h'],
                                'peak_total_ng_ml': max(total), 'peak_time_h': times[total.index(max(total))],
                                'terminal_half_life_h': math.log(2) / beta, 'distribution_half_life_h': math.log(2) / alpha})
    report['report_sha256'] = digest(report)
    return report


def reproduce_group_clearance():
    """Internal reproduction: typical total and unbound CL/F at each group's Table 1 median covariates
    against the authors' Table 2 non-compartmental group means. Same patients the model was fitted to."""
    extract = load_extract()
    groups = extract['author_reported_groups']
    rows = []
    for group, median in groups['table1_medians'].items():
        row = {'group': group, 'n': median['n'], 'egfr_median': median['egfr'], 'bsa_median': median['bsa'],
               'reported_total_cl_f': groups['table2_total_cl_f_l_h'][group],
               'reported_unbound_cl_f': groups['table2_unbound_cl_f_l_h'][group], 'forms': {}}
        for form in CL_FORMS:
            params = typical_parameters(median['egfr'], median['bsa'], form, extract)
            total, unbound = params['total_clearance_l_h'], params['unbound_clearance_l_h']
            row['forms'][form] = {
                'typical_total_cl_f': total, 'typical_unbound_cl_f': unbound,
                'total_within_one_sd': abs(total - row['reported_total_cl_f']['mean']) <= row['reported_total_cl_f']['sd'],
                'total_ratio_to_reported_mean': total / row['reported_total_cl_f']['mean']}
        rows.append(row)
    report = {'schema_version': 'kim-internal-reproduction-v1', 'method_version': METHOD_VERSION,
              'extract_sha256': EXTRACT_SHA256, 'classification': 'internal_descriptive_reproduction',
              'caveat': groups['caveat'], 'groups': rows}
    report['report_sha256'] = digest(report)
    return report


def compare_typical_exposure(state, dose_mg, hughes_weight_basis=None, kim_cl_form=None):
    """Hughes 2019 and Kim 2026 typical total CL/F and AUC to infinity for one synthetic state and dose."""
    from .covariate_estimation import estimate_hughes_covariates, primary_weight_basis_hughes
    from .pk_parameter_reference import load_parameter_extract, _parameter_math
    dose = float(dose_mg)
    if not math.isfinite(dose) or dose <= 0:
        raise ValueError('Dose must be a positive number of mg.')
    hughes_basis = hughes_weight_basis or primary_weight_basis_hughes()
    kim_form = kim_cl_form or primary_cl_form()
    hughes = estimate_hughes_covariates(state, hughes_basis)
    kim = estimate_kim_covariates(state)
    rows = {}
    if hughes['status'] == 'estimated':
        cl = _parameter_math(hughes['estimates']['fat_free_mass']['value'], hughes['estimates']['creatinine_clearance']['value'],
                             load_parameter_extract()['parameters'])['apparent_clearance_l_h']
        rows['lenalidomide_hughes_2019'] = {
            'covariates': {k: v['value'] for k, v in hughes['estimates'].items()}, 'assumption': {'weight_basis': hughes_basis},
            'typical_total_cl_f_l_h': cl, 'auc_0_infinity_ng_h_ml': 1000.0 * dose / cl,
            'warnings': hughes['warnings'], 'estimate_sha256': hughes['report_sha256']}
    if kim['status'] == 'estimated':
        params = typical_parameters(kim['estimates']['egfr_indexed']['value'], kim['estimates']['body_surface_area']['value'], kim_form)
        rows['lenalidomide_kim_2026'] = {
            'covariates': {k: v['value'] for k, v in kim['estimates'].items()}, 'assumption': {'cl_form': kim_form},
            'typical_total_cl_f_l_h': params['total_clearance_l_h'], 'auc_0_infinity_ng_h_ml': 1000.0 * dose / params['total_clearance_l_h'],
            'warnings': kim['warnings'], 'estimate_sha256': kim['report_sha256']}
    report = {'schema_version': 'lenalidomide-model-comparison-v1', 'method_version': METHOD_VERSION, 'dose_mg': dose,
              'state_sha256': kim['state_sha256'], 'models': rows,
              'missing_fields': sorted(set(hughes['missing_fields']) | set(kim['missing_fields'])),
              'kim_to_hughes_auc_ratio': (rows['lenalidomide_kim_2026']['auc_0_infinity_ng_h_ml'] / rows['lenalidomide_hughes_2019']['auc_0_infinity_ng_h_ml']
                                          if len(rows) == 2 else None),
              'note': ('Both are typical values with random effects at zero. Hughes was fitted in US patients with hematologic '
                       'malignancies, Kim in Korean multiple myeloma patients with renal impairment; a difference between them '
                       'is a difference between published models, not a measured fact about any patient.'),
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_kim_model_commands(app):
    @app.cli.command('patient-pk-kim')
    @click.option('--revision-id', type=click.IntRange(min=1), required=True)
    @click.option('--treatment-file', type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True)
    @click.option('--disease-code', type=click.Choice(('MM', 'CLL', 'AML', 'ALL', 'OTHER', 'UNKNOWN')), default='UNKNOWN')
    @click.option('--cl-form', type=click.Choice(CL_FORMS), required=True, help='Reading of the printed CL/F equation (see the assessment).')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(revision_id, treatment_file, disease_code, cl_form, output):
        """Kim 2026 typical-value unbound and total curves for a saved synthetic revision."""
        try:
            report = calculate_kim_pk(revision_id, _read_json(treatment_file), disease_code, cl_form)
            payload = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
            if output:
                with output.open('x', encoding='utf-8') as handle:
                    handle.write(payload)
                click.echo(f'Saved report: {output}\nReport SHA256: {report["report_sha256"]}')
            else:
                click.echo(payload, nl=False)
        except (ValueError, OSError, UnicodeError, SQLAlchemyError) as exc:
            raise click.ClickException(str(exc)) from exc

    @app.cli.command('pk-model-compare')
    @click.option('--example', is_flag=True, help='Use an explicitly invented synthetic state.')
    @click.option('--state-file', type=click.Path(exists=True, dir_okay=False), help='Raw synthetic patient-state JSON.')
    @click.option('--dose-mg', type=click.FloatRange(min=0, min_open=True), required=True)
    def compare_command(example, state_file, dose_mg):
        """Hughes 2019 vs Kim 2026 typical exposure for one synthetic state. Never a clinical prediction."""
        if example == (state_file is not None):
            raise click.ClickException('Choose exactly one of --example or --state-file.')
        try:
            from .covariate_estimation import example_state
            from .patient_state import _read_json as read_state
            state = example_state() if example else read_state(state_file)
            click.echo(json.dumps(compare_typical_exposure(state, dose_mg), indent=2, ensure_ascii=False, allow_nan=False))
        except (ValueError, OSError, UnicodeError) as exc:
            raise click.ClickException(str(exc)) from exc

    @app.cli.command('kim-internal-reproduction')
    def reproduction_command():
        """Kim 2026 typical CL/F at group medians vs the authors' Table 2 (same patients; descriptive)."""
        click.echo(json.dumps(reproduce_group_clearance(), indent=2, ensure_ascii=False, allow_nan=False))
