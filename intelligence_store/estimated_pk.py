"""Patient Lab 2.0d: typical-value educational PK from a saved synthetic patient revision.

The revision's declared fields are turned into Hughes covariates by `covariate_estimation`
and then run through the existing educational calculation unchanged. The wrapper keeps the
estimate and the calculation together so every curve traces back to formulas, inputs and
the Cockcroft-Gault weight-basis assumption.

The output is the model's typical-value curve for a patient with these covariates
(random effects at zero). It is not an individual prediction for a real person, and it is
not a dose recommendation.
"""
import copy
import json
from pathlib import Path

import click
from sqlalchemy.exc import SQLAlchemyError

from .patient_state import digest
from .patient_state_revisions import read_revision
from .covariate_estimation import WEIGHT_BASES, estimate_hughes_covariates, to_hughes_model_inputs, load_weight_basis_assessment
from .educational_pk import calculate_educational_pk
from .pk_model_inputs import validate_model_inputs
from .treatment_requests import _read_json

SCHEMA_VERSION = 'estimated-educational-pk-v1'
COMPARISON_SCHEMA_VERSION = 'estimated-educational-pk-basis-comparison-v1'
METHOD_VERSION = 'estimated-educational-pk-v1.0'
DISEASE_CODES = ('MM', 'CLL', 'AML', 'ALL', 'OTHER', 'UNKNOWN')

PREDICTION_TYPE = 'typical_value_for_declared_covariates'
PREDICTION_NOTE = ('Typical-value curve: what the model expects for a patient with these covariates, with all random '
                   'effects at zero. Patients with identical covariates vary widely around it (between-subject '
                   'variability in CL/F is about 54% CV in the source model). Not an individual prediction and not '
                   'a dose recommendation.')


def primary_weight_basis():
    """The recorded primary assumption, offered as the visible preselection in the page."""
    return load_weight_basis_assessment()['decision']['primary_assumption']


def estimate_for_revision(revision_id, weight_basis):
    """Estimate covariates from an immutable saved revision and bind the estimate to it."""
    revision = read_revision(revision_id)
    if revision is None:
        raise ValueError('Saved patient-state revision does not exist.')
    estimate = estimate_hughes_covariates(copy.deepcopy(revision.payload['state']), weight_basis)
    if estimate['state_sha256'] != revision.state_sha256:
        raise ValueError('Estimate does not match the saved revision state; no calculation was generated.')
    return estimate


def calculate_estimated_pk(revision_id, weight_basis, request, disease_code='UNKNOWN'):
    """Estimate covariates from the revision, then run the existing bounded educational calculation."""
    if disease_code not in DISEASE_CODES:
        raise ValueError('Unsupported disease context code.')
    estimate = estimate_for_revision(revision_id, weight_basis)
    report = {
        'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION,
        'revision_id': revision_id, 'weight_basis': weight_basis,
        'prediction_type': PREDICTION_TYPE, 'prediction_note': PREDICTION_NOTE,
        'covariate_estimate': estimate, 'covariate_estimate_sha256': estimate['report_sha256'],
        'model_inputs': None, 'calculation': None, 'calculation_sha256': None,
        'clinical_prediction_validated': False, 'ready_for_patient_simulation': False,
        'provenance_note': ('Covariates were computed by the estimator from the saved revision. The inherited '
                            'preflight blocker covariate_provenance_not_verified still applies: the estimator ran, '
                            'but its covariate definitions (including the weight basis) are not independently '
                            'verified against the source study.'),
    }
    from .lenalidomide_scope import hughes_scope
    revision = read_revision(revision_id)
    scope = hughes_scope(copy.deepcopy(revision.payload['state']), weight_basis, disease_code)
    report['model_scope'] = scope
    if estimate['status'] != 'estimated':
        report['status'] = 'missing_estimator_inputs'
        report['simulation_status'] = 'not_run'
    elif scope['scope_evaluation']['status'] != 'in_scope':
        report['status'] = 'outside_model_scope' if scope['scope_evaluation']['status'] == 'out_of_scope' else 'model_scope_cannot_determine'
        report['simulation_status'] = 'not_run'
        report['scope_blockers'] = scope_blockers(scope)
    else:
        inputs = to_hughes_model_inputs(estimate)
        calculation = calculate_educational_pk(revision_id, inputs, request, disease_code)
        if calculation['preflight_review']['explicit_model_inputs'] != validate_model_inputs(inputs):
            raise ValueError('Calculation did not use the estimated covariates; no result was generated.')
        report.update(model_inputs=inputs, calculation=calculation, calculation_sha256=calculation['report_sha256'],
                      status=calculation['status'], simulation_status=calculation['simulation_status'])
    report['report_sha256'] = digest(report)
    return report


