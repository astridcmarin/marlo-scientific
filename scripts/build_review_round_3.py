"""Build the extraction review queue for round 3 (5 November 2026).

Round 3 covers values extracted after round 2, which feed no calculation but are shown on pages: the five label
extracts of 4 November, the FDA 2024 renal guidance extract and the rest of REVLIMID sections 12.3 and 7. One item per
label entry (its structured values, with the quoted sentence it came from), so the owner checks each against the
source at the stated location. Run from the repository root; writes intelligence_store/data/extraction_review_queue_round3_v2.json (v2 adds the FDA
2026 draft hepatic guidance extract; v1 is kept unchanged).
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'intelligence_store' / 'data'
OUT = DATA / 'extraction_review_queue_round3_v2.json'
LABELS = ('carfilzomib', 'selinexor', 'thalidomide', 'isatuximab', 'elotuzumab')
SECTIONS = ('dosing', 'pk', 'special_populations', 'interactions')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quotes_of(node):
    return [v for k, v in node.items() if k.endswith('quote') and isinstance(v, str)]


def label_groups():
    groups = []
    for drug in LABELS:
        path = DATA / f'label_extract_{drug}_v1.json'
        doc = json.loads(path.read_text())
        items = []
        for section in SECTIONS:
            for key, entry in doc[section].items():
                items.append({'id': f'label_{drug}:/{section}/{key}', 'label': f"{section.replace('_', ' ')}: {key.replace('_', ' ')}",
                              'pointer': f'/{section}/{key}', 'value': entry, 'location': entry['location'],
                              'where_to_look': entry['location'],
                              'how_stored': 'the label sentence it comes from: “' + ' … '.join(quotes_of(entry)) + '”'})
        groups.append({'id': f'label_{drug}', 'priority': 1, 'file': f'intelligence_store/data/{path.name}', 'sha256': sha(path),
                       'where_to_look': doc['source']['document'] + ', revised ' + doc['source']['revised'],
                       'used_by': 'Label extract shown with the drug (no calculation yet; label-curve plans wait for this review)',
                       'items': items})
    return groups


def fda_group():
    path = DATA / 'fda_renal_impairment_guidance_2024_v1.json'
    doc = json.loads(path.read_text())
    items = []
    for i, cat in enumerate(doc['table_1']['categories']):
        items.append({'id': f'fda_renal_2024:/table_1/categories/{i}', 'label': f"Table 1: {cat['description']}",
                      'pointer': f'/table_1/categories/{i}', 'value': cat, 'location': doc['table_1']['location'],
                      'where_to_look': f"{doc['table_1']['location']}, Table 1, row “{cat['description']}”",
                      'how_stored': f"printed range as returned by the text layer: {cat['printed']}; read as {doc['table_1']['range_reading']}"})
    items.append({'id': 'fda_renal_2024:/table_1/footnotes/c', 'label': 'Table 1, footnote c', 'pointer': '/table_1/footnotes/c',
                  'value': doc['table_1']['footnotes']['c'], 'location': doc['table_1']['location'],
                  'where_to_look': f"{doc['table_1']['location']}, Table 1 footnote c", 'how_stored': 'quoted as returned by the text layer'})
    for key, q in doc['renal_function_measure'].items():
        items.append({'id': f'fda_renal_2024:/renal_function_measure/{key}/quote', 'label': key.replace('_', ' '),
                      'pointer': f'/renal_function_measure/{key}/quote', 'value': q['quote'], 'location': q['location'],
                      'where_to_look': q['location'], 'how_stored': 'quoted as returned by the text layer'})
    return {'id': 'fda_renal_2024', 'priority': 1, 'file': f'intelligence_store/data/{path.name}', 'sha256': sha(path),
            'where_to_look': f"{doc['source']['title']}, {doc['source']['date']} ({doc['source']['url']}); the PDF is not in the owner's folder yet",
            'used_by': 'Kidney-function classifications on the lenalidomide special-populations page and the body map',
            'items': items}


def fda_hepatic_group():
    path = DATA / 'fda_hepatic_impairment_guidance_2026_draft_v1.json'
    doc = json.loads(path.read_text())
    items = []
    for key, q in doc['recommendations'].items():
        items.append({'id': f'fda_hepatic_2026:/recommendations/{key}/quote', 'label': key.replace('_', ' '),
                      'pointer': f'/recommendations/{key}/quote', 'value': q['quote'], 'location': q['location'],
                      'where_to_look': q['location'], 'how_stored': 'quoted as returned by the text layer'})
    for table, key in (('child_pugh_table_1', 'groups'), ('nci_odwg_table_2', 'groups')):
        for i, grp in enumerate(doc[table][key]):
            items.append({'id': f'fda_hepatic_2026:/{table}/{key}/{i}', 'label': f"{doc[table]['location']}: group {grp['id']}",
                          'pointer': f'/{table}/{key}/{i}', 'value': grp, 'location': doc[table]['location'],
                          'where_to_look': doc[table]['location'], 'how_stored': doc[table]['reading']})
    return {'id': 'fda_hepatic_2026', 'priority': 1, 'file': f'intelligence_store/data/{path.name}', 'sha256': sha(path),
            'where_to_look': f"{doc['source']['title']}, {doc['source']['date']}, {doc['source']['status']} ({doc['source']['url']}); the PDF is not in the owner's folder yet",
            'used_by': 'Liver-function classifications on the lenalidomide special-populations page',
            'items': items}


def revlimid_pk_group():
    path = DATA / 'lenalidomide_label_2023_pk_v1.json'
    doc = json.loads(path.read_text())
    items = []

    def walk(node, pointer, inherited_location):
        location = node.get('location', inherited_location)
        if quotes_of(node):
            items.append({'id': f'lenalidomide_label_pk:{pointer}', 'label': pointer.strip('/').replace('/', ': ').replace('_', ' '),
                          'pointer': pointer, 'value': node, 'location': location, 'where_to_look': location,
                          'how_stored': 'quotes matched by script against the label text; numbers transcribed from them'})
            return
        for k, v in node.items():
            if isinstance(v, dict):
                walk(v, f'{pointer}/{k}', location)

    for block in ('absorption', 'distribution', 'elimination', 'renal_dialysis', 'drug_interactions_12_3', 'drug_interactions_7'):
        walk(doc[block], f'/{block}', None)
    return {'id': 'lenalidomide_label_pk', 'priority': 1, 'file': f'intelligence_store/data/{path.name}', 'sha256': sha(path),
            'where_to_look': doc['source']['document'] + ' (the same PDF as round 1 and 2)',
            'used_by': 'Label pharmacokinetics and interactions on the lenalidomide special-populations page and guided path',
            'items': items}


def build():
    groups = [revlimid_pk_group(), fda_group(), fda_hepatic_group()] + label_groups()
    return {'schema_version': 'extraction-review-queue-v1', 'queue_version': 'extraction-review-queue-round3-v2.0',
            'recorded_on': '2026-11-05', 'round': 3,
            'purpose': 'Values extracted after round 2 that are shown on pages but feed no calculation: the rest of the REVLIMID '
                       'pharmacokinetics and interactions sections, the FDA 2024 renal guidance categories, the five label '
                       'extracts of 4 November and the FDA 2026 draft hepatic guidance. Each item is one entry: check its values against the source at the stated location.',
            'excluded': 'Quotes were already matched by script against each source\'s text; this round checks the structured values '
                        'and that each quote is the right sentence at the right place.',
            'decisions': {'matches': 'The value matches the source at the stated location.',
                          'wrong': 'The value does not match the source (note what the source says).',
                          'cannot_check': 'The source or location could not be checked.'},
            'groups': groups}


if __name__ == '__main__':
    OUT.write_text(json.dumps(build(), indent=1, ensure_ascii=False) + '\n')
    queue = json.loads(OUT.read_text())
    print(OUT.relative_to(ROOT), sha(OUT), sum(len(g['items']) for g in queue['groups']), 'items',
          [(g['id'], len(g['items'])) for g in queue['groups']])
