"""Phase 1.2: one capability level per drug, so a user always knows what kind of evidence stands behind a page.

The level is derived, never typed in: from the curated reference catalogs (is anything curated for this drug?) and
from the model scorecards (which registered models exist for it, and has any been compared with outside data?).
A higher level is not a better drug or a safer answer; it only says how much modelling evidence the platform holds.
"""
from .model_scorecards import all_scorecards

LEVELS = (
    {'id': 'identity_only', 'rank': 0, 'label': 'Identity only',
     'meaning': 'Names and aliases are curated; no mechanism, safety or interaction reference is curated yet.'},
    {'id': 'knowledge_only', 'rank': 1, 'label': 'Knowledge only',
     'meaning': 'Curated reference information (mechanism, safety or interactions). No exposure or effect model.'},
    {'id': 'label_based_exposure', 'rank': 2, 'label': 'Label-based exposure',
     'meaning': 'A typical-value exposure curve from the product label\'s own parameters. Not a population model.'},
    {'id': 'published_model', 'rank': 3, 'label': 'Published model',
     'meaning': 'At least one published exposure or effect model is implemented, with its scorecard.'},
    {'id': 'published_model_checked', 'rank': 4, 'label': 'Published model, checked against outside data',
     'meaning': 'At least one published model has been compared with data not used to fit it. The comparison can disagree.'},
)
BY_ID = {level['id']: level for level in LEVELS}
CHECKED = ('done', 'done_exploratory')


def drug_level(canonical_name, has_curated_reference, scorecards=None):
    cards = [c for c in (scorecards or all_scorecards())['cards'] if c['drug'].casefold() == canonical_name.casefold()]
    checked = [c for c in cards if c['layers'][-1]['id'] == 'external_consistency' and c['layers'][-1]['status'] in CHECKED]
    # Label-based exposure is reserved for Phase 3.1; no such engine is installed, so the level is never assigned yet.
    level = ('published_model_checked' if checked else 'published_model' if cards else
             'knowledge_only' if has_curated_reference else 'identity_only')
    disagreements = sum(len(c['outside_data_disagreements']) for c in cards)
    return dict(BY_ID[level],
                models=[{'model_id': c['model_id'], 'name': c['name'], 'kind': c['kind'],
                         'disagreements': len(c['outside_data_disagreements'])} for c in cards],
                outside_data_disagreements=disagreements,
                note=(f'{disagreements} recorded disagreement{"s" if disagreements != 1 else ""} with outside data; see the scorecards.'
                      if disagreements else None))
