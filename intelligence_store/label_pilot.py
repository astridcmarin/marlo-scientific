"""Label ingestion pilot (decisions 0007 and 0009): draw the labels, draw the sections to review, apply the rule.

The plan (intelligence_store/data/label_ingestion_pilot_plan_v1.json) fixes the seeds, the sample sizes and the
pass rule. Draws are deterministic: the same inputs and seed give the same sample.
"""
import hashlib
import json
import math
import random
from pathlib import Path

from .spl_labels import category_class

PLAN_FILE = 'label_ingestion_pilot_plan_v1.json'
PLAN_PATH = Path(__file__).parent / 'data' / PLAN_FILE
PLAN_SHA256 = '67a6acdc863608eae94720cba0e659be0e33da2601e886240970b1380a1ec78a'  # locked 23 November 2026
LABEL_SEED = 20261120
SECTION_SEED = 20261121
N_BRAND = 20
N_GENERIC = 20
N_LABEL_SPARE = 10
N_REVIEW = 80
N_SPARE = 20
MAX_ERRORS = 2
BAR = 0.90
VERDICTS = ('match', 'error', 'not_reviewable')
ERROR_KINDS = ('text_missing', 'text_added', 'text_changed', 'order_wrong', 'heading_wrong', 'code_wrong',
               'table_unreadable', 'other')


def load_plan(path=PLAN_PATH):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError('The label ingestion pilot plan is missing or changed.')
    return json.loads(raw)


RX_PRODUCT_TYPE = 'HUMAN PRESCRIPTION DRUG'


def candidates_from_openfda_ndc(records):
    """The candidate list from openFDA's Human NDC Directory download (the 'results' list of its JSON file).

    Keeps product records whose product_type is HUMAN PRESCRIPTION DRUG and that carry exactly one
    openfda.spl_set_id, and groups them by set ID with the union of their marketing categories. Returns the
    candidates and a count of what was left out and why, so nothing is dropped silently.
    """
    by_set, left_out = {}, {'not_prescription': 0, 'no_set_id': 0, 'several_set_ids': 0, 'no_category': 0}
    for r in records:
        if (r.get('product_type') or '').strip().upper() != RX_PRODUCT_TYPE:
            left_out['not_prescription'] += 1
            continue
        set_ids = (r.get('openfda') or {}).get('spl_set_id') or []
        if not set_ids:
            left_out['no_set_id'] += 1
            continue
        if len(set(s.lower() for s in set_ids)) > 1:
            left_out['several_set_ids'] += 1
            continue
        category = (r.get('marketing_category') or '').strip().upper()
        if not category:
            left_out['no_category'] += 1
            continue
        by_set.setdefault(set_ids[0].lower(), set()).add(category)
    candidates = [{'set_id': k, 'marketing_categories': sorted(v)} for k, v in sorted(by_set.items())]
    return candidates, left_out


def sample_labels(candidates, exclude_set_ids=(), seed=LABEL_SEED, n_brand=N_BRAND, n_generic=N_GENERIC,
                  n_spare=N_LABEL_SPARE):
    """candidates: [{'set_id', 'marketing_categories': [...]}, ...] from the pinned candidate list. Brand and
    generic strata are each sorted by set ID, then sampled without replacement with one generator. Each stratum's
    list is in draw order: the first n are used, the next n_spare replace refused labels, in order."""
    seen, strata = set(), {'brand': [], 'generic': []}
    exclude = {s.lower() for s in exclude_set_ids}
    for c in candidates:
        sid = c['set_id'].lower()
        if sid in seen:
            raise ValueError(f'Set ID {sid} appears twice in the candidate list.')
        seen.add(sid)
        cls = category_class([m.strip().upper() for m in c['marketing_categories']])
        if sid not in exclude and cls in strata:
            strata[cls].append(sid)
    for cls, n in (('brand', n_brand + n_spare), ('generic', n_generic + n_spare)):
        if len(strata[cls]) < n:
            raise ValueError(f'Only {len(strata[cls])} {cls} candidates; the plan needs {n}.')
    rng = random.Random(seed)
    return {'brand': rng.sample(sorted(strata['brand']), n_brand + n_spare),
            'generic': rng.sample(sorted(strata['generic']), n_generic + n_spare),
            'used_per_stratum': {'brand': n_brand, 'generic': n_generic},
            'candidates': {k: len(v) for k, v in strata.items()}}


def sample_sections(con, seed=SECTION_SEED, n=N_REVIEW + N_SPARE):
    """Sections with text, in draw order: the first 80 reviewable are reviewed, spares replace any marked
    not_reviewable, in order."""
    rows = con.execute("SELECT set_id, version, method_version, ord FROM label_section WHERE text != '' "
                       "ORDER BY set_id, version, method_version, ord").fetchall()
    if len(rows) < n:
        raise ValueError(f'Only {len(rows)} sections with text; the plan draws {n}.')
    return [dict(zip(('set_id', 'version', 'method_version', 'ord'), r)) for r in random.Random(seed).sample(rows, n)]


def review_sheet(con, draws):
    items = []
    for i, d in enumerate(draws, start=1):
        row = con.execute('SELECT s.heading, s.code, s.code_name, s.text, d.title FROM label_section s JOIN '
                          'label_document d USING (set_id, version, method_version) WHERE s.set_id=? AND '
                          's.version=? AND s.method_version=? AND s.ord=?',
                          (d['set_id'], d['version'], d['method_version'], d['ord'])).fetchone()
        items.append({'draw': i, **d, 'label_title': row[4], 'heading': row[0], 'code': row[1], 'code_name': row[2],
                      'text': row[3], 'compare_with': f'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={d["set_id"]}',
                      'verdict': None, 'error_kind': None, 'note': None})
    return items


def lower_bound(successes, n, alpha=0.05):
    """Clopper-Pearson two-sided lower bound for a proportion, by bisection on the binomial tail."""
    if successes == 0:
        return 0.0
    def upper_tail(p):
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(successes, n + 1))
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if upper_tail(mid) < alpha / 2:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def evaluate(items):
    """Apply the locked rule to a completed review sheet: the first 80 items with a verdict other than
    not_reviewable are counted, in draw order; pass if they hold at most 2 errors."""
    for it in items:
        if it['verdict'] not in VERDICTS:
            raise ValueError(f'Draw {it["draw"]}: verdict {it["verdict"]!r} is not one of {VERDICTS}.')
        if it['verdict'] == 'error' and it['error_kind'] not in ERROR_KINDS:
            raise ValueError(f'Draw {it["draw"]}: an error needs one of {ERROR_KINDS}.')
    counted = [it for it in sorted(items, key=lambda x: x['draw']) if it['verdict'] != 'not_reviewable'][:N_REVIEW]
    if len(counted) < N_REVIEW:
        return {'result': 'incomplete', 'counted': len(counted),
                'reason': f'fewer than {N_REVIEW} reviewable sections among the {len(items)} drawn'}
    errors = [it for it in counted if it['verdict'] == 'error']
    matches = N_REVIEW - len(errors)
    lb = lower_bound(matches, N_REVIEW)
    return {'result': 'pass' if len(errors) <= MAX_ERRORS else 'fail', 'counted': N_REVIEW, 'errors': len(errors),
            'error_kinds': sorted({e['error_kind'] for e in errors}), 'accuracy': matches / N_REVIEW,
            'lower_bound_95': lb, 'meets_bar': lb >= BAR,
            'not_reviewable_used': sum(1 for it in items if it['verdict'] == 'not_reviewable')}
