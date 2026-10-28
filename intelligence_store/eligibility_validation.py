"""Phase 4.1e: the locked accuracy check of the eligibility extractor against the reference annotation.

Rules are those of eligibility_validation_plan_v1.json (pinned). This module was committed, with the annotation file
pinned, before the extractor was run on any validation-sample trial. Interpretations of the plan fixed here, before
running:

- Scoring is per (trial, criterion type) pair. Pairs annotated 'unclear' are excluded and counted separately.
- A pair is a true positive when it is annotated stated/multiple, every annotated value is matched by an extracted
  value, and every extracted value matches an annotated value.
- A pair is a false positive when it has any extracted value that matches no annotated value (this includes any
  value extracted for a not_stated pair). A pair is a false negative when it is annotated stated/multiple and at
  least one annotated value is not matched. A wrong value therefore makes the pair both FP and FN; a pair with all
  annotated values plus an extra value is FP only.
- Match: same comparator, same unit (guide labels), and the same number, with the plan's equivalences:
  /mm3 = /uL = cells/uL; x 10^9/L x 1000 = /mm3; g/dL x 10 = g/L; creatinine mg/dL x 88.42 = umol/L and bilirubin
  mg/dL x 17.1 = umol/L. Values must be equal after the exact factors (x 1000, x 10); only a mg/dL <-> umol/L pair may differ, by up
  to 0.5% (published conversions are rounded, e.g. 2 mg/dL written as 176.8 umol/L). 'other' matches only 'other' with an equal number.
- Equation (kidney) is reported but not required for a match.
- Precision = TP / (TP + FP pairs); recall = TP / (TP + FN pairs); Wilson 95% intervals.
- A type passes when precision >= 0.95 with lower bound >= 0.90 and recall >= 0.85 with lower bound >= 0.75, and it
  has at least 20 annotated stated/multiple pairs.
"""
import hashlib
import json
import math
from pathlib import Path

import click

from . import eligibility_extractor as ex
from .eligibility_annotations import load_sample
from .eligibility_corpus import load_corpus
from .patient_state import digest

DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'eligibility_validation_plan_v1.json'
PLAN_SHA256 = '2061c0a0a9a4ee94fd9331a47d6ca5692d23ef3cffac3081ebfacf63eb4c0b8c'
ANNOTATIONS_PATH = DATA / 'eligibility_annotations_v1.json'
ANNOTATIONS_SHA256 = '8111b4c3e70ce58c441ea223d460ee1a4a435bee7154362a6567d8a220b8c953'
EXTRACTOR_PATH = Path(ex.__file__)
EXTRACTOR_SHA256 = '54781353e752411a2f9dc27ae62e49b03390c92940180572ef18aad3d8a744ac'
REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'eligibility_validation_v1.json'
SCHEMA_VERSION = 'extraction-validation-report-v1'
TYPES = ('kidney_function_min', 'creatinine_max', 'anc_min', 'platelets_min', 'hemoglobin_min', 'bilirubin_max',
         'ast_alt_max', 'ecog_max')
RELATIVE_TOLERANCE_CONVERTED = 0.005
PASS = {'precision': 0.95, 'precision_lower': 0.90, 'recall': 0.85, 'recall_lower': 0.75, 'min_pairs': 20}


def _pinned(path, expected, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'{label} is missing or changed (pinned checksum differs); nothing was run.')
    return raw


def load_plan():
    return json.loads(_pinned(PLAN_PATH, PLAN_SHA256, 'Validation plan'))


def load_annotations(path=ANNOTATIONS_PATH):
    data = json.loads(_pinned(path, ANNOTATIONS_SHA256, 'Reference annotation'))
    claimed = data.pop('annotations_sha256')
    if digest(data) != claimed:
        raise ValueError('Reference annotation content checksum differs.')
    data['annotations_sha256'] = claimed
    return data


def check_extractor_frozen():
    _pinned(EXTRACTOR_PATH, EXTRACTOR_SHA256, 'Extractor (eligibility-extractor-v1.0)')


