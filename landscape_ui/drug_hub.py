"""Drug hub: everything Marlo has for one drug, gathered on its drug page (layout step 2, 3 November 2026).

The links are built from what the platform already records, not from a hand-kept list per drug: special-population
summaries, model scorecards, label-based exposure curves and registered research tools. A few drug-specific pages
(the lenalidomide guide, dose view and evidence pages) are listed by name. A link appears only when its page exists in
the running app and its data verified; nothing is promised that cannot be opened.
"""
from flask import url_for
from werkzeug.routing import BuildError

# Drug-specific pages that are not yet registered anywhere else. (group, title, endpoint, kwargs, note)
NAMED_PAGES = {
    'lenalidomide': [
        ('guide', 'Guided path', 'landscape.lenalidomide_guide', {}, 'From the label to the models and their checks, step by step.'),
        ('guide', 'Dose view', 'landscape.lenalidomide_dose_optimisation', {}, 'Label dose steps beside typical exposure from the checked models.'),
        ('evidence', 'Published renal PK evidence', 'landscape.renal_pk_evidence', {}, 'Observed group values from the renal-impairment study.'),
        ('evidence', 'Mechanism evidence', 'landscape.mechanism_map_demo', {}, 'Qualitative mechanism map with its sources.'),
    ],
    'ixazomib': [
        ('tools', 'Typical exposure (Gupta 2017)', 'landscape.ixazomib_exposure_page', {}, 'Population PK curves within the model\'s scope.'),
    ],
}
# Results that run on a saved synthetic patient record (opened from the record, not from here).
RECORD_TOOLS = {
    'lenalidomide': ['Educational PK (Hughes 2019, Kim 2026)', 'Elimination pathways', 'Body map (3D)', 'Relative odds of low blood counts'],
    'bortezomib': ['Platelet time course (Lignet 2022)'],
}
GROUPS = [
    ('guide', 'Guides and dosing'),
    ('label', 'Label and special populations'),
    ('models', 'Models and their checks'),
    ('tools', 'Exposure and effect tools'),
    ('evidence', 'Evidence'),
    ('patients', 'On synthetic patients'),
]


def _url(endpoint, **kwargs):
    try:
        return url_for(endpoint, **kwargs)
    except BuildError:
        return None


def hub_links(entity_id, label, cohort_id=None):
    """Groups of links for one drug: [{'id', 'title', 'links': [{'title', 'url', 'note'}]}], empty groups left out."""
    from intelligence_store import label_exposure_view, special_populations
    from intelligence_store.drug_research_tools import research_tool_registry
    from intelligence_store.model_scorecards import all_scorecards

    items = {key: [] for key, _ in GROUPS}

    def add(group, title, url, note):
        if url:
            items[group].append({'title': title, 'url': url, 'note': note})

    for group, title, endpoint, kwargs, note in NAMED_PAGES.get(entity_id, []):
        add(group, title, _url(endpoint, **kwargs), note)
    if entity_id in special_populations.available():
        add('label', 'Special populations', _url('landscape.special_populations', drug=entity_id),
            'What the label says for kidney and liver impairment, age and other groups, with sources.')
    for card in all_scorecards()['cards']:
        if card['drug'].casefold() == label.casefold():
            checks = len(card['outside_data_disagreements'])
            add('models', card['name'], _url('model_scorecard', model_id=card['model_id']),
                f"{card['kind']}. " + (f"{checks} recorded disagreement{'s' if checks != 1 else ''} with outside data."
                                       if checks else 'No recorded disagreement with outside data.'))
    if entity_id in label_exposure_view.available():
        add('tools', 'Label-based exposure', _url('landscape.label_exposure', drug=entity_id),
            'Typical curve from the label\'s own PK values, after its locked checks.')
    for tool in research_tool_registry().get(entity_id, []):
        if tool['availability'] == 'available' and tool['endpoint']:
            add('tools', tool['title'], _url(tool['endpoint']), tool['scope'])
    if entity_id in RECORD_TOOLS:
        add('patients', 'Synthetic patients', _url('landscape.patient_directory', cohort_id=cohort_id),
            'Open a saved synthetic record to run: ' + '; '.join(RECORD_TOOLS[entity_id]) + '.')
    return [{'id': key, 'title': title, 'links': items[key]} for key, title in GROUPS if items[key]]
