"""Phase 4.3: lenalidomide dose-optimisation view (docs/DOSE_OPTIMISATION.md).

For one synthetic patient, the typical daily lenalidomide exposure at each dose level under the two published models,
inside each model's scope (Phase 2.5) and at that model's own study doses only, as a ratio to the measured 25 mg
reference, with the relative odds of grade 3/4 cytopenia from the published exposure-safety odds ratios (Simulation
4.0a). Also the corpus trials that test lenalidomide, by phase and status. Nothing is fitted here, and no dose is
recommended or ranked.

Dose levels come from the models' sources, not from the platform: the Hughes 2019 listed study amounts up to the
reference dose (hughes_coverage_contract_v1.json) and the Kim 2026 study doses (kim_model.STUDY_DOSES_MG).
"""
import collections
import hashlib
import json
import math
from pathlib import Path

from .covariate_estimation import estimate_hughes_covariates, primary_weight_basis_hughes
from .eligibility_corpus import load_corpus
from .estimated_pk import _clearance_variability, scope_summary
from .intervention_names import name_key
from .kim_model import STUDY_DOSES_MG as KIM_DOSES, estimate_kim_covariates, primary_cl_form, typical_parameters
from .lenalidomide_relative_odds import ENDPOINTS, relative_odds_for_exposure
from .lenalidomide_scope import hughes_scope, kim_scope
from .model_coverage import load_coverage_contract
from .patient_state import digest, validate_patient_state
from .pk_parameter_reference import _parameter_math, load_parameter_extract
from .reference_exposure import compare_to_reference, load_reference_exposure

SCHEMA_VERSION = 'lenalidomide-dose-view-v1'
METHOD_VERSION = 'lenalidomide-dose-view-v1.1'
EXPOSURE_RESPONSE_PATH = Path(__file__).parent / 'data' / 'lenalidomide_exposure_response_guglieri_2017_v1.json'
EXPOSURE_RESPONSE_SHA256 = '676a2b8ff2f0d0d668e62105918ea28b6358cce0f745b72c2fafb4fd0efb6eb5'
ALIASES = ('Lenalidomide', 'Revlimid')       # drug_aliases_v1.json entry 'lenalidomide' (checked in a test)
MODELS = {'lenalidomide_hughes_2019': 'Hughes 2019', 'lenalidomide_kim_2026': 'Kim 2026'}
DOSE_STATUS = {
    'study_dose': "One of the model's study doses",
    'inside_range_not_listed': "Inside the model's dose range but not a listed study dose (coverage flag)",
    'not_a_study_dose': "Not a dose in the model's study: no value",
}
GAPS = [
    {'id': 'exposure_efficacy', 'text': 'A usable exposure–efficacy relationship: none found. The FDA review of the first approval (MDS) states none was studied; the one myeloma analysis found (below) is shown but not used. Without one, the view cannot show a trade-off between dose levels.'},
    {'id': 'label_dose_reductions', 'text': 'Label dose levels and renal dose reductions: not extracted.'},
    {'id': 'combination_regimens', 'text': 'Exposure–safety in combination regimens (with dexamethasone, bortezomib or daratumumab): the odds ratios come from monotherapy only.'},
    {'id': 'trial_dose_levels', 'text': 'Dose levels used in the trials: the pinned corpus holds intervention names, not arm descriptions or doses (owner decision, 30 October 2026).'},
]
LIMITS = [
    'Both models are linear, so for one patient each dose row is the reference-dose row scaled by the dose ratio. '
    "The models add the effect of the patient's kidney function and body size, not of dose.",
    'The doses and AUC range in the exposure–safety analysis were not reported, so the odds ratios may not hold at '
    'every dose shown, particularly the lowest.',
    'Relative odds are not probabilities: the intercept was not published, so absolute risk is unknown.',
    'Typical values for a synthetic record; not this or any patient\'s exposure, and not a dose recommendation.',
]


def load_exposure_response():
    raw = EXPOSURE_RESPONSE_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPOSURE_RESPONSE_SHA256:
        raise ValueError('Lenalidomide exposure-response evidence is missing or changed.')
    data = json.loads(raw)
    if data.get('schema_version') != 'exposure-response-evidence-v1':
        raise ValueError('Unsupported exposure-response evidence schema.')
    return data


