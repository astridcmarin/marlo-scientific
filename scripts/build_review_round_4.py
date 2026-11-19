"""Build the extraction review queue for round 4 (19 November 2026): the ixazomib entries of drug catalogue v2.

Drug catalogue v2 (18 November 2026) added ixazomib to the four linked catalogues (names, mechanism, safety,
interactions) from the NINLARO DailyMed SPL, set 038f2461-834b-4488-9ebd-863c83eef5a7, version 18. The entries are
AI-written summaries, not quotes, so nothing was matched by script: the owner checks each one against the label at the
stated sections. One item per entry. Round 4 is its own queue so that round 3 records, including drafts in progress,
are not affected. Run from the repository root; writes intelligence_store/data/extraction_review_queue_round4_v1.json.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'intelligence_store' / 'data'
OUT = DATA / 'extraction_review_queue_round4_v1.json'
LABEL = ('NINLARO (ixazomib) prescribing information, DailyMed SPL set 038f2461-834b-4488-9ebd-863c83eef5a7, version 18, '
         'effective 11 August 2026 (supplemental-information/drug-labels, the NINLARO PDF and ZIP)')
SUMMARY = 'AI-written summary of the label at these sections, not a quote: check that it says what the label says'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ixazomib_entry(name):
    path = DATA / f'{name}_v2.json'
    doc = json.loads(path.read_text())
    index = next(i for i, e in enumerate(doc['entries']) if (e.get('id') or e.get('entity_id')) == 'ixazomib')
    return path, doc['entries'][index], f'/entries/{index}'


def sections(node):
    return ', '.join(node['sections'])


def group(gid, name, used_by, items):
    path, _, _ = ixazomib_entry(name)
    return {'id': gid, 'priority': 1, 'file': f'intelligence_store/data/{path.name}', 'sha256': sha(path),
            'where_to_look': LABEL, 'used_by': used_by, 'items': items}


def item(gid, pointer, label, value, location, how_stored):
    return {'id': f'{gid}:{pointer}', 'label': label, 'pointer': pointer, 'value': value, 'location': location,
            'where_to_look': location, 'how_stored': how_stored}


def names_group():
    _, entry, base = ixazomib_entry('drug_aliases')
    items = [item('catalogue_names', f'{base}/aliases', 'names matched in trials', entry['aliases'],
                  'highlights and section 11 (generic name); product title (brand name)',
                  'the generic name and the brand name as the label prints them; trial names are matched to these exactly '
                  '(case and spacing ignored). Ixazomib Citrate and MLN9708 join through the earlier reviewed name mappings, not this entry'),
             item('catalogue_names', f'{base}/source', 'label version cited', entry['source'],
                  'the SPL set id, version and effective date on the DailyMed page',
                  'set id, version number and effective date from the SPL file; the XML checksum was computed from the downloaded ZIP')]
    return group('catalogue_names', 'drug_aliases', 'Names counted on the ixazomib drug page and the drug list', items)


def mechanism_group():
    _, entry, base = ixazomib_entry('drug_annotations')
    items = [item('catalogue_mechanism', f'{base}/fields/{f}', f, entry['fields'][f], 'section ' + sections(entry['fields'][f]),
                  SUMMARY + (' (a classification by the curator, from the label)' if f == 'modality' else ''))
             for f in ('mechanism', 'target', 'modality')]
    return group('catalogue_mechanism', 'drug_annotations', 'Mechanism, target and modality on the ixazomib drug page', items)


def safety_group():
    _, entry, base = ixazomib_entry('drug_safety')
    items = [item('catalogue_safety', f'{base}/boxed_warning', 'boxed warning', entry['boxed_warning'],
                  'the start of the full prescribing information and the highlights',
                  'recorded as absent: no boxed-warning section was found in the SPL file')]
    for i, w in enumerate(entry['selected_warnings']):
        items.append(item('catalogue_safety', f'{base}/selected_warnings/{i}', 'warning: ' + w['topic'], w,
                          'section ' + sections(w), SUMMARY + '; the topic name is the platform’s wording'))
    return group('catalogue_safety', 'drug_safety', 'Label warnings on the ixazomib drug page and in Patient Lab scenarios', items)


def interactions_group():
    _, entry, base = ixazomib_entry('drug_interactions')
    items = [item('catalogue_interactions', f'{base}/references/{i}', 'interaction: ' + r['partner_name'], r,
                  'sections ' + sections(r), SUMMARY + '; check the partner and the finding category')
             for i, r in enumerate(entry['references'])]
    return group('catalogue_interactions', 'drug_interactions', 'Interactions on the ixazomib drug page and in Patient Lab scenarios', items)


def build():
    return {'schema_version': 'extraction-review-queue-v1', 'queue_version': 'extraction-review-queue-round4-v1.0',
            'recorded_on': '2026-11-19', 'round': 4,
            'purpose': 'The ixazomib entries added in drug catalogue v2 (18 November 2026): names, mechanism, label warnings and '
                       'interactions, written from the NINLARO label by the AI assistant. None feeds a calculation. Each item is '
                       'one entry: check it against the label at the stated sections.',
            'excluded': 'These entries are summaries, not quotes, so nothing was matched by script against the label text. '
                        '“Matches” means the summary is faithful to the label at those sections.',
            'decisions': {'matches': 'The value matches the source at the stated location.',
                          'wrong': 'The value does not match the source (note what the source says).',
                          'cannot_check': 'The source or location could not be checked.'},
            'groups': [names_group(), mechanism_group(), safety_group(), interactions_group()]}


if __name__ == '__main__':
    OUT.write_text(json.dumps(build(), indent=1, ensure_ascii=False) + '\n')
    queue = json.loads(OUT.read_text())
    print(OUT.relative_to(ROOT), sha(OUT), sum(len(g['items']) for g in queue['groups']), 'items',
          [(g['id'], len(g['items'])) for g in queue['groups']])
