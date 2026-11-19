"""What the platform holds for one drug: its sources, their review state, and the regulatory documents among them.

Evidence-first plan items 6 and 7 (19 November 2026). Computed, not kept by hand: every source is a dataset in the pinned
dataset ledger, attributed to a drug when the drug's name or one of its curated aliases appears in the dataset's key or
title, or when a model named after the drug uses it. Its files carry the evidence state the review records give
(evidence_states). A source whose values have not been read is listed by title only, never with values, so that a later
blind check can still use it; a dataset that is neither read nor held (a model's fitting data) is not a holding. The
special-population summaries add the sources they cite (model extracts, labels, assessment reports) that the ledger does
not list as datasets. Regulatory documents are the sources whose title or citation names a product label, a
regulator's assessment report or review, or an AusPAR; the drug catalogue's own label version is listed with them.
"""
import re

from . import dataset_ledger as dl

REGULATORY_KINDS = (   # (kind, pattern over the dataset's title and source citations), first match wins
    ('EMA assessment report', re.compile(r'\bEPAR\b|assessment report|EMEA/|EMA/', re.I)),
    ('TGA AusPAR', re.compile(r'AusPAR', re.I)),
    ('Product label', re.compile(r'(?<![-\w])label\b|prescribing information', re.I)),     # not "open-label"
    ('FDA review', re.compile(r'FDA review|clinical pharmacology .*review|NDA \d', re.I)),
)


def _names(drug_id):
    """The drug's id and its curated aliases, lower case (the alias catalogue is the source of brand names)."""
    from .drug_aliases import load_alias_catalog
    names = {drug_id.lower()}
    try:
        entry = next((e for e in load_alias_catalog()['entries'] if e['id'] == drug_id), None)
    except Exception:          # the catalogue's own error types vary; holdings must not break the drug page
        entry = None
    if entry:
        names |= {a.lower() for a in entry['aliases']}
    return names, entry


def _mentions(text, names):
    text = text.lower().replace('_', ' ')
    return any(re.search(r'(?<![a-z])' + re.escape(n) + r'(?![a-z])', text) for n in names)


def regulatory_kind(dataset):
    text = ' '.join([dataset.get('title', '')] + list(dataset.get('sources', [])))
    return next((kind for kind, rx in REGULATORY_KINDS if rx.search(text)), None)


SCOPE_FILE = re.compile(r'_scope_v\d+\.json$')


def _earlier_versions(path):
    """The files a pinned file says it supersedes, following the chain."""
    import json
    from .evidence_index import ROOT
    out, seen = [], set()
    while path and path not in seen:
        seen.add(path)
        try:
            sup = json.loads((ROOT / path).read_text()).get('supersedes')
        except (OSError, ValueError):
            break
        path = sup.get('file') if isinstance(sup, dict) else None
        if path:
            out.append(path)
    return out


def _special_population_sources(drug_id):
    from . import special_populations as sp
    try:
        return sp.build(drug_id)['sources'] if drug_id in sp.available() else []
    except Exception:
        return []


def _catalogue_review(path, drug_id):
    """Round 4 reviewed one drug's entries inside the shared catalogue files: say so for that drug only."""
    import json
    from . import extraction_review as er
    try:
        view = er.round_4_view()
    except Exception:
        return None
    for g in view['groups']:
        if g['file'] != path:
            continue
        doc = json.loads((er.ROOT / path).read_text())
        ids = {(doc['entries'][int(i['pointer'].split('/')[2])].get('id')
                or doc['entries'][int(i['pointer'].split('/')[2])].get('entity_id')) for i in g['items']}
        if ids != {drug_id}:
            return None
        if all(i['status'] and i['status']['decision'] == 'matches' for i in g['items']):
            return {'file': path, 'state': 'reviewed_by_owner',
                    'label': f"This drug's {len(g['items'])} entries reviewed by the owner (round 4)"}
    return None


def _file_state(path, drug_id=None):
    from .evidence_states import state_of
    try:
        s = state_of(path)
    except Exception:
        s = None
    if s is None and drug_id:
        own = _catalogue_review(path, drug_id)
        if own:
            return own
    if s is None:                    # a later version: say whether an earlier version was reviewed (it does not inherit)
        for earlier in _earlier_versions(path):
            try:
                e = state_of(earlier)
            except Exception:
                e = None
            if e and e['state'] == 'reviewed_by_owner':
                return {'file': path, 'state': 'earlier_reviewed',
                        'label': f"Earlier version reviewed by the owner ({earlier.rsplit('/', 1)[-1]}); this version not yet"}
    return {'file': path, 'state': s['state'] if s else None, 'label': s['label'] if s else 'Not in a review queue'}