def published_exposure_response():
    """The thesis findings, for display only: nothing here enters a calculation."""
    e = load_exposure_response()
    return {'kind': 'cited_finding_not_used_in_calculation', 'source': e['source']['document'],
            'source_status': e['source']['publication_status'], 'extraction': e['source']['extraction'],
            'design': {k: e['design'][k] for k in ('setting', 'population', 'n_patients', 'pk_sampled_patients', 'exposure_definition')},
            'time_to_progression': {k: e['time_to_progression'][k] for k in ('events', 'hazard_ratios', 'direction', 'quotes', 'location')},
            'time_to_severe_neutropenia': {k: e['time_to_severe_neutropenia'][k] for k in ('events', 'hazard_ratios', 'auc_tested_not_retained', 'location')},
            'why_not_used': e['platform_assessment']['reasons'], 'not_this': e['not_this'],
            'evidence_version': e['evidence_version'], 'evidence_sha256': EXPOSURE_RESPONSE_SHA256}


def dose_levels():
    """Hughes listed amounts up to the reference dose, plus the Kim study doses."""
    ref = load_reference_exposure()['reference']['dose_mg']
    listed = [float(a) for a in load_coverage_contract()['listed_amounts_mg'] if a <= ref]
    return sorted(set(listed) | {float(d) for d in KIM_DOSES})


def dose_status(model_id, dose):
    if model_id == 'lenalidomide_kim_2026':
        return 'study_dose' if dose in KIM_DOSES else 'not_a_study_dose'
    contract = load_coverage_contract()
    lo, hi = contract['amount_range_mg']
    if any(math.isclose(dose, a, rel_tol=0, abs_tol=1e-12) for a in contract['listed_amounts_mg']):
        return 'study_dose'
    return 'inside_range_not_listed' if lo <= dose <= hi else 'not_a_study_dose'


def _typical_cl(model_id, state, weight_basis, cl_form):
    if model_id == 'lenalidomide_hughes_2019':
        est = estimate_hughes_covariates(state, weight_basis)
        if est['status'] != 'estimated':
            return None, est
        e = est['estimates']
        cl = _parameter_math(e['fat_free_mass']['value'], e['creatinine_clearance']['value'],
                             load_parameter_extract()['parameters'])['apparent_clearance_l_h']
        return cl, est
    est = estimate_kim_covariates(state)
    if est['status'] != 'estimated':
        return None, est
    e = est['estimates']
    return typical_parameters(e['egfr_indexed']['value'], e['body_surface_area']['value'], cl_form)['total_clearance_l_h'], est


def _model_column(model_id, state, disease_code, weight_basis, cl_form, doses):
    scope = (hughes_scope(state, weight_basis, disease_code) if model_id == 'lenalidomide_hughes_2019'
             else kim_scope(state, disease_code))
    ev = scope['scope_evaluation']
    col = {'model': model_id, 'label': MODELS[model_id], 'scope': scope_summary(scope),
           'scope_result_sha256': scope['result_sha256'], 'computed': False, 'cells': []}
    col['assumption'] = ({'weight_basis': weight_basis} if model_id == 'lenalidomide_hughes_2019' else {'cl_form': cl_form})
    if ev['status'] != 'in_scope':
        col['reason'] = 'Outside the model scope or not determinable; no value is computed.'
        return col
    cl, est = _typical_cl(model_id, state, weight_basis, cl_form)
    if cl is None:
        col['reason'] = 'Missing estimator inputs: ' + ', '.join(est['missing_fields'])
        return col
    variability = _clearance_variability(model_id)
    col.update(computed=True, tier=ev['weakest_rule_tier'], typical_total_cl_f_l_h=cl,
               covariates={k: v['value'] for k, v in est['estimates'].items()}, warnings=list(est['warnings']),
               covariate_estimate_sha256=est['report_sha256'], variability=variability)
    for dose in doses:
        status = dose_status(model_id, dose)
        cell = {'dose_mg': dose, 'dose_status': status}
        if status != 'not_a_study_dose':
            ref = compare_to_reference(dose, cl)
            odds = relative_odds_for_exposure(ref['ratio_to_reference'], variability=variability)
            cell.update(typical_daily_auc_ng_h_ml=ref['typical_daily_auc_ng_h_ml'], ratio_to_reference=ref['ratio_to_reference'],
                        relative_odds={k: {'relative_odds': v['relative_odds'], 'ci95': v['ci95'],
                                           'between_patient_90': [v['between_patient_90']['p05'], v['between_patient_90']['p95']],
                                           'statistically_significant': v['statistically_significant']}
                                       for k, v in odds['endpoints'].items()})
        col['cells'].append(cell)
    return col