def _summary(result):
    calc = result['calculation']
    row = {'weight_basis': result['weight_basis'],
           'evidence_level': result['covariate_estimate']['weight_basis_evidence']['evidence_level'],
           'status': result['status'], 'report_sha256': result['report_sha256']}
    if result['covariate_estimate']['status'] == 'estimated':
        row['creatinine_clearance_ml_min'] = result['covariate_estimate']['estimates']['creatinine_clearance']['value']
        row['fat_free_mass_kg'] = result['covariate_estimate']['estimates']['fat_free_mass']['value']
    if calc is not None and calc['points']:
        peak = max(calc['points'], key=lambda p: p['concentration_ng_ml'])
        row.update(apparent_clearance_l_h=calc['parameters']['apparent_clearance_l_h'],
                   auc_0_horizon_ng_h_ml=calc['auc_0_horizon_ng_h_ml'],
                   peak_concentration_ng_ml=peak['concentration_ng_ml'], peak_time_h=peak['time_h'])
    return row


def compare_estimated_pk(revision_id, request, disease_code='UNKNOWN'):
    """Run every weight basis for one revision and request; curves are kept for overlay display."""
    results = {basis: calculate_estimated_pk(revision_id, basis, request, disease_code) for basis in WEIGHT_BASES}
    rows = [_summary(r) for r in results.values()]
    completed = [r for r in rows if 'auc_0_horizon_ng_h_ml' in r]
    spread = None
    if len(completed) == len(rows):
        aucs = [r['auc_0_horizon_ng_h_ml'] for r in rows]
        crcls = [r['creatinine_clearance_ml_min'] for r in rows]
        spread = {'crcl_max_to_min_ratio': max(crcls) / min(crcls), 'auc_max_to_min_ratio': max(aucs) / min(aucs),
                  'interpretation': 'Exposure spread attributable only to the unresolved weight basis, '
                                    'with random effects at zero.'}
    report = {'schema_version': COMPARISON_SCHEMA_VERSION, 'method_version': METHOD_VERSION,
              'revision_id': revision_id, 'prediction_type': PREDICTION_TYPE, 'rows': rows, 'spread': spread,
              'results': results, 'clinical_prediction_validated': False, 'ready_for_patient_simulation': False}
    report['report_sha256'] = digest(report)
    return report


MODEL_COMPARISON_SCHEMA_VERSION = 'estimated-pk-model-comparison-v1'
MODEL_COMPARISON_NOTE = ('Both curves are typical values (random effects at zero) for covariates estimated from the same '
                         'saved record. Hughes 2019 was fitted in US patients with hematologic malignancies using '
                         'Cockcroft-Gault creatinine clearance; Kim 2026 in 30 Korean multiple myeloma patients with '
                         'renal impairment using CKD-EPI 2021 eGFR. A difference between the curves is a difference '
                         'between published models, not a measured fact about any patient, and neither curve has been '
                         'validated for prediction.')


def scope_blockers(scope):
    """Blockers from a model-scope result: one per rule out of scope or undeterminable."""
    codes = {'out_of_scope': 'outside_model_scope', 'cannot_determine': 'model_scope_cannot_determine'}
    return [{'code': codes[r['status']], 'message': f"{r['id'].replace('_', ' ')}: {r.get('reason') or 'outside the model scope'}"}
            for r in scope['scope_evaluation']['rules'] if r['status'] in codes]


