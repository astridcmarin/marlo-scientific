"""Review of AI-assisted extractions by the platform owner (docs/EXTRACTION_REVIEW.md).

The queue (extraction_review_queue_v1.json, pinned here) lists every value that feeds a calculation or a quoted dose,
each by JSON pointer into a pinned extract. `queue_view` refuses to show the queue if any listed file changed or any
value no longer matches it. Review records are downloaded from the review page, checked with `validate_record`, and
then pinned in REVIEW_RECORDS; the latest record's decision for an item is its status. Nothing here changes a value:
a value found wrong is corrected by a new version of its extract, never in place.
"""
import copy
import hashlib
import json
from datetime import date
from pathlib import Path

from .patient_state import digest

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).parent / 'data'
QUEUE_PATH = DATA / 'extraction_review_queue_v1.json'
QUEUE_SHA256 = '3ebad5506b7e1c9ed95a581f485389b4ef421727013aa826071aab79daab3961'
# Round 3 (5 November 2026): values shown on pages but feeding no calculation, in a queue of their own so that the
# first queue and the records made against it stay unchanged. Built by scripts/build_review_round_3.py.
ROUND_3_QUEUE_PATH = DATA / 'extraction_review_queue_round3_v4.json'
ROUND_3_QUEUE_SHA256 = 'e1627e36d00c5064a5f50dd712b4321db6b0e9df3a1d064e4f63ed6532f49324'
# Superseded before any record was made against it, kept unchanged: v3 (117 entries, without the Hughes parameter precision;
# Hughes cited as DM instead of JH)
ROUND_3_QUEUE_V3_SHA256 = '28ff797fb70542d95c5f036963b5abdf4044c00dee1d114e1eaf7fe2787ce359'
# Superseded before any record was made against it, kept unchanged: v2 (113 entries, without the bioanalytical methods)
ROUND_3_QUEUE_V2_SHA256 = '3cd9f931f243efcd96633b8e03bc5d7a40d4629b5b0b2ee44e82363d82e12a71'
# Superseded before any record was made against it, kept unchanged: extraction_review_queue_round3_v1.json (99 entries,
# without the FDA 2026 draft hepatic guidance)
ROUND_3_QUEUE_V1_SHA256 = 'f955d8dddfb7fc5ee47d17df79b9010858428e5c5760dfa73d66c6a12f932575'
QUEUES = {'main': (QUEUE_PATH, QUEUE_SHA256), 'round_3': (ROUND_3_QUEUE_PATH, ROUND_3_QUEUE_SHA256)}
RECORD_SCHEMA = 'extraction-review-record-v1'
DECISIONS = ('matches', 'wrong', 'cannot_check')
# Pinned review records, oldest first: (file name in intelligence_store/data, sha256).
REVIEW_RECORDS = (
    ('extraction_review_record_2026-11-03_v1.json', '8bf417fb74bce88361db9a1c7f171dc8e12f96d2be1f8b100b250635b9ffb478'),  # round 1, Astrid, 3 November 2026
    ('extraction_review_record_2026-11-04_round2_v1.json', 'e7e6da378e62fa9884cb55a1edc4359dc8a0fdf3a2bce76521187969b28128e7'),  # round 2, Astrid, 4 November 2026
)


class ReviewError(ValueError):
    pass


