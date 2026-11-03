"""What a saved synthetic record can show, grouped by question, with a status before anything is opened.

Layout step 3 (3 November 2026). For each result that runs on a patient-state record, this module reads the same
scope checks and evidence statuses the result pages use, and reports one status per result:

- checked:          in scope, and every rule that applies has an outside check that agreed;
- within_data:      in scope, inside the data the model was fitted to, but not checked against outside data here;
- partly_checked:   consistent with outside data in the primary scenario only;
- flagged:          in scope, but an outside check disagrees here (the result page shows the warning);
- calibrated:       at the calibration point of the model (normal kidney function for the pathway model);
- needs_input:      the record lacks something the model needs (named);
- not_available:    outside what the model covers; the page refuses to compute.

Nothing is calculated here beyond the scope checks and the pathway band; no curve, exposure or risk is produced.
The disease rule of the population PK models is not used: disease is declared on each calculation page, not stored on
the record.
"""
import copy

STATUS_TEXT = {
    'checked': 'Checked: outside data agree in this range',
    'within_data': 'Within the model\'s data; not checked against outside data here',
    'partly_checked': 'Consistent with outside data in the primary scenario only',
    'flagged': 'Outside check disagrees here; the page shows the warning',
    'calibrated': 'At the model\'s calibration point',
    'needs_input': 'Needs more information on this record',
    'not_available': 'Outside what the model covers; not computed',
}
STATUS_LABEL = {
    'checked': 'Checked', 'within_data': 'Within model data', 'partly_checked': 'Partly checked', 'flagged': 'Flagged',
    'calibrated': 'Calibrated', 'needs_input': 'Needs input', 'not_available': 'Not available',
}
QUESTIONS = [
    ('exposure', 'How much drug is in the blood?'),
    ('elimination', 'Where does the drug leave the body?'),
    ('blood_counts', 'What happens to blood counts?'),
]
IGNORED_RULES = ('disease',)


def _first_sentence(text):
    """The first sentence of a scope reason; the rest refers to data shown on the result page itself."""
    if not text:
        return 'outside the model scope.'
    head = text.split('. ')[0].rstrip('.')
    return head + '.'


def _from_scope(evaluation):
    """Status and detail from a model-scope evaluation, leaving out rules declared elsewhere."""
    rows = [r for r in evaluation['rules'] if r['id'] not in IGNORED_RULES]
    outside = [r for r in rows if r['status'] == 'out_of_scope']
    unknown = [r for r in rows if r['status'] == 'cannot_determine']
    if outside:
        return 'not_available', '; '.join(f"{r['id'].replace('_', ' ')}: {_first_sentence(r.get('reason'))}" for r in outside)
    if unknown:
        return 'needs_input', 'Missing: ' + ', '.join(r['id'].replace('_', ' ') for r in unknown)
    tiers = [r.get('tier') for r in rows if r['status'] == 'in_scope']
    if 'external_check_disagrees' in tiers:
        flagged = [r['id'].replace('_', ' ') for r in rows if r.get('tier') == 'external_check_disagrees']
        return 'flagged', 'Outside check disagrees for: ' + ', '.join(flagged)
    if 'inside_model_data' in tiers:
        return 'within_data', None
    return 'checked', None


BAND_STATUS = {'calibrated': 'calibrated', 'checked_consistent': 'checked',
               'consistent_primary_only': 'partly_checked', 'check_disagrees': 'flagged'}


def record_results(revision_id):
    """Results for one saved revision: [{'id', 'question', 'items': [...]}], items with status and endpoint."""
    from .bortezomib_patient_platelets import platelet_scope
    from .body_map import record_map
    from .estimated_pk import primary_weight_basis
    from .lenalidomide_scope import hughes_scope, kim_scope
    from .patient_state_revisions import read_revision

    revision = read_revision(revision_id)
    if revision is None:
        raise ValueError('Saved patient-state revision does not exist.')
    state = revision.payload['state']
    items = {key: [] for key, _ in QUESTIONS}

    def add(question, title, drug, status, detail, endpoint):
        items[question].append({'title': title, 'drug': drug, 'status': status, 'status_label': STATUS_LABEL[status],
                                'status_text': STATUS_TEXT[status],
                                'detail': detail, 'endpoint': endpoint})

    for title, scope in (('Typical concentration curve (Hughes 2019)',
                          hughes_scope(copy.deepcopy(state), primary_weight_basis(), 'UNKNOWN')),
                         ('Typical concentration curve in renal impairment (Kim 2026)',
                          kim_scope(copy.deepcopy(state), 'UNKNOWN'))):
        status, detail = _from_scope(scope['scope_evaluation'])
        add('exposure', title, 'Lenalidomide', status, detail, 'landscape.educational_pk')

    view = record_map(revision_id)
    if view['status'] == 'completed':
        status = BAND_STATUS[view['band']['status']]
        detail = f"Creatinine clearance {view['crcl_ml_min']:.0f} mL/min ({view['band']['id']} kidney function)."
    elif view['status'] == 'outside_range':
        status, detail = 'not_available', view['message']
    else:
        status, detail = 'needs_input', view.get('message')
    add('elimination', 'Elimination pathways', 'Lenalidomide', status, detail, 'landscape.patient_renal_pathways_page')
    add('elimination', 'Body map (3D)', 'Lenalidomide', status, detail, 'landscape.patient_body_map')

    status, detail = _from_scope(platelet_scope(copy.deepcopy(state))['scope_evaluation'])
    add('blood_counts', 'Platelet time course (Lignet 2022)', 'Bortezomib', status, detail,
        'landscape.patient_bortezomib_platelets')

    return [{'id': key, 'question': question, 'items': items[key]} for key, question in QUESTIONS]