def scope_summary(scope):
    """Compact view of a model-scope result for comparison rows."""
    ev = scope['scope_evaluation']
    return {'status': ev['status'], 'weakest_rule_tier': ev.get('weakest_rule_tier'), 'flags': ev.get('flags', []),
            'rules': ev['rules'], 'observed': scope['observed'], 'scope_sha256': scope['scope_sha256'],
            'scope_version': ev['scope_version']}


def _hughes_row(result):
    row = {'model': 'lenalidomide_hughes_2019', 'label': 'Hughes 2019', 'status': result['status'],
           'assumption': {'weight_basis': result['weight_basis']}, 'covariates': {},
           'warnings': list(result['covariate_estimate']['warnings']), 'blockers': [],
           'report_sha256': result['report_sha256']}
    if result['covariate_estimate']['status'] == 'estimated':
        row['covariates'] = {k: v['value'] for k, v in result['covariate_estimate']['estimates'].items()}
    if 'model_scope' in result:
        row['scope'] = scope_summary(result['model_scope'])
        row['blockers'] = list(result.get('scope_blockers', []))
    calc = result['calculation']
    if calc is not None:
        row['blockers'] = [{'code': b['code'], 'message': b['message']} for b in calc['execution_blockers']]
        if calc['points']:
            peak = max(calc['points'], key=lambda p: p['concentration_ng_ml'])
            row.update(typical_total_cl_f_l_h=calc['parameters']['apparent_clearance_l_h'],
                       auc_0_horizon_ng_h_ml=calc['auc_0_horizon_ng_h_ml'],
                       auc_0_infinity_ng_h_ml=calc['analytic_auc_0_infinity_ng_h_ml'],
                       peak_concentration_ng_ml=peak['concentration_ng_ml'], peak_time_h=peak['time_h'],
                       times_h=[p['time_h'] for p in calc['points']],
                       total_concentration_ng_ml=[p['concentration_ng_ml'] for p in calc['points']])
    return row


def _kim_row(result):
    estimate = result['covariate_estimate']
    row = {'model': 'lenalidomide_kim_2026', 'label': 'Kim 2026', 'status': result['status'],
           'assumption': {'cl_form': result['cl_form'], 'cl_form_evidence': result['cl_form_evidence']},
           'covariates': ({k: v['value'] for k, v in estimate['estimates'].items()} if estimate['status'] == 'estimated' else {}),
           'warnings': list(estimate['warnings']), 'blockers': copy.deepcopy(result['execution_blockers']),
           'report_sha256': result['report_sha256'], 'scope': scope_summary(result['model_scope'])}
    if result['status'] == 'completed':
        exposure = result['exposure']
        row.update(typical_total_cl_f_l_h=result['parameters']['total_clearance_l_h'],
                   auc_0_horizon_ng_h_ml=exposure['total_auc_0_horizon_ng_h_ml'],
                   auc_0_infinity_ng_h_ml=exposure['total_auc_0_infinity_ng_h_ml'],
                   peak_concentration_ng_ml=exposure['peak_total_ng_ml'], peak_time_h=exposure['peak_time_h'],
                   times_h=list(result['times_h']), total_concentration_ng_ml=list(result['total_concentration_ng_ml']),
                   unbound_concentration_ng_ml=list(result['unbound_concentration_ng_ml']))
    return row


def _clearance_variability(model):
    """Between-patient SD of ln CL/F for each published model, from its pinned extract."""
    import math
    if model == 'lenalidomide_hughes_2019':
        from .covariate_estimation import load_variability_extract
        omega = load_variability_extract()['random_effects']['omega_matrix'][0][0]
        return {'omega_cl_sd': math.sqrt(omega), 'source': 'Hughes 2019 final control stream, OMEGA(CL) = %g' % omega,
                'assumption': None}
    if model == 'lenalidomide_kim_2026':
        from .kim_model import load_extract
        re = load_extract()['random_effects']
        return {'omega_cl_sd': re['reported']['cl_pct_cv'] / 100.0,
                'source': 'Kim 2026, between-patient variability of CL/F %g%% CV' % re['reported']['cl_pct_cv'],
                'assumption': re['cv_to_omega']}
    raise ValueError('Unknown model for clearance variability.')


