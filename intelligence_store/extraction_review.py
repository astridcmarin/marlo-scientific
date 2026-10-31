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
RECORD_SCHEMA = 'extraction-review-record-v1'
DECISIONS = ('matches', 'wrong', 'cannot_check')
# Pinned review records, oldest first: (file name in intelligence_store/data, sha256).
REVIEW_RECORDS = ()


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


def validate_record(record, queue=None):
    """Check a downloaded review record before it is pinned. Returns the record unchanged or raises ReviewError."""
    queue = queue or load_queue()
    if not isinstance(record, dict) or record.get('schema_version') != RECORD_SCHEMA:
        raise ReviewError('Not an extraction review record.')
    if record.get('queue_sha256') != QUEUE_SHA256 or record.get('queue_version') != queue['queue_version']:
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


def queue_view(records=None):
    queue = load_queue()
    reviews = load_records(records)
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
    view = {'schema_version': 'extraction-review-view-v1', 'queue_version': queue['queue_version'], 'queue_sha256': QUEUE_SHA256,
            'purpose': queue['purpose'], 'excluded': queue['excluded'], 'decision_labels': queue['decisions'],
            'groups': groups, 'counts': counts, 'total': sum(counts.values()),
            'records': [{'file': r['file'], 'sha256': r['sha256'], 'reviewer': r['reviewer'], 'reviewed_on': r['reviewed_on'],
                         'decisions': len(r['decisions'])} for r in reviews]}
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
