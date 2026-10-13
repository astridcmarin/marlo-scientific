"""Deterministic covariate estimation for synthetic patient states (Patient Lab 2.0b).

Turns declared synthetic state fields into the covariates a published model needs, with
the formula, version, inputs and assumptions recorded for each value. The first consumer
is the Hughes 2019 lenalidomide model (fat-free mass and Cockcroft-Gault CrCl).

An estimate is a calculation under stated assumptions. It is not a measured value, it does
not make a model applicable, and nothing here runs a simulation or predicts a response.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

import click

from .patient_state import digest, validate_patient_state, UNITS as STATE_UNITS, SCHEMA_VERSION as STATE_SCHEMA

SCHEMA_VERSION = 'hughes-covariate-estimate-v1'
COMPARISON_SCHEMA_VERSION = 'hughes-covariate-weight-basis-comparison-v1'
METHOD_VERSION = 'covariate-estimation-v1.0'
DATA = Path(__file__).parent / 'data'
REGISTRY_PATH = DATA / 'covariate_formula_registry_v1.json'
REGISTRY_SHA256 = '04b601577f7a9b4b6a41b6ef7218d96fb68ee2ea731fee50f57de57b3456b712'
ASSESSMENT_PATH = DATA / 'hughes_weight_basis_assessment_v1.json'
ASSESSMENT_SHA256 = 'bbaffa714dd5bd2fb9773a1620fb022c35bd90175b972d0a0855d9f6916be2c6'
VARIABILITY_PATH = DATA / 'hughes_variability_extract_v1.json'
VARIABILITY_SHA256 = '2e5970e646f6acdbee434f6c52e1bc051ecfdec163c0aee825fe1c4ea1dde5d4'
COVERAGE_PATH = DATA / 'hughes_coverage_contract_v1.json'
FINDINGS_PATH = DATA / 'hughes_applicability_findings_v1.json'
FINDINGS_SHA256 = 'a7dbfdd44cc3c5f56a6642cdd762eedab3da3a8f57f30c32f22fcd5029bce5a0'
COVERAGE_SHA256 = 'b452b4f21d4449ef88fc7821481376c08b16ad8fcd1b90a6664bba7408857fe6'

WEIGHT_BASES = ('ideal_body_weight_devine', 'adjusted_body_weight_0_4', 'total_body_weight')
REQUIRED_FIELDS = ('age_years', 'biological_sex', 'weight', 'height', 'serum_creatinine')

# Constants mirror the pinned registry; tests assert that they agree.
CREATININE_UMOL_PER_MG_DL = 88.4
CM_PER_INCH = 2.54
JANMAHASATIAN = {'MALE': (9270.0, 6680.0, 216.0), 'FEMALE': (9270.0, 8780.0, 244.0)}
DEVINE_BASE_KG = {'MALE': 50.0, 'FEMALE': 45.5}
DEVINE_KG_PER_INCH = 2.3
DEVINE_MIN_HEIGHT_CM = 60 * CM_PER_INCH
ABW_FACTOR = 0.4
CG_FEMALE_FACTOR = 0.85


class CovariateEstimationError(ValueError):
    pass


def _load_pinned(path, expected, schema, label):
    try:
        raw = Path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('Checksum differs')
        data = json.loads(raw)
        if data['schema_version'] != schema:
            raise ValueError('Schema differs')
        return data
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CovariateEstimationError(f'{label} is missing or changed; no estimate was generated.') from exc


def load_formula_registry(path=REGISTRY_PATH):
    return _load_pinned(path, REGISTRY_SHA256, 'covariate-formula-registry-v1', 'Covariate formula registry')


def load_weight_basis_assessment(path=ASSESSMENT_PATH):
    return _load_pinned(path, ASSESSMENT_SHA256, 'covariate-method-assessment-v1', 'Weight-basis assessment')


def load_variability_extract(path=VARIABILITY_PATH):
    return _load_pinned(path, VARIABILITY_SHA256, 'pk-variability-extract-v1', 'Variability extract')


def load_applicability_findings(path=FINDINGS_PATH):
    return _load_pinned(path, FINDINGS_SHA256, 'model-applicability-findings-v1', 'Applicability findings')


def load_coverage_contract(path=COVERAGE_PATH):
    return _load_pinned(path, COVERAGE_SHA256, 'hughes-coverage-contract-v1', 'Source coverage contract')


# ---------------------------------------------------------------- formulas

def _positive(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise CovariateEstimationError(f'{label} must be a finite positive number.')
    return float(value)


def _sex(value):
    if value not in ('MALE', 'FEMALE'):
        raise CovariateEstimationError('biological_sex must be MALE or FEMALE for these sex-specific formulas.')
    return value


def body_mass_index(weight_kg, height_cm):
    weight, height = _positive(weight_kg, 'weight'), _positive(height_cm, 'height')
    return weight / (height / 100.0) ** 2


def fat_free_mass_janmahasatian(weight_kg, height_cm, sex):
    numerator, intercept, slope = JANMAHASATIAN[_sex(sex)]
    weight = _positive(weight_kg, 'weight')
    return numerator * weight / (intercept + slope * body_mass_index(weight, height_cm))


def ideal_body_weight_devine(height_cm, sex):
    height = _positive(height_cm, 'height')
    value = DEVINE_BASE_KG[_sex(sex)] + DEVINE_KG_PER_INCH * (height / CM_PER_INCH - 60.0)
    if value <= 0:
        raise CovariateEstimationError('Devine ideal body weight is not defined at this height.')
    return value


def adjusted_body_weight(weight_kg, ideal_weight_kg, factor=ABW_FACTOR):
    weight, ideal = _positive(weight_kg, 'weight'), _positive(ideal_weight_kg, 'ideal body weight')
    return ideal + factor * (weight - ideal)


def cockcroft_gault(age_years, dosing_weight_kg, serum_creatinine_umol_l, sex):
    if isinstance(age_years, bool) or not isinstance(age_years, (int, float)) or not 0 <= age_years < 140:
        raise CovariateEstimationError('Cockcroft-Gault requires an age between 0 and 140 years.')
    weight = _positive(dosing_weight_kg, 'dosing weight')
    scr_mg_dl = _positive(serum_creatinine_umol_l, 'serum creatinine') / CREATININE_UMOL_PER_MG_DL
    value = (140.0 - age_years) * weight / (72.0 * scr_mg_dl)
    return value * (CG_FEMALE_FACTOR if _sex(sex) == 'FEMALE' else 1.0)


# ---------------------------------------------------------------- estimation

def _range_status(value, bounds):
    lo, hi = bounds
    return 'within_reported_range' if lo <= value <= hi else 'outside_reported_range'


def _step(quantity, value, unit, formula_id, registry, inputs, assumptions=None):
    return {'quantity': quantity, 'value': value, 'unit': unit, 'formula_id': formula_id,
            'formula_version': registry['formulas'][formula_id]['version'],
            'inputs': inputs, 'assumptions': assumptions or {}}


def _field_input(state, name):
    field = state['fields'][name]
    return {'value': field['value'], 'unit': field['unit'], 'from': f'patient_state.{name}', 'origin': field['origin']}


def estimate_hughes_covariates(state, weight_basis):
    """Estimate Hughes 2019 covariates from a synthetic patient state under one declared weight basis."""
    if weight_basis not in WEIGHT_BASES:
        raise CovariateEstimationError(f'weight_basis must be one of {", ".join(WEIGHT_BASES)}; there is no default.')
    try:
        canonical = validate_patient_state(state)
    except ValueError as exc:
        raise CovariateEstimationError(str(exc)) from exc
    registry = load_formula_registry()
    assessment = load_weight_basis_assessment()
    coverage = load_coverage_contract()
    fields = canonical['fields']
    missing = [name for name in REQUIRED_FIELDS if fields[name]['value'] is None]
    report = {
        'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'model': 'lenalidomide_hughes_2019',
        'purpose': 'synthetic_educational',
        'state_schema_version': STATE_SCHEMA, 'state_sha256': digest(canonical),
        'registry_version': registry['registry_version'], 'registry_sha256': REGISTRY_SHA256,
        'assessment_version': assessment['assessment_version'], 'assessment_sha256': ASSESSMENT_SHA256,
        'coverage_contract_sha256': COVERAGE_SHA256,
        'weight_basis': weight_basis,
        'weight_basis_evidence': {
            'assessment_status': assessment['status'],
            'is_primary_assumption': weight_basis == assessment['decision']['primary_assumption'],
            **copy.deepcopy(assessment['basis_evidence'][weight_basis])},
        'status': 'missing_inputs' if missing else 'estimated',
        'missing_fields': missing, 'estimates': None, 'derivations': [], 'coverage_checks': [], 'warnings': [],
        'applicability_findings': [], 'findings_version': None,
        'simulation_status': 'not_run', 'ready_for_patient_simulation': False,
        'limitations': [
            'Estimates are calculations from declared synthetic inputs under the recorded assumptions, not measurements.',
            'The Cockcroft-Gault weight basis used by Hughes et al. is unresolved; see the assessment record.',
            'Reported source ranges are coverage context, not clinical thresholds or evidence of applicability.',
            'Indexed eGFR is never substituted for creatinine clearance.',
            'No exposure, efficacy, toxicity or dosing output.'],
    }
    if missing:
        report['report_sha256'] = digest(report)
        return report

    age = fields['age_years']['value']
    sex = fields['biological_sex']['value']
    weight = fields['weight']['value']
    height = fields['height']['value']
    scr = fields['serum_creatinine']['value']
    warnings = report['warnings']

    bmi = body_mass_index(weight, height)
    ffm = fat_free_mass_janmahasatian(weight, height, sex)
    report['derivations'].append(_step('body_mass_index', bmi, 'kg/m2', 'body_mass_index', registry,
        {'weight': _field_input(canonical, 'weight'), 'height': _field_input(canonical, 'height')}))
    report['derivations'].append(_step('fat_free_mass', ffm, 'kg', 'fat_free_mass_janmahasatian', registry,
        {'weight': _field_input(canonical, 'weight'), 'body_mass_index': {'value': bmi, 'unit': 'kg/m2', 'from': 'derivation.body_mass_index'},
         'biological_sex': _field_input(canonical, 'biological_sex')}))

    if weight_basis == 'total_body_weight':
        dosing_weight, dosing_from = weight, 'patient_state.weight'
    else:
        if height < DEVINE_MIN_HEIGHT_CM:
            warnings.append('Height is below 152.4 cm (60 in); the Devine formula extrapolates below its base weight.')
        ibw = ideal_body_weight_devine(height, sex)
        report['derivations'].append(_step('ideal_body_weight', ibw, 'kg', 'ideal_body_weight_devine', registry,
            {'height': _field_input(canonical, 'height'), 'biological_sex': _field_input(canonical, 'biological_sex')}))
        if weight_basis == 'ideal_body_weight_devine':
            dosing_weight, dosing_from = ibw, 'derivation.ideal_body_weight'
            if weight < ibw:
                warnings.append('Total body weight is below Devine ideal body weight; an ideal-weight basis exceeds actual weight.')
        else:
            dosing_weight = adjusted_body_weight(weight, ibw)
            dosing_from = 'derivation.adjusted_body_weight'
            report['derivations'].append(_step('adjusted_body_weight', dosing_weight, 'kg', 'adjusted_body_weight_0_4', registry,
                {'weight': _field_input(canonical, 'weight'), 'ideal_body_weight': {'value': ibw, 'unit': 'kg', 'from': 'derivation.ideal_body_weight'}},
                {'correction_factor': ABW_FACTOR}))

    crcl = cockcroft_gault(age, dosing_weight, scr, sex)
    report['derivations'].append(_step('creatinine_clearance', crcl, 'mL/min', 'creatinine_clearance_cockcroft_gault', registry,
        {'age_years': _field_input(canonical, 'age_years'),
         'dosing_weight': {'value': dosing_weight, 'unit': 'kg', 'from': dosing_from},
         'serum_creatinine': _field_input(canonical, 'serum_creatinine'),
         'biological_sex': _field_input(canonical, 'biological_sex')},
        {'weight_basis': weight_basis, 'creatinine_umol_per_mg_dl': CREATININE_UMOL_PER_MG_DL,
         'weight_basis_evidence_level': report['weight_basis_evidence']['evidence_level']}))

    if ffm > weight:
        warnings.append('Estimated fat-free mass exceeds total body weight; check the declared inputs.')
    saved = fields['creatinine_clearance']['value']
    if saved is not None and not math.isclose(saved, crcl, rel_tol=1e-9):
        warnings.append(f'The state also declares creatinine_clearance = {saved} mL/min; the estimate differs and neither replaces the other.')
    if fields['egfr_indexed']['value'] is not None:
        warnings.append('Indexed eGFR is present in the state and was not used; it is not a creatinine-clearance equivalent.')

    for name, spec in coverage['state_ranges'].items():
        value = fields[name]['value']
        if fields[name]['unit'] != spec['unit']:
            raise CovariateEstimationError(f'{name}: coverage units differ; no conversion is performed.')
        report['coverage_checks'].append({'field': name, 'role': 'estimator_input', 'value': value,
                                          'unit': spec['unit'], 'source_range': spec['range'],
                                          'status': _range_status(value, spec['range'])})
    for name, value in (('fat_free_mass', ffm), ('creatinine_clearance', crcl)):
        spec = coverage['covariate_ranges'][name]
        report['coverage_checks'].append({'field': name, 'role': 'model_covariate', 'value': value,
                                          'unit': spec['unit'], 'source_range': spec['range'],
                                          'status': _range_status(value, spec['range'])})
    findings = load_applicability_findings()
    report['applicability_findings'] = []
    for finding in findings['findings']:
        value = {'creatinine_clearance': crcl, 'fat_free_mass': ffm}[finding['covariate']]
        if value < finding['applies_below']:
            warnings.append(finding['warning'])
            report['applicability_findings'].append({'id': finding['id'], 'status': finding['status'],
                                                     'evidence_report': finding['evidence']['report']})
    report['findings_version'] = findings['findings_version']
    outside = [c['field'] for c in report['coverage_checks'] if c['status'] == 'outside_reported_range']
    if outside:
        warnings.append('Outside the reported Hughes study ranges: ' + ', '.join(outside) + '. Any model use would be extrapolation.')

    report['estimates'] = {
        'fat_free_mass': {'value': ffm, 'unit': 'kg', 'formula_id': 'fat_free_mass_janmahasatian'},
        'creatinine_clearance': {'value': crcl, 'unit': 'mL/min', 'formula_id': 'creatinine_clearance_cockcroft_gault',
                                 'weight_basis': weight_basis}}
    report['report_sha256'] = digest(report)
    return report


def compare_weight_bases(state):
    """Run every supported weight basis and show how far the unresolved assumption moves CrCl and CL/F."""
    from .pk_parameter_reference import load_parameter_extract, _parameter_math
    extract = load_parameter_extract()
    estimates = {basis: estimate_hughes_covariates(state, basis) for basis in WEIGHT_BASES}
    first = estimates[WEIGHT_BASES[0]]
    rows = []
    if first['status'] == 'estimated':
        for basis, report in estimates.items():
            ffm = report['estimates']['fat_free_mass']['value']
            crcl = report['estimates']['creatinine_clearance']['value']
            params = _parameter_math(ffm, crcl, extract['parameters'])
            rows.append({'weight_basis': basis, 'evidence_level': report['weight_basis_evidence']['evidence_level'],
                         'creatinine_clearance_ml_min': crcl, 'fat_free_mass_kg': ffm,
                         'typical_apparent_clearance_l_h': params['apparent_clearance_l_h'],
                         'estimate_sha256': report['report_sha256']})
    summary = None
    if rows:
        crcls = [r['creatinine_clearance_ml_min'] for r in rows]
        cls = [r['typical_apparent_clearance_l_h'] for r in rows]
        summary = {'crcl_max_to_min_ratio': max(crcls) / min(crcls), 'typical_cl_max_to_min_ratio': max(cls) / min(cls),
                   'interpretation': 'Spread of typical CL/F attributable only to the unresolved weight basis, with random effects at zero.'}
    report = {'schema_version': COMPARISON_SCHEMA_VERSION, 'method_version': METHOD_VERSION,
              'state_sha256': first['state_sha256'], 'status': first['status'], 'missing_fields': first['missing_fields'],
              'parameter_extract_version': extract['extract_version'], 'rows': rows, 'summary': summary,
              'simulation_status': 'not_run', 'ready_for_patient_simulation': False}
    report['report_sha256'] = digest(report)
    return report


def to_hughes_model_inputs(estimate):
    """Express an estimate as hughes-model-inputs-v1 fields, labeled as assumptions with their provenance."""
    if not isinstance(estimate, dict) or estimate.get('schema_version') != SCHEMA_VERSION:
        raise CovariateEstimationError('Expected a hughes-covariate-estimate-v1 report.')
    body = {k: v for k, v in estimate.items() if k != 'report_sha256'}
    if estimate.get('report_sha256') != digest(body):
        raise CovariateEstimationError('Estimate digest mismatch; regenerate the estimate instead of editing it.')
    if estimate['status'] != 'estimated':
        raise CovariateEstimationError('The estimate is incomplete; no model inputs were produced.')
    from .pk_model_inputs import SCHEMA_VERSION as INPUT_SCHEMA, RECORDED_METHODS
    source = (f'{METHOD_VERSION}; estimate sha256 {estimate["report_sha256"]}; state sha256 {estimate["state_sha256"]}; '
              f'registry {estimate["registry_version"]}')
    fields = {}
    for name, value in estimate['estimates'].items():
        note = source
        if name == 'creatinine_clearance':
            note += (f'; Cockcroft-Gault weight basis {estimate["weight_basis"]} '
                     f'({estimate["weight_basis_evidence"]["evidence_level"]}; assessment {estimate["assessment_version"]})')
        fields[name] = {'value': value['value'], 'unit': value['unit'], 'origin': 'assumption',
                        'method': RECORDED_METHODS[name], 'source_ref': note}
    return {'schema_version': INPUT_SCHEMA, 'purpose': 'synthetic_educational', 'fields': fields}


def example_state():
    """An explicitly invented synthetic state with every estimator input declared."""
    values = [('age_years', 65), ('biological_sex', 'MALE'), ('weight', 95), ('height', 178), ('serum_creatinine', 90)]
    fields = {name: {'value': value, 'unit': STATE_UNITS[name], 'origin': 'synthetic_input',
                     'observed_at': None, 'source_ref': None} for name, value in values}
    return validate_patient_state({'schema_version': STATE_SCHEMA, 'purpose': 'synthetic_educational', 'fields': fields})


def register_covariate_estimation_commands(app):
    @app.cli.command('covariate-estimate')
    @click.option('--example', is_flag=True, help='Use an explicitly invented synthetic state.')
    @click.option('--state-file', type=click.Path(exists=True, dir_okay=False), help='Raw synthetic patient-state JSON.')
    @click.option('--weight-basis', type=click.Choice(WEIGHT_BASES), help='Cockcroft-Gault weight basis (required unless --compare-bases).')
    @click.option('--compare-bases', is_flag=True, help='Run every supported weight basis side by side.')
    @click.option('--output', type=click.Path(dir_okay=False), help='Create report JSON; existing files are not overwritten.')
    def covariate_estimate(example, state_file, weight_basis, compare_bases, output):
        """Estimate Hughes 2019 covariates from a synthetic state. No simulation is run."""
        if example == (state_file is not None):
            raise click.ClickException('Choose exactly one of --example or --state-file.')
        if compare_bases == (weight_basis is not None):
            raise click.ClickException('Choose exactly one of --weight-basis or --compare-bases.')
        try:
            if example:
                state = example_state()
            else:
                from .patient_state import _read_json
                state = _read_json(state_file)
            report = compare_weight_bases(state) if compare_bases else estimate_hughes_covariates(state, weight_basis)
            payload = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
            if output:
                with open(output, 'x', encoding='utf-8') as handle:
                    handle.write(payload)
                click.echo(f'Saved report: {output}\nReport SHA256: {report["report_sha256"]}')
            else:
                click.echo(payload, nl=False)
        except (OSError, UnicodeError, ValueError, TypeError, RecursionError) as exc:
            raise click.ClickException(str(exc)) from exc