def _scale(ctype, unit):
    """(dimension, factor to a common unit, converted?) for the plan's equivalences."""
    if ctype in ('anc_min', 'platelets_min'):
        if unit in ('/mm3 (= /uL)', 'cells/uL'):
            return 'per_uL', 1.0
        if unit == 'x 10^9/L':
            return 'per_uL', 1000.0
    if ctype == 'hemoglobin_min':
        if unit == 'g/dL':
            return 'g/dL', 1.0
        if unit == 'g/L':
            return 'g/dL', 0.1
    if ctype == 'creatinine_max':
        if unit == 'mg/dL':
            return 'mg/dL', 1.0
        if unit == 'umol/L':
            return 'mg/dL', 1 / 88.42
    if ctype == 'bilirubin_max':
        if unit == 'mg/dL':
            return 'mg/dL', 1.0
        if unit == 'umol/L':
            return 'mg/dL', 1 / 17.1
    return unit, 1.0


def values_match(ctype, a, b):
    if a['comparator'] != b['comparator']:
        return False
    dim_a, fa = _scale(ctype, a['unit'])
    dim_b, fb = _scale(ctype, b['unit'])
    if dim_a != dim_b:
        return False
    va, vb = float(a['value']) * fa, float(b['value']) * fb
    if 'umol/L' in (a['unit'], b['unit']) and a['unit'] != b['unit']:
        return math.isclose(va, vb, rel_tol=RELATIVE_TOLERANCE_CONVERTED)
    return math.isclose(va, vb, rel_tol=1e-9, abs_tol=1e-12)


def score_pair(ctype, annotated, extracted):
    """Classify one (trial, type) pair; annotated is the annotation entry, extracted the extractor's entry."""
    if annotated['status'] == 'unclear':
        return {'outcome': 'excluded_unclear', 'tp': False, 'fp': False, 'fn': False}
    gold, got = annotated['values'], extracted['values']
    gold_matched = [any(values_match(ctype, g, e) for e in got) for g in gold]
    got_matched = [any(values_match(ctype, g, e) for g in gold) for e in got]
    positive = annotated['status'] in ('stated', 'multiple')
    fp = not all(got_matched)
    fn = positive and not all(gold_matched)
    tp = positive and not fp and not fn
    outcome = 'tp' if tp else 'tn' if not positive and not got else '+'.join(x for x, flag in (('fp', fp), ('fn', fn)) if flag)
    return {'outcome': outcome, 'tp': tp, 'fp': fp, 'fn': fn}


def wilson(successes, n, z=1.959963984540054):
    if n == 0:
        return None, None
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def summarise(pairs):
    """Per-type counts, precision, recall, intervals and the pass decision."""
    out = {}
    for ctype in TYPES:
        rows = [p for p in pairs if p['type'] == ctype]
        tp = sum(p['tp'] for p in rows)
        fp = sum(p['fp'] for p in rows)
        fn = sum(p['fn'] for p in rows)
        annotated_positive = sum(1 for p in rows if p['annotated_status'] in ('stated', 'multiple'))
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        p_lo, p_hi = wilson(tp, tp + fp)
        r_lo, r_hi = wilson(tp, tp + fn)
        if annotated_positive < PASS['min_pairs']:
            decision = 'insufficient_data'
        elif (precision is not None and recall is not None and precision >= PASS['precision'] and p_lo >= PASS['precision_lower']
              and recall >= PASS['recall'] and r_lo >= PASS['recall_lower']):
            decision = 'pass'
        else:
            decision = 'fail'
        out[ctype] = {
            'annotated': {s: sum(1 for p in rows if p['annotated_status'] == s) for s in ('stated', 'multiple', 'not_stated', 'unclear')},
            'tp': tp, 'fp_pairs': fp, 'fn_pairs': fn,
            'true_negative_pairs': sum(1 for p in rows if p['outcome'] == 'tn'),
            'precision': precision, 'precision_95ci': [p_lo, p_hi], 'recall': recall, 'recall_95ci': [r_lo, r_hi],
            'decision': decision,
        }
    return out


def _value_view(v):
    return {k: v.get(k) for k in ('comparator', 'value', 'unit', 'section', 'equation') if v.get(k) is not None}


