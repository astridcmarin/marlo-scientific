"""Patient Lab 2.2b: the bortezomib platelet model in a synthetic patient's own absolute counts.

The Lignet 2022 model is scale-invariant: every compartment starts at the baseline, the feedback term uses
the ratio baseline/current, and the drug term does not involve counts, so the fraction-of-baseline curve is
the same whatever the starting count (tested). A patient's absolute curve is therefore their baseline times
the typical fraction. That matches Lonial 2005, where the mean percent fall was independent of baseline;
the same percent fall from a low start reaches lower absolute counts.

This is a typical curve for a hypothetical course of the studied regimen. It is not a prediction of this
patient's counts, their grade of thrombocytopenia, or a suitable dose.
"""
import copy
from pathlib import Path

from .covariate_estimation import _load_pinned
from .patient_state import digest
from .patient_state_revisions import read_revision
from .bortezomib_platelets import platelet_timecourse

CONTEXT_PATH = Path(__file__).parent / 'data' / 'bortezomib_platelet_context_v1.json'
CONTEXT_SHA256 = '4154f2d0cde5933a1e017fce62effbf012bcf09453b3b46e2ef43fb558e12775'
SCHEMA_VERSION = 'bortezomib-patient-platelet-view-v1'
METHOD_VERSION = 'bortezomib-patient-platelets-v1.0'


def load_context(path=CONTEXT_PATH):
    return _load_pinned(path, CONTEXT_SHA256, 'observed-context-v1', 'Bortezomib platelet context')


def grade_for(count, grading):
    """Grade (2-4) under the source's grading for a count, or None at or above 75."""
    for band in grading['thresholds']:
        lo, hi = band['lower_inclusive'], band['upper_exclusive']
        if count < hi and (lo is None or count >= lo):
            return band['grade']
    return None


def patient_platelet_view(revision_id, cycles=1):
    revision = read_revision(revision_id)
    if revision is None:
        raise ValueError('Saved patient-state revision does not exist.')
    state = revision.payload['state']
    context = load_context()
    field = state['fields'].get('platelet_count')
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'revision_id': revision.id,
              'state_schema_version': state['schema_version'], 'state_sha256': revision.state_sha256,
              'context_version': context['context_version'], 'context_sha256': CONTEXT_SHA256,
              'clinical_prediction_validated': False, 'ready_for_patient_simulation': False}
    if field is None or field['value'] is None:
        report.update(status='missing_platelet_count',
                      message=('This record has no baseline platelet count. Save a new patient-state revision with '
                               'the platelet count (schema v2) to draw absolute curves.'))
        report['report_sha256'] = digest(report)
        return report
    baseline = float(field['value'])
    curves = platelet_timecourse(cycles)
    grading = context['grading']
    eligibility = context['eligibility']
    warnings = []
    if baseline < eligibility['minimum_with_extensive_marrow_involvement_1e9_per_l']:
        warnings.append(f'Baseline {baseline:g} x10^9/L is below every entry threshold of the source study '
                        f'(50, or 30 with extensive marrow involvement); the model has no data from such patients.')
    elif baseline < eligibility['minimum_platelets_1e9_per_l']:
        warnings.append(f'Baseline {baseline:g} x10^9/L is below the usual entry threshold of 50 x10^9/L; the source '
                        f'admitted such patients only with extensive marrow involvement or after transfusion.')
    observed = {o['id']: o for o in context['observed']}
    split = observed['grade_4_by_baseline']
    if baseline < split['baseline_threshold_1e9_per_l']:
        incidence = (f"In the source population, grade 4 thrombocytopenia (below 10 x10^9/L) occurred in "
                     f"{split['below_threshold_percent']}% of patients whose baseline was below "
                     f"{split['baseline_threshold_1e9_per_l']} x10^9/L.")
    else:
        incidence = (f"In the source population, grade 4 thrombocytopenia (below 10 x10^9/L) occurred in at most "
                     f"{split['at_or_above_threshold_percent_at_most']}% of patients whose baseline was "
                     f"{split['baseline_threshold_1e9_per_l']} x10^9/L or higher.")
    illustrative_nadir = baseline * (1 - observed['mean_individual_reduction']['value_percent'] / 100.0)
    variants = {}
    for name, v in curves['variants'].items():
        absolute = [baseline * f for f in v['fraction_of_baseline']]
        lowest = baseline * v['nadir_fraction']
        variants[name] = {'description': v['description'], 'absolute_1e9_per_l': absolute,
                          'lowest_typical_1e9_per_l': lowest, 'lowest_typical_time_h': v['nadir_time_h'],
                          'typical_curve_grade_at_lowest': grade_for(lowest, grading),
                          'pre_dose_day11_by_cycle': [dict(d, platelets_1e9_per_l=baseline * d['fraction_of_baseline'])
                                                      for d in v['pre_dose_day11_by_cycle']]}
    report.update(
        status='completed', cycles=cycles, baseline_1e9_per_l=baseline,
        baseline_provenance={k: field[k] for k in ('origin', 'observed_at', 'source_ref')},
        times_h=curves['times_h'], regimen=copy.deepcopy(curves['regimen']), variants=variants,
        grading=copy.deepcopy(grading), eligibility_warnings=warnings,
        observed_context={'incidence_for_this_baseline': incidence,
                          'grade_3_4_overall_percent': observed['grade_3_4_incidence']['value_percent'],
                          'any_grade_percent': observed['any_grade_incidence']['value_percent'],
                          'illustrative_average_individual_nadir_1e9_per_l': illustrative_nadir,
                          'illustrative_note': observed['mean_individual_reduction']['use']},
        model_report_sha256=curves['report_sha256'], model_reading=copy.deepcopy(curves['reading']),
        limitations=[
            'A typical curve for a hypothetical course of the studied regimen (1.3 mg/m2, days 1, 4, 8, 11 of 21-day cycles); no dose holds or reductions.',
            'The typical curve dips less than individual patients do: in the source, the average patient fell about 60% from their own start, while the typical curves fall about 30-47%.',
            'Grades are shown as reference lines. Where the typical curve sits is not this patient\'s grade or risk; the observed incidence by baseline is the better guide to risk.',
            'The model was fitted to mean data from the same study; it has no between-patient spread and no external validation.',
            *curves['limitations']])
    report['report_sha256'] = digest(report)
    return report