PHASE_LABELS = {'EARLY_PHASE1': 'Early phase 1', 'PHASE1': 'Phase 1', 'PHASE2': 'Phase 2', 'PHASE3': 'Phase 3',
                'PHASE4': 'Phase 4', 'NA': 'Not applicable'}


def phase_label(phases):
    return ' / '.join(PHASE_LABELS.get(p, p) for p in phases) or 'Not stated'


def corpus_trials():
    """Corpus trials with an intervention named exactly Lenalidomide or Revlimid (the alias catalog's rule), by phase
    and status. Names that only mention lenalidomide (combinations, dose wording) are counted separately, not matched."""
    corpus = load_corpus()
    keys = {name_key(a) for a in ALIASES}
    matched, mention = [], []
    for t in corpus['trials']:
        names = [i['name'] for i in t['interventions']]
        if any(name_key(n) in keys for n in names):
            matched.append(t)
        elif any(any(a.casefold() in n.casefold() for a in ALIASES) for n in names):
            mention.append(t)
    phase = collections.Counter(phase_label(t['phases']) for t in matched)
    status = collections.Counter(t['overall_status'] for t in matched)
    early = sorted((t for t in matched if set(t['phases']) & {'EARLY_PHASE1', 'PHASE1'}), key=lambda t: t['nct_id'])
    return {'method': 'Exact intervention-name match to the alias catalog entry (Lenalidomide, Revlimid).',
            'corpus_sha256': corpus['corpus_sha256'], 'corpus_trials': corpus['counts']['trials'],
            'cohort': corpus['cohort']['condition'] + ', interventional', 'retrieved': corpus['cohort']['finished_at_utc'],
            'matched': len(matched), 'mention_only_not_matched': len(mention),
            'by_phase': sorted(phase.items(), key=lambda kv: -kv[1]), 'by_status': sorted(status.items(), key=lambda kv: -kv[1]),
            'phase_1_trials': [{'nct_id': t['nct_id'], 'title': t['brief_title'], 'phases': t['phases'], 'phase_label': phase_label(t['phases']),
                                'status': t['overall_status'], 'enrollment': (t.get('enrollment') or {}).get('count')}
                               for t in early]}


def lenalidomide_dose_view(state, disease_code, weight_basis=None, cl_form=None):
    state = validate_patient_state(state)
    weight_basis = weight_basis or primary_weight_basis_hughes()
    cl_form = cl_form or primary_cl_form()
    doses = dose_levels()
    ref = load_reference_exposure()['reference']
    result = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'drug': 'lenalidomide',
              'state_sha256': digest(state), 'disease_code': disease_code, 'dose_levels_mg': doses,
              'dose_levels_source': 'Hughes 2019 listed study amounts up to the reference dose, plus the Kim 2026 study doses.',
              'reference': {'dose_mg': ref['dose_mg'], 'auc_ng_h_ml': ref['value'], 'sd': ref['sd'], 'n': ref['n'],
                            'population': ref['population']},
              'endpoints': list(ENDPOINTS),
              'models': [_model_column(m, state, disease_code, weight_basis, cl_form, doses) for m in MODELS],
              'trials': corpus_trials(), 'published_exposure_response': published_exposure_response(), 'gaps': GAPS, 'limits': LIMITS,
              'not_this': 'Not dosing guidance: no dose is recommended or ranked.',
              'clinical_prediction_validated': False, 'ready_for_patient_simulation': False}
    result['result_sha256'] = digest(result)
    return result
