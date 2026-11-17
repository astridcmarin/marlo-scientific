"""Adjudication of the second-annotation disagreements (plan eligibility_second_annotation_plan_v1.json, `adjudication`).

The plan allows this only after annotator B's record is pinned and the agreement analysis is committed; both were done on
16 November 2026. The owner and B go through each disagreement under annotation guide v2 — the guide both of them read —
and each pair ends as the owner's value, B's value, or unclear, with a reason.

This is deliberately not blind: both readings are shown, labelled, because the two readers sit together and each knows
their own answers, so hiding the labels would buy nothing. The consequence is recorded in `resolution`: the guide's
author is in the room, and B may defer to her.

`view` assembles the disagreeing pairs from the pinned record, the pinned annotation and the locked agreement report.
`write_page` writes a standalone page holding only the guide, the criteria texts, both readings and the form.
`validate_record` applies the page's own rules to a returned record. `resolution` gives the split and, from it, each
reader's error count among the adjudicated pairs — the first per-reader estimate the project has had.

An adjudicated reference is NOT produced here: that would be a new annotation version under its own plan.
"""
import hashlib
import json
from pathlib import Path

from . import eligibility_annotations_v2 as ann2
from . import eligibility_second_annotation as sa
from . import eligibility_shared_errors as se
from . import eligibility_validation_v2 as v2
from .patient_state import digest

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).parent / 'data'
REPORT_PATH = ROOT / 'docs' / 'verification' / 'eligibility_second_annotation_v1.json'
REPORT_SHA256 = '627a4e13661a8736a8eee1f363508952422b840c75da21ee9e25764d29bb2040'
RECORD_SCHEMA = 'eligibility-adjudication-record-v1'
CHOICES = ('owner', 'annotator_b', 'unclear')
# The locked adjudication record of 17 November 2026, pinned before its analysis.
RECORD_PATH = DATA / 'eligibility_adjudication_record_v1.json'
RECORD_SHA256 = '0f63e47e80d676d795b46c1a7ab5cc2ceeba22933c1ee380545b19339d1fb8f5'


def load_record(path=RECORD_PATH):
    raw = Path(path).read_bytes()
    if RECORD_SHA256 is not None and hashlib.sha256(raw).hexdigest() != RECORD_SHA256:
        raise ValueError('The adjudication record is missing or changed.')
    return json.loads(raw)


def load_report(path=REPORT_PATH):
    raw = Path(path).read_bytes()
    if REPORT_SHA256 is not None and hashlib.sha256(raw).hexdigest() != REPORT_SHA256:
        raise ValueError('The second-annotation report is missing or changed.')
    return json.loads(raw)


def _entry(e):
    return {'status': e.get('status'), 'note': e.get('note') or '',
            'values': [{'comparator': v.get('comparator'), 'value': v.get('value'), 'unit': v.get('unit'),
                        'section': v.get('section'), 'describes': v.get('describes'),
                        'qualifier': v.get('qualifier') or '', 'sentence': v.get('sentence') or ''}
                       for v in (e.get('values') or [])]}


def view(report=None, p=None):
    """The disagreeing pairs, in the order the report lists them, with both readings labelled."""
    report = report or load_report()
    p = p or sa.page_payload()
    problems, b = sa.validate_record(sa.load_record(), p)
    if problems:
        raise ValueError(problems)
    a_all = v2.load_annotations()['annotations']
    texts = {t['nct_id']: t['criteria_text'] for t in p['trials']}
    items = []
    for k, d in enumerate(report['disagreements_for_adjudication'], 1):
        n, t = d['nct_id'], d['type']
        items.append({'position': k, 'id': f'{n}:{t}', 'nct_id': n, 'type': t,
                      'type_label': ann2.TYPES[t]['label'], 'short': se.LABELS[t],
                      'units': list(ann2.TYPES[t]['units']),
                      'criteria_text': texts[n],
                      'owner': _entry(a_all[n]['criteria'][t]),
                      'annotator_b': _entry(b[n][t])})
    out = {'schema_version': 'eligibility-adjudication-view-v1',
           'plan_version': report['plan_version'], 'plan_sha256': report['plan_sha256'],
           'report_file_sha256': REPORT_SHA256, 'report_sha256': report['report_sha256'],
           'page_sha256': report['page_sha256'],
           'guide_sha256': p['guide_sha256'], 'choices': list(CHOICES),
           'total': len(items), 'items': items}
    out['view_sha256'] = digest(out)
    return out


def write_page(path, v=None):
    """Writes the standalone adjudication page (one HTML file, no server). Returns its view_sha256."""
    import jinja2
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(ROOT / 'app' / 'templates')), autoescape=True)
    v = v or view()
    guide = sa.guide_path()
    page = env.get_template('eligibility_adjudication_standalone.html').render(
        v=v, guide_html=sa._md(guide.read_text(encoding='utf-8')))
    Path(path).write_text(page, encoding='utf-8')
    return v['view_sha256']


