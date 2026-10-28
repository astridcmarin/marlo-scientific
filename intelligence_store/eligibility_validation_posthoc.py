"""Phase 4.1e, post hoc: why the locked check failed. Not part of the locked plan, and not a pass for any type.

Written after the locked result (docs/verification/eligibility_validation_v1.json) was known. It changes no pinned
file and no decision; it only describes the disagreements:

1. Convention. The guide asks the annotator to write exclusion criteria as the eligible side ("CrCl < 30" in
   exclusion -> >= 30). A re-scoring applies that rule mechanically to every annotated exclusion value whose
   comparator appears as a symbol in its own sentence (so it was recorded as written), whatever the extractor said,
   and reads ECOG '< k' as '<= k-1' on both sides (an integer scale). Values written in words are left as they are.
2. Categories of the disagreements that remain after that re-scoring.
3. Attainability of the pass rule: the smallest number of errors that still allows the Wilson lower bounds required
   by the plan, given each type's number of annotated pairs.
"""
import collections
import copy
import json
from pathlib import Path

import click

from . import eligibility_extractor as ex
from . import eligibility_validation as ev
from .eligibility_annotation_review import _written_as_in_sentence
from .eligibility_annotations import load_sample
from .eligibility_corpus import load_corpus
from .patient_state import digest

REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'eligibility_validation_v1_posthoc.json'
_FLIP = {'>=': '<', '>': '<=', '<=': '>', '<': '>='}


def _ecog_integer(v):
    v = dict(v)
    if v['comparator'] == '<':
        v['comparator'], v['value'] = '<=', str(int(float(v['value'])) - 1)
    elif v['comparator'] == '>':
        v['comparator'], v['value'] = '>=', str(int(float(v['value'])) + 1)
    return v


def eligible_side(ctype, entry):
    """The annotation entry with exclusion values recorded as written turned to the eligible side (guide rule 1)."""
    entry = copy.deepcopy(entry)
    values = []
    for v in entry['values']:
        v = dict(v)
        if v['section'] == 'exclusion' and _written_as_in_sentence(v):
            v['comparator'] = _FLIP[v['comparator']]
        if ctype == 'ecog_max':
            v = _ecog_integer(v)
        if not any(ev.values_match(ctype, v, kept) for kept in values):
            values.append(v)
    entry['values'] = values
    if entry['status'] in ('stated', 'multiple'):
        entry['status'] = 'stated' if len(values) == 1 else 'multiple'
    return entry


def _extracted(ctype, entry):
    if ctype != 'ecog_max':
        return entry
    entry = copy.deepcopy(entry)
    entry['values'] = [_ecog_integer(v) for v in entry['values']]
    return entry


def category(ctype, gold, got):
    outcome = ev.score_pair(ctype, gold, got)['outcome']
    if outcome in ('tp', 'tn', 'excluded_unclear'):
        return None
    gv, xv = gold['values'], got['values']
    if not xv:
        return 'missed (nothing extracted)'
    if gold['status'] == 'not_stated':
        return 'extracted where annotated not stated'
    same_number = lambda a, b: a['comparator'] == b['comparator'] and float(a['value']) == float(b['value'])
    if len(xv) == len(gv) and all(any(same_number(a, b) for b in xv) for a in gv):
        return 'same number, different unit label'
    if gold['status'] == 'multiple' and all(any(ev.values_match(ctype, b, a) for a in gv) for b in xv):
        return 'annotated multiple (cohort or exception), fewer extracted'
    if all(any(ev.values_match(ctype, a, b) for b in xv) for a in gv):
        return 'extra value extracted'
    return 'different value or comparator'


def min_errors_allowed(n, lower=0.90):
    """Largest number of errors e such that the Wilson lower bound of (n - e)/n is still >= lower."""
    allowed = None
    for e in range(n + 1):
        lo, _ = ev.wilson(n - e, n)
        if lo is not None and lo >= lower:
            allowed = e
    return allowed


def run():
    annotations = ev.load_annotations()
    ev.check_extractor_frozen()
    sample = load_sample()
    texts = {t['nct_id']: t['eligibility']['criteria_text'] for t in load_corpus()['trials']}
    rescored, changed, cats = [], 0, collections.defaultdict(collections.Counter)
    examples = collections.defaultdict(list)
    for nct_id in sample['annotation_order']:
        extracted = ex.extract(texts[nct_id])
        for ctype in ev.TYPES:
            original = annotations['annotations'][nct_id]['criteria'][ctype]
            gold = eligible_side(ctype, original)
            changed += gold != original
            got = _extracted(ctype, extracted[ctype])
            rescored.append(dict(type=ctype, annotated_status=gold['status'], **ev.score_pair(ctype, gold, got)))
            c = category(ctype, gold, got)
            if c:
                cats[ctype][c] += 1
                examples[c].append({'nct_id': nct_id, 'type': ctype})
    summary = ev.summarise(rescored)
    attain = {}
    for ctype, s in summary.items():
        n = s['annotated']['stated'] + s['annotated']['multiple']
        attain[ctype] = {'annotated_positive_pairs': n,
                         'errors_allowed_for_recall_lower_bound_0.75': min_errors_allowed(n, 0.75),
                         'errors_allowed_for_precision_lower_bound_0.90_if_all_found': min_errors_allowed(n, 0.90)}
    report = {
        'schema_version': 'extraction-validation-posthoc-v1',
        'status': 'post_hoc_not_a_pass',
        'locked_report': 'docs/verification/eligibility_validation_v1.json',
        'annotations_sha256_file': ev.ANNOTATIONS_SHA256, 'extractor_sha256': ev.EXTRACTOR_SHA256,
        'method': __doc__.split('It changes no pinned\nfile and no decision; it only describes the disagreements:')[1].strip(),
        'annotation_entries_changed_by_rule_1': changed,
        'rescored_per_type': summary,
        'remaining_disagreement_categories': {t: dict(c) for t, c in cats.items()},
        'remaining_disagreement_totals': dict(sum((collections.Counter(c) for c in cats.values()), collections.Counter())),
        'examples': {c: v[:10] for c, v in examples.items()},
        'pass_rule_attainability': attain,
        'note': 'Every type still fails after the re-scoring. Nothing is shown on the platform.',
    }
    report['report_sha256'] = digest(report)
    return report


def register_eligibility_validation_posthoc_commands(app):
    @app.cli.command('eligibility-validation-posthoc')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(output):
        """Post-hoc description of the Phase 4.1e disagreements (not part of the locked plan)."""
        report = run()
        payload = json.dumps(report, indent=1, ensure_ascii=False, allow_nan=False) + '\n'
        if output:
            with output.open('x', encoding='utf-8') as handle:
                handle.write(payload)
            click.echo(f'Saved report: {output}\nReport SHA256: {report["report_sha256"]}')
        else:
            click.echo(payload, nl=False)
