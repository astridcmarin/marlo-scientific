"""Track B: double extraction for extraction-review round 3 (plan: data/extraction_double_extraction_plan_v1.json).

A second reader (Claude Fable, in a separate session) extracts each round 3 entry again from the source document,
without seeing the platform's extract: it gets a blinded entry (an opaque id, the source document and location, and the
field names to fill, with every value removed and every number in the label masked). This module builds the blinded
entries, compares the two extractions and draws the fixed random sample of agreements for the owner to review.

Agreement is decided on numbers only, so that it is objective: every number in the entry (numeric fields and numbers
written inside text fields) must match between the two extractions as a multiset; quotes are not compared with each
other but each second-reader quote must be found in the source by scripts/check_source_quotes.py; locations are given,
not compared. Research tooling; no page uses it.
"""
import hashlib
import json
import random
import re
from pathlib import Path

DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'extraction_double_extraction_plan_v1.json'
PLAN_SHA256 = 'bdd87e4a95e94f54efb80474e77ec7f44bbc56af19bcd552d5a51448379e66cb'
QUEUE_PATH = DATA / 'extraction_review_queue_round3_v4.json'
QUEUE_SHA256 = 'e1627e36d00c5064a5f50dd712b4321db6b0e9df3a1d064e4f63ed6532f49324'
RESULT_PATH = DATA / 'extraction_double_extraction_result_v1.json'
RESULT_SHA256 = 'e221038b8c60a87884ace424c46bb74ea25e213663fbd3c55be322418a87757d'
META_KEYS = frozenset({'id', 'location', 'check', 'source', 'file_sha256', 'dataset'})
NUMBER = re.compile(r'(?<![A-Za-z])\d+(?:[.,]\d+)*')


def _pinned(path, expected, what):
    raw = Path(path).read_bytes()
    if expected is not None and hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'{what} is missing or changed; a change needs a new version.')
    return json.loads(raw)


def load_plan():
    return _pinned(PLAN_PATH, PLAN_SHA256, 'Double-extraction plan')


def load_queue():
    return _pinned(QUEUE_PATH, QUEUE_SHA256, 'Round 3 queue')


def load_result():
    """The second extraction and its comparison (12 November 2026); the owner's review is recorded separately."""
    return _pinned(RESULT_PATH, RESULT_SHA256, 'Double-extraction result')


def opaque_id(item_id):
    return 'B-' + hashlib.sha256(item_id.encode()).hexdigest()[:10]


def _template(value):
    if isinstance(value, dict):
        return {k: _template(v) for k, v in value.items() if k not in META_KEYS}
    if isinstance(value, list):
        return ['…'] if value else []
    return None


def mask_numbers(text):
    return NUMBER.sub('#', text)


def blind_items(queue, groups):
    """The blinded entries of the named groups, in queue order."""
    out = []
    for g in queue['groups']:
        if g['id'] not in groups:
            continue
        for it in g['items']:
            out.append({'blind_id': opaque_id(it['id']), 'source_document': g['where_to_look'],
                        'where_to_look': it['where_to_look'], 'what': mask_numbers(it['label']),
                        'fields_to_fill': _template(it['value']) if isinstance(it['value'], dict) else {'quote': None}})
    return out


def numbers(value):
    """Every number in a value, as a sorted list of strings without thousands separators; quotes excluded."""
    found = []

    def walk(v, key=None):
        if key is not None and (key in META_KEYS or key.endswith('quote') or key == 'quotes'):
            return
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, (int, float)):
            found.append(_norm(repr(float(v))))
        elif isinstance(v, str):
            found.extend(_norm(n) for n in NUMBER.findall(v))
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(x, k)
        elif isinstance(v, list):
            for x in v:
                walk(x, key)
    walk(value)
    return sorted(found)


def _norm(token):
    token = token.replace(',', '') if re.fullmatch(r'\d{1,3}(,\d{3})+(\.\d+)?', token) else token.replace(',', '.')
    value = float(token)
    return repr(value)


def compare(first, second):
    """'agree' or 'disagree', with the numbers each extraction has that the other lacks."""
    a, b = numbers(first), numbers(second)
    only_first, only_second = list(a), list(b)
    for n in a:
        if n in only_second:
            only_second.remove(n)
            only_first.remove(n)
    return {'result': 'agree' if not only_first and not only_second else 'disagree',
            'only_first': only_first, 'only_second': only_second}


def agreement_sample(agreeing_ids, size, seed):
    ids = sorted(agreeing_ids)
    return sorted(random.Random(seed).sample(ids, min(size, len(ids))))