def validate_record(record, v=None):
    """(problems, decisions). Problems are messages; decisions maps pair id to its decision."""
    v = v or view()
    problems, out = [], {}
    if record.get('schema_version') != RECORD_SCHEMA:
        problems.append(f'schema_version must be {RECORD_SCHEMA}')
    if record.get('view_sha256') != v['view_sha256']:
        problems.append('view_sha256 does not match the adjudication view')
    seen = record.get('decisions') or {}
    ids = {it['id'] for it in v['items']}
    for extra in sorted(set(seen) - ids):
        problems.append(f'{extra}: not a disagreeing pair in this view')
    for it in v['items']:
        d = seen.get(it['id'])
        if not d:
            problems.append(f"{it['id']}: no decision")
            continue
        if d.get('choice') not in CHOICES:
            problems.append(f"{it['id']}: choice must be one of {', '.join(CHOICES)}")
        if not (d.get('reason') or '').strip():
            problems.append(f"{it['id']}: a reason is required")
        if not problems or problems[-1].split(':')[0] != it['id']:
            out[it['id']] = {'choice': d['choice'], 'reason': d['reason'].strip()}
    return problems, out


def resolution(record, v=None, adjudicators=None):
    """The split, and each reader's error count among the adjudicated pairs. Raises if the record is invalid.

    adjudicators: who was present, which the record itself does not carry. The page should ask for it; until it
    does, it is passed in and recorded as the owner stated it.
    """
    v = v or view()
    problems, decisions = validate_record(record, v)
    if problems:
        raise ValueError(problems)
    by_type, totals = {}, {c: 0 for c in CHOICES}
    for it in v['items']:
        c = decisions[it['id']]['choice']
        totals[c] += 1
        row = by_type.setdefault(it['type'], {c2: 0 for c2 in CHOICES})
        row[c] += 1
    pairs = v['items'][0]['position'] and 400
    owner_wrong, b_wrong = totals['annotator_b'], totals['owner']
    out = {'schema_version': 'eligibility-adjudication-report-v1',
           'plan_version': v['plan_version'], 'view_sha256': v['view_sha256'],
           'report_file_sha256': v['report_file_sha256'], 'report_sha256': v['report_sha256'],
           'guide_sha256': v['guide_sha256'],
           'adjudicators': adjudicators or 'not recorded',
           'adjudicated_pairs': v['total'], 'of_pairs_compared': pairs,
           'resolved_to': dict(totals), 'by_type': by_type,
           'reader_errors_among_adjudicated': {
               'owner_annotation_wrong': owner_wrong, 'annotator_b_wrong': b_wrong,
               'neither_settled': totals['unclear'],
               'note': ('Counted only among the pairs the two readers disagreed on. Pairs they agreed on are not '
                        'adjudicated, so a shared error is invisible here and these are lower bounds on each '
                        "reader's error count, not error rates.")},
           'scorer_note': {
               'finding': ('The agreement scorer compares (comparator, value as written, unit as written) with no '
                           'normalisation, so two readings of the same threshold can be scored as a disagreement. Two of '
                           'the 43 are of that kind: ">=8 g/dL" against ">=8.0 g/dL", and ">1000 cells/uL" against '
                           '">1000 /mm3 (= /uL)" - the second being an equivalence annotation guide v2 explicitly '
                           'promises the scoring treats as the same.'),
               'effect': ('Overall exact agreement would be 0.8975 rather than 0.8925 with those equivalences applied. '
                          'The plan reads the lower bound of the bootstrap interval against 0.90, and 0.8475 is far '
                          'enough below it that the verdict does not change. The locked result stands as scored.'),
               'next': ('A successor plan should either normalise values and units in the scorer or stop promising the '
                        'equivalence in the guide. Not changed here: the scorer belongs to a locked result.'),
           },
           'limitations': [
               'Adjudication is not blind: both readings are shown, labelled, because the readers sit together.',
               'The three choices cannot express "both readings wrong". Seven of the ten unclear decisions say so in '
               'their reason, which is why the per-reader counts below are lower bounds.',
               'Sixteen of the 43 reasons restate the verdict rather than giving one; 27 are substantive.',
               "The guide's author is one of the two readers, so B may defer to her; this is not corrected for.",
               'Only disagreements are adjudicated, so errors both readers share are not detected.',
               'An adjudicated reference is not produced here; that is a new annotation version under its own plan.'],
           'clinical_prediction_validated': False}
    out['report_sha256_self'] = digest(out)
    return out
