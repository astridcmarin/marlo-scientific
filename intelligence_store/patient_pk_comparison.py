"""Join verified state differences and archived exposure arithmetic; no prediction."""
from .patient_state import digest
from .patient_state_comparison import _compare_verified_revisions
from .patient_state_revisions import read_revision
from .saved_scenarios import read_scenario
from .educational_pk_runs import read_pk_run
from .educational_pk_comparison import _compare_verified_runs
from .educational_pk_comparison_summary import _treatment_values


def compare_patient_pk(scenario_id, left_revision_id, right_revision_id, left_run_id, right_run_id, *, right_scenario_id=None):
    scenario = read_scenario(scenario_id)
    right_scenario_id = scenario_id if right_scenario_id is None else right_scenario_id
    right_scenario = read_scenario(right_scenario_id)
    a, b = read_revision(left_revision_id), read_revision(right_revision_id)
    if scenario is None or right_scenario is None or a is None or b is None:
        raise ValueError('Choose an existing scenario and two patient revisions.')
    if a.scenario_id != scenario_id or b.scenario_id != right_scenario_id:
        raise ValueError('Each patient revision must belong to its selected scenario.')
    if a.id == b.id:
        raise ValueError('Choose two different patient revisions. Use the existing same-state run comparison for one revision.')
    left, right = read_pk_run(left_run_id), read_pk_run(right_run_id)
    if left is None or right is None or left.revision_id != a.id or right.revision_id != b.id:
        raise ValueError('Each run must belong to its selected patient revision.')
    states = _compare_verified_revisions(a, b)
    states.pop('report_sha256')
    states.pop('scenario_id')
    states.pop('scenario_payload_sha256')
    states.update(schema_version='two-scenario-patient-state-comparison-v1',
        method_version='two-scenario-patient-state-comparison-v1.0',
        left_scenario_id=scenario_id, right_scenario_id=right_scenario_id,
        left_scenario_payload_sha256=scenario.payload_sha256,
        right_scenario_payload_sha256=right_scenario.payload_sha256)
    states['report_sha256'] = digest(states)
    exposure = _compare_verified_runs(left, right, revision_id=a.id)
    left_drug = scenario.payload['analysis']['report']['selected_drug']['entity_id']
    right_drug = right_scenario.payload['analysis']['report']['selected_drug']['entity_id']
    drugs_match = left_drug == right_drug == exposure['left']['request']['drug'] == exposure['right']['request']['drug']
    exposure['compatibility_checks'].append({'code':'scenario_and_treatment_drug_identity','matches':drugs_match})
    if not drugs_match:
        exposure.update(status='comparison_withheld', points=None, exposure_difference=None)
    exposure.pop('report_sha256')
    exposure.pop('revision_id')
    exposure.update(schema_version='cross-revision-educational-pk-comparison-v1',
        method_version='cross-revision-educational-pk-comparison-v1.0',
        left_revision_id=a.id, right_revision_id=b.id)
    exposure['report_sha256'] = digest(exposure)
    changes = [r['field'] for r in exposure['covariate_changes'] if r['value_changed']]
    treatment_changed = _treatment_values(exposure['left']['request']) != _treatment_values(exposure['right']['request'])
    if treatment_changed:
        context = 'Treatment values differ; a covariate effect is not isolated.'
    elif len(changes) > 1:
        context = 'Multiple explicit model covariates differ; this is a combined-input comparison.'
    elif changes:
        context = 'One explicit model covariate differs. This describes a model-input comparison, not a verified patient effect.'
    else:
        context = 'No explicit model covariate values or treatment values differ. Patient-state changes alone do not imply an exposure change.'
    if exposure['status'] != 'compatible_educational_comparison':
        context = 'Archive compatibility differs; exposure overlay and differences are withheld. Recorded input differences remain visible.'
    report = {
        'schema_version': 'patient-state-exposure-comparison-v2',
        'method_version': 'patient-state-exposure-comparison-v2.0',
        'scenario_id': scenario_id, 'scenario_payload_sha256': scenario.payload_sha256,
        'right_scenario_id': right_scenario_id,
        'scenario_sources': {
            side: {'scenario_id': row.id, 'title': row.title, 'payload_sha256': row.payload_sha256,
                   'cohort': row.payload['analysis']['report']['cohort'],
                   'selected_drug': row.payload['analysis']['report']['selected_drug']}
            for side, row in (('left', scenario), ('right', right_scenario))},
        'state_comparison': states, 'exposure_comparison': exposure,
        'context': context, 'treatment_values_changed': treatment_changed,
        'changed_explicit_covariates': changes,
        'clinical_prediction_validated': False, 'ready_for_patient_simulation': False,
        'model_rerun': False, 'database_writes_performed': False,
        'limitation': 'Compares two synthetic state revisions and their independently declared educational PK archives. Revisions do not establish biological progression or two independently observed patients. Exposure differences are not efficacy, toxicity, dose suitability or clinical causality. No doses are normalized and no state field is substituted into model inputs.'}
    report['report_sha256'] = digest(report)
    return report
