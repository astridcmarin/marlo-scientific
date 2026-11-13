"""The shared-error review (13 November 2026): the trial and type pairs that both eligibility extractors got wrong.

Both blind checks are done (docs/verification/eligibility_validation_v2.json, extractor v1.1;
docs/verification/eligibility_validation_llm_c1.json, Track C run 1), so the annotation may now be shown. A pair is
listed when both extractors' outcome is neither tp nor tn under plan v2's scoring (score_pair). The owner looks at each
and records whether the annotation stands, needs correcting, or the trial is unclear. Decisions do not change either
locked result: a correction would go into a new annotation version and any rescoring would be a new, labelled analysis.
"""
import hashlib
import json
import re
from pathlib import Path

from . import eligibility_extractor_llm as llm
from . import eligibility_validation_llm as val
from . import eligibility_validation_v2 as v2
from .patient_state import digest

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / 'docs' / 'development' / 'eligibility_llm_c1_outputs'
VIEW_VERSION = 'eligibility-shared-errors-v1'
DECISIONS = {
    'annotation_stands': 'The annotation is right; both extractors are wrong',
    'annotation_needs_correcting': 'The annotation should change (say how in the note)',
    'trial_unclear': 'The text is genuinely ambiguous; reasonable readers could differ',
}
LABELS = {'kidney_function_min': 'Kidney function (minimum)', 'creatinine_max': 'Serum creatinine (maximum)',
          'anc_min': 'Neutrophils (minimum)', 'platelets_min': 'Platelets (minimum)', 'hemoglobin_min': 'Haemoglobin (minimum)',
          'bilirubin_max': 'Bilirubin (maximum)', 'ast_alt_max': 'AST/ALT (maximum)', 'ecog_max': 'ECOG (maximum)'}
OUTCOMES = {'fn': 'missed a threshold you annotated', 'fp': 'reported a value you did not annotate',
            'fp+fn': 'reported a different value'}
WORDS = {'kidney_function_min': r'creatinine clearance|crcl|egfr|gfr|renal|kidney|cockcroft|ccr\b',
         'creatinine_max': r'creatinine', 'anc_min': r'neutrophil|anc\b|granulocyte',
         'platelets_min': r'platelet|plt\b', 'hemoglobin_min': r'h(a)?emoglobin|hgb|hb\b',
         'bilirubin_max': r'bilirubin', 'ast_alt_max': r'\bast\b|\balt\b|sgot|sgpt|transaminase|aminotransferase',
         'ecog_max': r'ecog|performance status|karnofsky|zubrod'}


def _llm_run_1(order):
    merged = {}
    for trials, s in zip(val.chunks(order), range(1, 6)):
        merged.update(llm.load_outputs(OUTPUTS / f'run1_session{s}.jsonl', trials)['extracted'])
    return merged


def _lines(text, ctype):
    pat = re.compile(WORDS[ctype], re.I)
    return [ln.strip(' -*•\t') for ln in re.split(r'\n+', text) if pat.search(ln)]


def build():
    annotations = v2.load_annotations()
    order = v2.load_sample()['annotation_order']
    texts = dict(llm.criteria_texts(order))
    model = _llm_run_1(order)
    items, counts = [], {t: 0 for t in v2.TYPES}
    for n in order:
        rule = v2.ex.extract(texts[n])
        for ctype in v2.TYPES:
            a = annotations['annotations'][n]['criteria'][ctype]
            sr, sl = v2.score_pair(ctype, a, rule[ctype]), v2.score_pair(ctype, a, model[n][ctype])
            if sr['outcome'] in ('tp', 'tn', 'excluded_unclear') or sl['outcome'] in ('tp', 'tn', 'excluded_unclear'):
                continue
            counts[ctype] += 1
            items.append({'id': f'{n}:{ctype}', 'nct_id': n, 'type': ctype, 'type_label': LABELS[ctype],
                          'annotated': a, 'v1_1': {'values': rule[ctype]['values'], 'outcome': sr['outcome'], 'outcome_text': OUTCOMES[sr['outcome']]},
                          'llm_run_1': {'values': model[n][ctype]['values'], 'status': model[n][ctype].get('status'), 'outcome': sl['outcome'], 'outcome_text': OUTCOMES[sl['outcome']]},
                          'relevant_lines': _lines(texts[n], ctype), 'criteria_text': texts[n]})
    view = {'view_version': VIEW_VERSION, 'annotations_sha256_file': v2.ANNOTATIONS_SHA256,
            'reports': [{'file': p, 'sha256': hashlib.sha256((ROOT / p).read_bytes()).hexdigest()}
                        for p in ('docs/verification/eligibility_validation_v2.json', 'docs/verification/eligibility_validation_llm_c1.json')],
            'counts': counts, 'total': len(items), 'items': items, 'decisions': DECISIONS}
    view['view_sha256'] = digest({k: view[k] for k in ('view_version', 'annotations_sha256_file', 'reports', 'counts', 'items')})
    return view


def validate_record(record, view=None):
    """A downloaded review record -> list of problems (empty if valid)."""
    view = view or build()
    ids = {i['id'] for i in view['items']}
    problems = []
    if record.get('view_sha256') != view['view_sha256']:
        problems.append('The record was made from a different list (view checksum differs).')
    for k, d in record.get('decisions', {}).items():
        if k not in ids:
            problems.append(f'{k}: not in the list')
        elif d.get('decision') not in DECISIONS:
            problems.append(f'{k}: unknown decision')
        elif d['decision'] == 'annotation_needs_correcting' and not (d.get('note') or '').strip():
            problems.append(f'{k}: a correction needs a note saying what the annotation should be')
    return problems
