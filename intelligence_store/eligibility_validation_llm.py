"""Track C: scoring of the language-model extractor llm-c1 on the v2 validation sample (plan v3).

Uses plan v2's corpus, sample, annotation export, score_pair and decision rule unchanged (eligibility_validation_v2).
Run 1 is the primary result; run 2 measures run-to-run agreement. The comparison with extractor v1.1 is descriptive.
Research only; nothing here is used by a page.
"""
import hashlib
import json
from pathlib import Path

from . import eligibility_extractor_llm as llm
from . import eligibility_validation as v1
from . import eligibility_validation_v2 as v2

DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'eligibility_validation_plan_v3.json'
PLAN_SHA256 = '62cf708be1fbb29558a30a64c0c014f7560e68d6dcb47d2c3c4cd7859be2b854'
SCHEMA_VERSION = 'eligibility-validation-llm-report-v1'
CHUNK_SIZE = 40


def load_plan():
    return json.loads(v1._pinned(PLAN_PATH, PLAN_SHA256, 'Validation plan v3'))


def chunks(order, size=CHUNK_SIZE):
    """The trials of each input file, by position in the annotation order."""
    return [order[i:i + size] for i in range(0, len(order), size)]


def _key(entry):
    return (entry['status'], sorted((v['comparator'], float(v['value']), v['unit']) for v in entry['values']))


def score_run(annotations, order, extracted):
    pairs = []
    for nct_id in order:
        criteria = annotations[nct_id]['criteria']
        for ctype in v2.TYPES:
            s = v2.score_pair(ctype, criteria[ctype], extracted[nct_id][ctype])
            pairs.append({'nct_id': nct_id, 'type': ctype, 'annotated_status': criteria[ctype]['status'], **s})
    return pairs


def agreement(run_a, run_b, order):
    same = {t: 0 for t in v2.TYPES}
    for nct_id in order:
        for t in v2.TYPES:
            same[t] += _key(run_a[nct_id][t]) == _key(run_b[nct_id][t])
    n = len(order)
    return {'per_type': {t: same[t] / n for t in v2.TYPES}, 'overall': sum(same.values()) / (n * len(v2.TYPES)), 'trials': n}


def paired(pairs_llm, pairs_rule):
    """Per type: pairs where exactly one extractor is correct (tp or tn)."""
    ok = lambda p: p['outcome'] in ('tp', 'tn')
    out = {t: {'only_llm_correct': 0, 'only_v1_1_correct': 0, 'both': 0, 'neither': 0} for t in v2.TYPES}
    for a, b in zip(pairs_llm, pairs_rule):
        assert (a['nct_id'], a['type']) == (b['nct_id'], b['type'])
        if a['outcome'] == 'excluded_unclear':
            continue
        key = 'both' if ok(a) and ok(b) else 'only_llm_correct' if ok(a) else 'only_v1_1_correct' if ok(b) else 'neither'
        out[a['type']][key] += 1
    return out


def evaluate(annotations, order, run1, run2, rule_extracted):
    """All of the plan's outputs from already-loaded inputs (so the same code runs on synthetic data in the tests)."""
    p1, p2 = score_run(annotations, order, run1), score_run(annotations, order, run2)
    pr = score_run(annotations, order, rule_extracted)
    return {'run_1': v2.summarise(p1), 'run_2': v2.summarise(p2), 'v1_1': v2.summarise(pr),
            'run_to_run_agreement': agreement(run1, run2, order), 'paired_with_v1_1': paired(p1, pr),
            'errors_run_1': [p for p in p1 if p['outcome'] not in ('tp', 'tn', 'excluded_unclear')]}


def run_check(run1_files, run2_files, run_notes):
    """run1_files / run2_files: the pinned output files, one per input chunk, in chunk order; run_notes: the model
    identifier and date each session reported."""
    plan = load_plan()
    annotations = v2.load_annotations()
    order = v2.load_sample()['annotation_order']
    texts = dict(llm.criteria_texts(order))
    v2.check_extractor_frozen()

    def read(files):
        merged, problems, shas = {}, {}, []
        for trials, path in zip(chunks(order), files, strict=True):
            got = llm.load_outputs(path, trials)
            merged.update(got['extracted'])
            problems.update(got['problems'])
            shas.append({'file': str(path), 'sha256': got['file_sha256']})
        return merged, problems, shas

    run1, problems1, files1 = read(run1_files)
    run2, problems2, files2 = read(run2_files)
    result = evaluate(annotations['annotations'], order, run1, run2, {n: v2.ex.extract(texts[n]) for n in order})
    report = {'schema_version': SCHEMA_VERSION, 'plan_version': plan['plan_version'], 'plan_sha256': PLAN_SHA256,
              'prompt_sha256': llm.PROMPT_SHA256, 'annotations_sha256_file': v2.ANNOTATIONS_SHA256,
              'runs': {'run_1': {'files': files1, 'no_answer': problems1, 'sessions': run_notes['run_1']},
                       'run_2': {'files': files2, 'no_answer': problems2, 'sessions': run_notes['run_2']}},
              **result, 'clinical_prediction_validated': False}
    report['report_sha256'] = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()
    return report
