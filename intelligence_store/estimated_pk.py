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
    if estimate['status'] != 'estimated':
        report['status'] = 'missing_estimator_inputs'
        report['simulation_status'] = 'not_run'
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