def run_check():
    plan = load_plan()
    check_extractor_frozen()
    annotations = load_annotations()
    sample = load_sample()
    texts = {t['nct_id']: t['eligibility']['criteria_text'] for t in load_corpus()['trials']}
    pairs = []
    for nct_id in sample['annotation_order']:
        extracted = ex.extract(texts[nct_id])
        criteria = annotations['annotations'][nct_id]['criteria']
        for ctype in TYPES:
            s = score_pair(ctype, criteria[ctype], extracted[ctype])
            row = {'nct_id': nct_id, 'type': ctype, 'annotated_status': criteria[ctype]['status'], **s}
            if s['outcome'] not in ('tp', 'tn', 'excluded_unclear'):
                row['annotated_values'] = [dict(_value_view(v), sentence=v['sentence'], qualifier=v.get('qualifier') or None)
                                           for v in criteria[ctype]['values']]
                row['extracted_values'] = [dict(_value_view(v), segment=v['segment']) for v in extracted[ctype]['values']]
                if criteria[ctype].get('note'):
                    row['annotator_note'] = criteria[ctype]['note']
            if ctype == 'kidney_function_min' and s['tp']:
                row['equation_agrees'] = criteria[ctype].get('equation') == extracted[ctype]['values'][0].get('equation')
            pairs.append(row)
    per_type = summarise(pairs)
    kidney_tp = [p for p in pairs if 'equation_agrees' in p]
    report = {
        'schema_version': SCHEMA_VERSION,
        'plan_version': plan['plan_version'], 'plan_sha256': PLAN_SHA256,
        'extractor_version': ex.VERSION, 'extractor_sha256': EXTRACTOR_SHA256,
        'annotations_sha256_file': ANNOTATIONS_SHA256, 'annotations_content_sha256': annotations['annotations_sha256'],
        'sample_sha256': plan['inputs']['sample']['sha256'],
        'annotation': {
            'annotator': plan['procedure']['annotation'],
            'trials': len(sample['annotation_order']),
            'self_review': f"{len(annotations.get('reviews', {}))} trials reviewed before export",
            'corrections_before_extraction': len(annotations['corrections']),
            'corrections_note': 'All corrections were made during the annotator\'s own review round, before the extractor was run on any sample trial; none was prompted by extractor output.',
        },
        'prespecification_note': (
            'The extractor (eligibility-extractor-v1.0, sha256 above) was committed on 22 October 2026, 14:56 UTC, before any '
            'sample text was seen by its author, and has not changed since. During annotation the annotator asked about three '
            'short wordings from sample trials (an ECOG 0-2 line, a "\\>= 40" escape and a "0\\~2 points" ECOG line); no rule was '
            'changed. This scoring module and the pinned annotation file were committed before the extractor was run on the sample.'),
        'scoring_interpretation': __doc__.split('Interpretations of the plan fixed here, before\nrunning:')[1].strip(),
        'pass_rule': PASS,
        'per_type': per_type,
        'kidney_equation_agreement_among_true_positives': {'agree': sum(p['equation_agrees'] for p in kidney_tp), 'of': len(kidney_tp)},
        'passing_types': [t for t in TYPES if per_type[t]['decision'] == 'pass'],
        'errors': [p for p in pairs if p['outcome'] not in ('tp', 'tn', 'excluded_unclear')],
        'excluded_unclear': [{'nct_id': p['nct_id'], 'type': p['type']} for p in pairs if p['outcome'] == 'excluded_unclear'],
        'limitations': [
            'One annotator; accuracy is measured against one person\'s reading. A second annotation of 20 trials is recommended.',
            'Multiple myeloma interventional trials registered on ClinicalTrials.gov only.',
        ],
    }
    report['report_sha256'] = digest(report)
    return report


def register_eligibility_validation_commands(app):
    @app.cli.command('eligibility-validation-check')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(output):
        """Run the locked accuracy check of the eligibility extractor (Phase 4.1e)."""
        try:
            report = run_check()
        except (ValueError, OSError, KeyError) as exc:
            raise click.ClickException(str(exc)) from exc
        payload = json.dumps(report, indent=1, ensure_ascii=False, allow_nan=False) + '\n'
        if output:
            with output.open('x', encoding='utf-8') as handle:
                handle.write(payload)
            click.echo(f'Saved report: {output}\nReport SHA256: {report["report_sha256"]}')
        else:
            click.echo(payload, nl=False)