def _resolve(document, pointer):
    node = document
    for token in pointer[1:].split('/') if pointer else []:
        token = token.replace('~1', '/').replace('~0', '~')
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def load_queue(path=QUEUE_PATH, sha256=QUEUE_SHA256):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ReviewError('The extraction review queue is missing or changed.')
    queue = json.loads(raw)
    if queue.get('schema_version') != 'extraction-review-queue-v1':
        raise ReviewError('Unsupported review queue schema.')
    for group in queue['groups']:
        raw = (ROOT / group['file']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != group['sha256']:
            raise ReviewError(f"{group['file']} changed since the queue was built; the queue needs a new version.")
        document = json.loads(raw)
        for item in group['items']:
            try:
                found = _resolve(document, item['pointer'])
            except (KeyError, IndexError, ValueError) as exc:
                raise ReviewError(f"{item['id']} does not resolve.") from exc
            if found != item['value']:
                raise ReviewError(f"{item['id']} no longer matches its file.")
    return queue


def item_ids(queue=None):
    queue = queue or load_queue()
    return {item['id'] for group in queue['groups'] for item in group['items']}


def queue_key(record):
    """Which pinned queue a record was made against, or None."""
    sha = record.get('queue_sha256') if isinstance(record, dict) else None
    return next((k for k, (_, s) in QUEUES.items() if s == sha), None)


def validate_record(record, queue=None):
    """Check a downloaded review record before it is pinned. Returns the record unchanged or raises ReviewError.
    The record is checked against the queue whose checksum it carries (the first queue or round 3's)."""
    if not isinstance(record, dict) or record.get('schema_version') != RECORD_SCHEMA:
        raise ReviewError('Not an extraction review record.')
    key = queue_key(record)
    if key is None:
        raise ReviewError('The record was made against a different review queue.')
    queue = queue or load_queue(*QUEUES[key])
    if record.get('queue_version') != queue['queue_version']:
        raise ReviewError('The record was made against a different review queue.')
    for key in ('reviewer', 'reviewed_on'):
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise ReviewError(f'Missing {key}.')
    try:
        date.fromisoformat(record['reviewed_on'])
    except ValueError as exc:
        raise ReviewError('reviewed_on must be an ISO date.') from exc
    decisions = record.get('decisions')
    if not isinstance(decisions, dict) or not decisions:
        raise ReviewError('No decisions.')
    known = item_ids(queue)
    for item_id, d in decisions.items():
        if item_id not in known:
            raise ReviewError(f'Unknown item {item_id}.')
        if not isinstance(d, dict) or d.get('decision') not in DECISIONS:
            raise ReviewError(f'Invalid decision for {item_id}.')
        if not isinstance(d.get('note', ''), str):
            raise ReviewError(f'Invalid note for {item_id}.')
        if d['decision'] == 'wrong' and not d.get('note', '').strip():
            raise ReviewError(f'{item_id}: a value marked wrong needs a note saying what the source shows.')
    return record


def load_records(records=None):
    out = []
    for name, sha in (REVIEW_RECORDS if records is None else records):
        raw = (DATA / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ReviewError(f'Review record {name} is missing or changed.')
        out.append(dict(validate_record(json.loads(raw)), file=name, sha256=sha))
    return out


def queue_view(records=None, queue_name='main'):
    path, queue_sha = QUEUES[queue_name]
    queue = load_queue(path, queue_sha)
    reviews = [r for r in load_records(records) if r['queue_sha256'] == queue_sha]
    status = {}
    for rec in reviews:
        for item_id, d in rec['decisions'].items():
            status[item_id] = {'decision': d['decision'], 'note': d.get('note', ''), 'reviewed_on': rec['reviewed_on'],
                               'reviewer': rec['reviewer'], 'record': rec['file']}
    groups, counts = [], {'unreviewed': 0, **{d: 0 for d in DECISIONS}}
    for g in queue['groups']:
        items = []
        for item in g['items']:
            st = status.get(item['id'])
            counts[st['decision'] if st else 'unreviewed'] += 1
            items.append(dict(copy.deepcopy(item), status=st))
        groups.append(dict({k: v for k, v in g.items() if k != 'items'}, items=items,
                           reviewed=sum(1 for i in items if i['status'])))
    view = {'schema_version': 'extraction-review-view-v1', 'queue_version': queue['queue_version'], 'queue_sha256': queue_sha,
            'purpose': queue['purpose'], 'excluded': queue['excluded'], 'decision_labels': queue['decisions'],
            'groups': groups, 'counts': counts, 'total': sum(counts.values()),
            'records': [{'file': r['file'], 'sha256': r['sha256'], 'reviewer': r['reviewer'], 'reviewed_on': r['reviewed_on'],
                         'decisions': len(r['decisions'])} for r in reviews]}
    view['view_sha256'] = digest(view)
    return view


ROUND_2_PATH = DATA / 'extraction_review_round_2_v1.json'
ROUND_2_SHA256 = '3c44305907fcdba4d742d7b31aa81a9a6ca13f24a70b3b9149b2255fbbffae4d'


def load_round_2():
    raw = ROUND_2_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ROUND_2_SHA256:
        raise ReviewError('The round 2 list is missing or changed.')
    rnd = json.loads(raw)
    if rnd['queue_sha256'] != QUEUE_SHA256:
        raise ReviewError('The round 2 list was made against a different review queue.')
    first = dict(REVIEW_RECORDS).get(rnd['follows_record'])
    if first is None:
        raise ReviewError('The round 1 record the round 2 list follows is not pinned.')
    decided = next(r for r in load_records() if r['file'] == rnd['follows_record'])['decisions']
    expected = {i for i in item_ids() if decided.get(i, {}).get('decision') != 'matches'}
    if {i['id'] for i in rnd['items']} != expected:
        raise ReviewError('The round 2 list is not exactly the items round 1 did not mark as matching.')
    return rnd


def round_2_view(records=None):
    """The queue view limited to the round 2 items, each with where to look and how the stored value was obtained."""
    rnd = load_round_2()
    aid = {i['id']: i for i in rnd['items']}
    view = queue_view(records)
    groups = []
    for g in view['groups']:
        items = [dict(i, where_to_look=aid[i['id']]['where_to_look'], how_stored=aid[i['id']]['how_stored'])
                 for i in g['items'] if i['id'] in aid]
        if items:
            groups.append(dict(g, items=items, reviewed=sum(1 for i in items if i['status'])))
    view = dict(view, groups=groups, round=2, round_purpose=rnd['purpose'], round_caution=rnd['caution'],
                round_sha256=ROUND_2_SHA256, round_total=len(aid))
    view.pop('view_sha256', None)
    view['view_sha256'] = digest(view)
    return view


def round_3_view(records=None):
    """The round 3 queue (values shown on pages, no calculation), in the round layout of the review page."""
    view = queue_view(records, 'round_3')
    queue = load_queue(*QUEUES['round_3'])
    view = dict(view, round=3, round_purpose=queue['purpose'], round_caution=queue['excluded'], round_total=view['total'])
    view.pop('view_sha256', None)
    view['view_sha256'] = digest(view)
    return view


SECOND_READING_REASONS = {
    'disagree': 'In the list because the two extractions disagree',
    'not_comparable': 'In the list because it has no numbers to compare: check the whole entry',
    'sampled_agreement': 'In the list as one of the 20 sampled agreements (seed 20261111)',
    'out_of_scope': 'In the list because the second reader had no source PDF for it: check the whole entry',
}


def track_b_view(records=None):
    """Round 3 limited to the entries the owner reviews under the Track B plan (every disagreement, every entry without
    numbers, the 20 sampled agreements, the 21 out-of-scope entries), each with the second reading beside it.

    Decisions made on this page are ordinary round 3 decisions on the same queue checksum, so a record downloaded here
    is validated and pinned like any round 3 record. They are the owner's decisions; the second reading only helps."""
    from .double_extraction import load_plan as load_track_b_plan, load_result
    plan, result = load_track_b_plan(), load_result()
    reason = {}
    for key, ids in (('disagree', result['owner_to_review']['disagreements']),
                     ('not_comparable', result['owner_to_review']['not_comparable']),
                     ('sampled_agreement', result['owner_to_review']['sampled_agreements'])):
        reason.update(dict.fromkeys(ids, key))
    second = {e['id']: e for e in result['entries']}
    outside = set(plan['out_of_scope']['groups'])
    base = round_3_view(records)
    groups = []
    for g in base['groups']:
        items = []
        for item in g['items']:
            why = 'out_of_scope' if g['id'] in outside else reason.get(item['id'])
            if why is None:
                continue
            e = second.get(item['id'], {})
            items.append(dict(item, second_reading={
                'reason': why, 'reason_text': SECOND_READING_REASONS[why], 'value': e.get('second_reader_value'),
                'platform_only': e.get('only_first') or [], 'second_only': e.get('only_second') or [],
                'note': e.get('why', ''), 'quotes_not_found': e.get('missing_quotes') or []}))
        if items:
            groups.append(dict(g, items=items, reviewed=sum(1 for i in items if i['status'])))
    counts = {k: sum(1 for g in groups for i in g['items'] if i['second_reading']['reason'] == k) for k in SECOND_READING_REASONS}
    view = dict(base, groups=groups, track_b=True, round_total=sum(counts.values()), track_b_counts=counts,
                round_purpose=(f"Track B ({plan['plan_version']}): the round 3 entries you review after the second, independent "
                               'extraction. Each shows the platform\'s values, the second reading and why the entry is listed.'),
                track_b_fail_rule=plan['decision_rule']['fail'])
    view.pop('view_sha256', None)
    view['view_sha256'] = digest(view)
    return view


def register_extraction_review_commands(app):
    import click

    @app.cli.command('extraction-review-check')
    @click.argument('record_file', type=click.Path(exists=True, dir_okay=False, path_type=Path))
    def command(record_file):
        """Validate a downloaded extraction review record and print its checksum for pinning."""
        raw = record_file.read_bytes()
        try:
            record = validate_record(json.loads(raw))
        except (ReviewError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        counts = {d: sum(1 for x in record['decisions'].values() if x['decision'] == d) for d in DECISIONS}
        click.echo(json.dumps({'valid': True, 'sha256': hashlib.sha256(raw).hexdigest(), 'decisions': counts}, indent=2))


# ---------------------------------------------------------------- review status shown on pages
# Pages show the owner review for a pinned file only when that exact file is in the queue; a later version of a file
# (for example renal_pk_group_evidence_v2.json) is not covered by a review of the earlier one.
KEY_FILES = {
    'model:lenalidomide_hughes_2019': ('intelligence_store/data/hughes_parameter_extract_v1.json',
                                       'intelligence_store/data/hughes_variability_extract_v1.json'),
    'model:lenalidomide_kim_2026': ('intelligence_store/data/kim_2026_model_extract_v1.json',),
    'model:lenalidomide_exposure_safety_2016': ('intelligence_store/data/lenalidomide_exposure_safety_v2.json',),
    'model:ixazomib_pk_gupta_2017': ('intelligence_store/data/ixazomib_pk_gupta_2017_extract_v1.json',),
    'model:daratumumab_pk_luo_2021': ('intelligence_store/data/daratumumab_pk_luo_2021_extract_v1.json',),
    'label:lenalidomide': ('intelligence_store/data/lenalidomide_label_2023_v1.json',),
    'label:pomalidomide': ('intelligence_store/data/label_pk_pomalidomide_v1.json',),
    'label:dexamethasone': ('intelligence_store/data/label_pk_dexamethasone_hemady_v1.json',),
}


def _file_status(group):
    items = group['items']
    counts = {d: sum(1 for i in items if i['status'] and i['status']['decision'] == d) for d in DECISIONS}
    counts['unreviewed'] = sum(1 for i in items if not i['status'])
    dates = sorted({i['status']['reviewed_on'] for i in items if i['status']})
    reviewers = sorted({i['status']['reviewer'] for i in items if i['status']})
    n, name = len(items), group['file'].rsplit('/', 1)[-1]
    when = (dates[0] if len(dates) == 1 else f'{dates[0]} to {dates[-1]}') if dates else None
    if counts['matches'] == n:
        text = (f'Owner review: all {n} values the platform uses from {name} match the source '
                f'(checked by the platform owner, {when}). Not an independent review.')
    elif counts['unreviewed'] == n:
        text = f'Owner review: the {n} values the platform uses from {name} have not been reviewed yet.'
    else:
        parts = [f"{counts['matches']} of {n} values the platform uses from {name} match the source"]
        parts += [f"{counts[k]} {label}" for k, label in (('wrong', 'found wrong'), ('cannot_check', 'could not be checked'),
                                                          ('unreviewed', 'not yet reviewed')) if counts[k]]
        text = 'Owner review: ' + '; '.join(parts) + f' (platform owner, {when}). Not an independent review.'
    return {'file': group['file'], 'values': n, 'counts': counts, 'reviewed_on': dates, 'reviewers': reviewers,
            'all_match': counts['matches'] == n, 'text': text}


def owner_review(keys, view=None):
    """Review status for pinned files, by file path or by a KEY_FILES key. Files not in the queue are skipped."""
    views = [view] if view else [queue_view(), queue_view(queue_name='round_3')]
    by_file = {g['file']: g for v in views for g in v['groups']}
    files = []
    for key in ([keys] if isinstance(keys, str) else keys):
        for f in KEY_FILES.get(key, (key,)):
            if f in by_file and f not in files:
                files.append(f)
    return [_file_status(by_file[f]) for f in files]