def compare_published_models(revision_id, weight_basis, cl_form, request, disease_code='UNKNOWN'):
    """Hughes 2019 and Kim 2026 typical-value curves for one saved revision and one request.

    Each model keeps its own covariates, assumption, coverage warnings and execution blockers; a model that
    is blocked (for example a dose its study did not use) is shown as blocked, never silently substituted.
    """
    from .kim_model import calculate_kim_pk
    from .reference_exposure import average_daily_dose, compare_to_reference
    from .treatment_requests import validate_treatment_request
    if weight_basis not in WEIGHT_BASES:
        raise ValueError('Unsupported Cockcroft-Gault weight basis.')
    hughes = calculate_estimated_pk(revision_id, weight_basis, request, disease_code)
    kim = calculate_kim_pk(revision_id, request, disease_code, cl_form)
    rows = [_hughes_row(hughes), _kim_row(kim)]
    daily_dose = average_daily_dose(validate_treatment_request(request))
    from .lenalidomide_relative_odds import relative_odds_for_exposure
    for row in rows:
        if 'typical_total_cl_f_l_h' in row:
            row['reference_exposure'] = compare_to_reference(daily_dose, row['typical_total_cl_f_l_h'])
            # Simulation 4.0a: relative odds of grade 3/4 cytopenia from the same exposure ratio (relative only).
            row['relative_odds'] = relative_odds_for_exposure(row['reference_exposure']['ratio_to_reference'],
                                                              variability=_clearance_variability(row['model']))
    ratio = None
    if all('auc_0_infinity_ng_h_ml' in r for r in rows):
        ratio = {'kim_to_hughes_auc_0_infinity': rows[1]['auc_0_infinity_ng_h_ml'] / rows[0]['auc_0_infinity_ng_h_ml'],
                 'kim_to_hughes_peak': rows[1]['peak_concentration_ng_ml'] / rows[0]['peak_concentration_ng_ml']}
    report = {'schema_version': MODEL_COMPARISON_SCHEMA_VERSION, 'method_version': METHOD_VERSION,
              'revision_id': revision_id, 'declared_disease_code': disease_code,
              'prediction_type': PREDICTION_TYPE, 'rows': rows, 'ratio': ratio, 'note': MODEL_COMPARISON_NOTE,
              'hughes_report_sha256': hughes['report_sha256'], 'kim_report_sha256': kim['report_sha256'],
              'clinical_prediction_validated': False, 'ready_for_patient_simulation': False}
    report['report_sha256'] = digest(report)
    return report


def register_estimated_pk_commands(app):
    @app.cli.command('patient-pk-estimated')
    @click.option('--revision-id', type=click.IntRange(min=1), required=True)
    @click.option('--treatment-file', type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True)
    @click.option('--disease-code', type=click.Choice(DISEASE_CODES), default='UNKNOWN')
    @click.option('--weight-basis', type=click.Choice(WEIGHT_BASES), help='Cockcroft-Gault weight basis (required unless --compare-bases).')
    @click.option('--compare-bases', is_flag=True, help='Run every supported weight basis side by side.')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(revision_id, treatment_file, disease_code, weight_basis, compare_bases, output):
        """Estimate covariates from a saved revision and run the educational calculation."""
        if compare_bases == (weight_basis is not None):
            raise click.ClickException('Choose exactly one of --weight-basis or --compare-bases.')
        try:
            request = _read_json(treatment_file)
            report = (compare_estimated_pk(revision_id, request, disease_code) if compare_bases
                      else calculate_estimated_pk(revision_id, weight_basis, request, disease_code))
            payload = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
            if output:
                with output.open('x', encoding='utf-8') as handle:
                    handle.write(payload)
                click.echo(f'Saved report: {output}\nReport SHA256: {report["report_sha256"]}')
            else:
                click.echo(payload, nl=False)
        except (ValueError, OSError, UnicodeError, SQLAlchemyError) as exc:
            raise click.ClickException(str(exc)) from exc
