"""The evidence-state ladder for pinned extracts (plan docs/EVIDENCE_CONNECTIONS_PLAN.md, update 3).

Each extract that is in a review queue gets exactly one state from what the review records say:
- extracted: taken from a source (quotes matched by script where checked), not yet fully reviewed;
- reviewed_by_owner: every value the platform uses from it was checked against the source by the owner and matched;
- agreed_by_two_extractions: a second, independent extraction agreed and the sampled owner check found no error
  (Track B; no file has this state until that review is recorded).
Separately, and never in place of those: whether a model using the extract has a locked check against outside data. That
describes the model, not the value. AI reviews (for example the review of 10 November 2026) are not review records and
never change a state.
"""
from . import dataset_ledger as dl
from . import evidence_index as ei
from . import extraction_review as er

STATES = ('extracted', 'reviewed_by_owner', 'agreed_by_two_extractions')
LABELS = {'extracted': 'Extracted', 'reviewed_by_owner': 'Reviewed by the owner',
          'agreed_by_two_extractions': 'Agreed by two extractions, sampled'}
OUTSIDE_DATA_ROLES = ('checked_blind', 'checked_blind_with_deviation', 'checked_not_blind')
DOUBLE_EXTRACTION_RECORDS = ()      # Track B: pinned records of agreed-and-sampled entries, added when that review runs


def _queue_groups():
    return [g for v in (er.queue_view(), er.queue_view(queue_name='round_3')) for g in v['groups']]


def _checked_models():
    return sorted({u['model'] for u in dl.load_ledger()['uses'] if u['role'] in OUTSIDE_DATA_ROLES})


def states():
    checked = set(_checked_models())
    out = {}
    for group in _queue_groups():
        status = er._file_status(group)
        state = 'reviewed_by_owner' if status['all_match'] else 'extracted'
        try:
            models = ei.view(group['file'])['depends_on_it']['models']
        except KeyError:
            models = []
        entry = out.setdefault(group['file'], {'file': group['file'], 'state': state, 'label': LABELS[state],
                                               'owner_review': status['text'], 'counts': status['counts'],
                                               'models_checked_against_outside_data': sorted(set(models) & checked),
                                               'models_not_checked': sorted(set(models) - checked)})
        if state != entry['state']:                     # the same file in two queues: the weaker state wins
            entry.update(state='extracted', label=LABELS['extracted'])
    return out


def state_of(file):
    return states().get(file)