def holdings(drug_id, ledger=None):
    ledger = ledger or dl.load_ledger()
    names, catalogue_entry = _names(drug_id)
    uses = ledger['uses']
    rows = []
    for key, ds in ledger['datasets'].items():
        by_model = [u for u in uses if u['dataset'] == key and u['model'].startswith(drug_id + '_')]
        if not (_mentions(key, names) or _mentions(ds.get('title', ''), names) or by_model):
            continue
        ds_uses = [u for u in uses if u['dataset'] == key]
        unread = not ds.get('values_first_seen')
        if unread and not ds.get('source_files'):
            continue                 # never seen and not held (a model's fitting data): not a holding
        rows.append({
            'dataset': key, 'title': ds['title'], 'sources': list(ds.get('sources', [])),
            'values_first_seen': ds.get('values_first_seen'), 'unread': unread,
            'files': [] if unread else [_file_state(f, drug_id) for f in ds.get('files', [])],
            'checks': sorted({u['report'] for u in ds_uses if u.get('report')}),
            'roles': sorted({u['role'] for u in ds_uses}),
            'regulatory_kind': regulatory_kind(ds),
        })
    covered = {f['file']: r for r in rows for f in r['files']}
    for src in _special_population_sources(drug_id):
        if src['file'] in covered or SCOPE_FILE.search(src['file']):
            continue                 # already listed, or a platform scope file (the platform's own, not a source)
        earlier = _earlier_versions(src['file'])
        same = next((covered[e] for e in earlier if e in covered), None)
        if same is not None:         # a later version of a file already listed: add it to that source
            same['files'].append(_file_state(src['file'], drug_id))
            covered[src['file']] = same
            continue
        row = {'dataset': None, 'title': src['title'], 'sources': [], 'values_first_seen': None, 'unread': False,
               'files': [_file_state(src['file'], drug_id)], 'checks': [], 'roles': [],
               'regulatory_kind': regulatory_kind({'title': src['title']}), 'via': 'special-population summary'}
        rows.append(row)
        covered[src['file']] = row
    for r in rows:                   # keep current files only: a file superseded by another in the same source is dropped
        names = [f['file'] for f in r['files']]
        old = {e for n in names for e in _earlier_versions(n)}
        r['files'] = [f for f in r['files'] if f['file'] not in old]
    rows.sort(key=lambda r: (r['unread'], r['title']))
    catalogue = None
    if catalogue_entry:
        src = catalogue_entry['source']
        catalogue = {'title': src.get('title'), 'set_id': src.get('set_id'), 'label_version': src.get('label_version'),
                     'effective': src.get('label_effective_date'), 'url': src.get('url'), 'verified_on': src.get('verified_on')}
    return {'drug': drug_id,
            'read': [r for r in rows if not r['unread']],
            'held_unread': [r for r in rows if r['unread']],
            'regulatory': [r for r in rows if r['regulatory_kind'] and not r['unread']],
            'regulatory_held_unread': [r for r in rows if r['regulatory_kind'] and r['unread']],
            'catalogue_label': catalogue,
            'rule': ('Sources are datasets in the pinned dataset ledger that name the drug or one of its aliases, or that a '
                     'model named after the drug uses. Unread sources are listed by title only.'),
            'clinical_prediction_validated': False}


STATE_WORDS = {'reviewed_by_owner': 'reviewed by the owner', 'agreed_by_two_extractions': 'agreed by two extractions, sampled',
               'earlier_reviewed': 'reviewed by the owner in an earlier version, not in this one',
               'extracted': 'extracted, review not complete', None: 'not in a review queue'}
STATE_ORDER = ('reviewed_by_owner', 'agreed_by_two_extractions', 'earlier_reviewed', 'extracted', None)


def state_summary(row):
    """One line for a read source: its files' review states and how many checks used it."""
    n = len(row['files'])
    counts = {st: sum(1 for f in row['files'] if f['state'] == st) for st in STATE_ORDER}
    if n == 1:
        parts = [STATE_WORDS[row['files'][0]['state']].capitalize()]
    elif n:
        parts = ['; '.join(f'{c} of {n} files {STATE_WORDS[st]}' for st, c in counts.items() if c)]
        parts[0] = parts[0][0].upper() + parts[0][1:]
    else:
        parts = ['No extract file on the platform']
    if row['checks']:
        parts.append(f"used in {len(row['checks'])} locked check{'s' if len(row['checks']) != 1 else ''}")
    return '; '.join(parts) + '.'
