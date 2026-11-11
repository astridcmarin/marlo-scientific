"""Development scores of the language-model extractor llm-c1 on the v1 validation sample (plan v3, 11 November 2026).

Reads the stored model outputs in docs/development/eligibility_llm_c1/ and writes
docs/development/eligibility_llm_c1_development.json. Run from the repository root.

The v1 annotation follows guide v1, which recorded exclusion comparators inconsistently and used "multiple" for
exceptions, so two scores are given per type: plan v2's score_pair as it stands, and a direction-free score (value
and unit only). Both are a guide for development, not a measure of accuracy; extractor v1.1 is shown on the same
trials, and it was tuned on them.
"""
import copy
import hashlib
import json
from pathlib import Path

from intelligence_store import eligibility_extractor_llm as llm
from intelligence_store import eligibility_extractor_v1_1 as ex
from intelligence_store import eligibility_validation as v1
from intelligence_store import eligibility_validation_v2 as v2

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / 'docs' / 'development' / 'eligibility_llm_c1'
OUT = ROOT / 'docs' / 'development' / 'eligibility_llm_c1_development.json'
REVISIONS = (
    {'revision': 1, 'prompt': DEV / 'prompt_revision_1.md', 'outputs': DEV / 'revision_1_v1_sample.jsonl', 'run_on': '2026-11-11'},
    {'revision': 2, 'prompt': llm.PROMPT_PATH, 'outputs': DEV / 'revision_2_v1_sample.jsonl', 'run_on': '2026-11-11'},
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def undirected(entry):
    e = copy.deepcopy(entry)
    for v in e['values']:
        v['comparator'] = '>='
    return e


def scores(annotations, order, extracted):
    strict, loose = [], []
    for n in order:
        for t in v2.TYPES:
            gold, got = annotations[n]['criteria'][t], extracted[n][t]
            base = {'nct_id': n, 'type': t, 'annotated_status': gold['status']}
            strict.append({**base, **v2.score_pair(t, gold, got)})
            loose.append({**base, **v2.score_pair(t, undirected(gold), undirected(got))})
    brief = lambda s: {t: {k: s[t][k] for k in ('tp', 'fp_pairs', 'fn_pairs', 'precision', 'recall')} for t in v2.TYPES}
    return {'plan_v2_score_pair': brief(v1.summarise(strict, v2.PASS)), 'direction_free': brief(v1.summarise(loose, v2.PASS))}


def build():
    annotations_path = v1.ANNOTATIONS_PATH
    annotations = v1.load_annotations()['annotations']
    order = json.loads((v1.DATA / 'eligibility_validation_sample_v1.json').read_text())['annotation_order']
    texts = dict(llm.criteria_texts(order))
    revisions = []
    for r in REVISIONS:
        got = llm.load_outputs(r['outputs'], order)
        revisions.append({'revision': r['revision'], 'prompt': str(Path(r['prompt']).relative_to(ROOT)), 'prompt_sha256': sha(r['prompt']),
                          'outputs': str(r['outputs'].relative_to(ROOT)), 'outputs_sha256': got['file_sha256'],
                          'model_identifier': 'claude-fable-5-2', 'sessions': 3, 'run_on': r['run_on'],
                          'no_answer': len(got['problems']), **scores(annotations, order, got['extracted'])})
    return {'schema_version': 'extractor-development-record-v1', 'extractor': llm.VERSION, 'recorded_on': '2026-11-11',
            'data': {'annotations': str(Path(annotations_path).relative_to(ROOT)), 'trials': len(order),
                     'note': 'v1 validation sample, annotated with guide v1 and already seen; development only'},
            'revisions': revisions,
            'v1_1_on_the_same_trials': {'note': 'extractor v1.1 was tuned on these trials, so its scores here are not a fair comparison',
                                        **scores(annotations, order, {n: ex.extract(texts[n]) for n in order})},
            'clinical_prediction_validated': False}


if __name__ == '__main__':
    OUT.write_text(json.dumps(build(), indent=1, ensure_ascii=False) + '\n')
    print(OUT.relative_to(ROOT), sha(OUT))
