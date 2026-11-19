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
        ('guide', 'Dose view', 'landscape.lenalidomide_dose_optimisation', {}, 'Label dose steps beside typical exposure from the two population models, with their check results.'),
        ('tools', 'Body map explorer', 'landscape.body_map_explorer', {}, 'Where the drug leaves the body at a chosen kidney function, in 3D, beside what the renal-impairment study observed.'),
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
    ('findings', 'What the checks found'),
    ('holdings', 'Sources the platform holds'),
    ('regulatory', 'Regulatory documents'),
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

    def add(group, title, url, note, plain=False):
        if url or plain:
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
    # Every locked check on this drug's models, failures included (evidence-first plan, item 4, 18 November 2026).
    # A findings file that fails its checksum leaves the group out rather than breaking the drug page.
    from intelligence_store.check_findings import FindingsError, findings_for_drug
    try:
        rows = findings_for_drug(entity_id)
    except (FindingsError, ValueError, OSError):
        rows = []
    findings_url = _url('check_findings')
    for r in rows:
        add('findings', r['question'], findings_url and f"{findings_url}#{r['id']}", f"{r['outcome_label']}.")
    # What the platform holds and the regulatory documents among it (evidence-first plan, items 6 and 7, 19 November 2026).
    # Computed from the dataset ledger and the special-population summaries; unread sources by title only.
    from intelligence_store.drug_holdings import holdings, state_summary
    try:
        held = holdings(entity_id)
    except (ValueError, OSError, KeyError):
        held = None
    if held:
        def evidence_url(row):
            return row['files'] and _url('evidence_index_file', file=row['files'][0]['file'])
        for row in held['read']:
            add('holdings', row['title'], evidence_url(row), state_summary(row), plain=True)
        for row in held['held_unread']:
            add('holdings', row['title'], None, 'Held unread for a planned blind check: its values have not been read.', plain=True)
        cat = held['catalogue_label']
        if cat and cat.get('url'):
            add('regulatory', f"{cat['title'] or 'Product label'} (DailyMed, version {cat['label_version']})", cat['url'],
                f"The drug catalogue's names, mechanism, warnings and interactions; checked on {cat['verified_on']}.")
        for row in held['regulatory']:
            add('regulatory', row['title'], evidence_url(row), f"{row['regulatory_kind']}. {state_summary(row)}", plain=True)
        for row in held['regulatory_held_unread']:
            add('regulatory', row['title'], None, f"{row['regulatory_kind']}, held unread for a planned blind check.", plain=True)
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
