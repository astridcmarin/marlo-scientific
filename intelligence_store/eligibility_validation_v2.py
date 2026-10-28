"""Phase 4.2c: the locked accuracy check of extractor v1.1 against the v2 reference annotation.

Rules are those of eligibility_validation_plan_v2.json (pinned). Extractor v1.1 is pinned here by checksum before the v2
annotation is finished, so it cannot change after this commit. The annotation checksum is added (in its own commit)
when the export arrives, before the extractor is run on any v2 sample trial; until then the check refuses to run.

Scoring is that of v1 (eligibility_validation.py: pair outcomes, Wilson intervals), with the v2 plan's additions:
K/uL (x 10^3/uL) = x 10^9/L; ECOG '< k' = '<= k-1' and '> k' = '>= k+1' on both sides; pass rule precision >= 0.90
(lower bound >= 0.80), recall >= 0.80 (lower bound >= 0.70), at least 30 annotated stated/multiple pairs.
"""
import json
from pathlib import Path

import click

from . import eligibility_extractor_v1_1 as ex
from . import eligibility_validation as v1
from .eligibility_annotations_v2 import load_sample
from .eligibility_corpus import load_corpus
from .patient_state import digest

DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'eligibility_validation_plan_v2.json'
PLAN_SHA256 = '8a543d7df767afd3ec729a6c5c61d22dd9324392dccac59412cac4ee9e8643a8'
ANNOTATIONS_PATH = DATA / 'eligibility_annotations_v2.json'
ANNOTATIONS_SHA256 = None          # set when the v2 export is pinned, before the extractor runs on the v2 sample
EXTRACTOR_PATH = Path(ex.__file__)
EXTRACTOR_SHA256 = 'bfc57df7e629000c8a6bcdebb55d28f38716cce99329b344830668c70aedf08f'
REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'eligibility_validation_v2.json'
SCHEMA_VERSION = 'extraction-validation-report-v2'
TYPES = v1.TYPES
PASS = {'precision': 0.90, 'precision_lower': 0.80, 'recall': 0.80, 'recall_lower': 0.70, 'min_pairs': 30}
K_UL = 'x 10^3/uL (K/uL)'


def load_plan():
    return json.loads(v1._pinned(PLAN_PATH, PLAN_SHA256, 'Validation plan v2'))


def check_extractor_frozen():
    v1._pinned(EXTRACTOR_PATH, EXTRACTOR_SHA256, 'Extractor (eligibility-extractor-v1.1)')


def load_annotations(path=ANNOTATIONS_PATH, expected=None):
    expected = expected or ANNOTATIONS_SHA256
    if not expected:
        raise ValueError('The v2 reference annotation is not pinned yet; nothing was run.')
    data = json.loads(v1._pinned(path, expected, 'Reference annotation v2'))
    claimed = data.pop('annotations_sha256')
    if digest(data) != claimed:
        raise ValueError('Reference annotation v2 content checksum differs.')
    data['annotations_sha256'] = claimed
    return data


def _ecog(v):
    v = dict(v)
    if v['comparator'] == '<':
        v['comparator'], v['value'] = '<=', str(int(float(v['value'])) - 1)
    elif v['comparator'] == '>':
        v['comparator'], v['value'] = '>=', str(int(float(v['value'])) + 1)
    return v


def _k_ul(ctype, v):
    if ctype in ('anc_min', 'platelets_min') and v.get('unit') == K_UL:
        return dict(v, unit='x 10^9/L')          # 1 K/uL = 1000/uL = 1 x 10^9/L
    return v


def normalise(ctype, v):
    v = _k_ul(ctype, v)
    return _ecog(v) if ctype == 'ecog_max' else v


def values_match(ctype, a, b):
    return v1.values_match(ctype, normalise(ctype, a), normalise(ctype, b))


def score_pair(ctype, annotated, extracted):
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


def summarise(pairs):
    return v1.summarise(pairs, PASS)


def run_check(annotations=None):
    plan = load_plan()
    check_extractor_frozen()
    annotations = annotations or load_annotations()
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
                row['annotated_values'] = [{k: v.get(k) for k in ('comparator_as_written', 'describes', 'comparator', 'value', 'unit', 'section', 'sentence', 'qualifier')}
                                           for v in criteria[ctype]['values']]
                row['extracted_values'] = [{k: v.get(k) for k in ('comparator', 'value', 'unit', 'section', 'segment')}
                                           for v in extracted[ctype]['values']]
                if criteria[ctype].get('note'):
                    row['annotator_note'] = criteria[ctype]['note']
            if ctype == 'kidney_function_min' and s['tp']:
                row['equation_agrees'] = criteria[ctype].get('equation') == extracted[ctype]['values'][0].get('equation')
            pairs.append(row)
    per_type = summarise(pairs)
    kidney_tp = [p for p in pairs if 'equation_agrees' in p]
    report = {
        'schema_version': SCHEMA_VERSION, 'plan_version': plan['plan_version'], 'plan_sha256': PLAN_SHA256,
        'extractor_version': ex.VERSION, 'extractor_sha256': EXTRACTOR_SHA256,
        'annotations_sha256_file': ANNOTATIONS_SHA256, 'annotations_content_sha256': annotations['annotations_sha256'],
        'sample_sha256': plan['inputs']['sample']['sha256'],
        'annotation': {'trials': len(sample['annotation_order']), 'reviewed_before_export': annotations.get('reviewed'),
                       'corrections_before_extraction': len(annotations['corrections'])},
        'pass_rule': PASS, 'per_type': per_type,
        'kidney_equation_agreement_among_true_positives': {'agree': sum(p['equation_agrees'] for p in kidney_tp), 'of': len(kidney_tp)},
        'passing_types': [t for t in TYPES if per_type[t]['decision'] == 'pass'],
        'errors': [p for p in pairs if p['outcome'] not in ('tp', 'tn', 'excluded_unclear')],
        'excluded_unclear': [{'nct_id': p['nct_id'], 'type': p['type']} for p in pairs if p['outcome'] == 'excluded_unclear'],
        'limitations': ['One annotator; accuracy is measured against one person\'s reading.',
                        'Multiple myeloma interventional trials registered on ClinicalTrials.gov only.'],
    }
    report['report_sha256'] = digest(report)
    return report


def register_eligibility_validation_v2_commands(app):
    @app.cli.command('eligibility-validation-v2-check')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(output):
        """Run the locked v2 accuracy check of extractor v1.1 (Phase 4.2c)."""
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

