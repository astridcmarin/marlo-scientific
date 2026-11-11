"""Track C: an eligibility-threshold extractor that asks a language model to read the criteria text (extractor llm-c1).

The model is given the pinned prompt (data/eligibility_extractor_llm_c1_prompt.md) and one trial's registered criteria
text per record, and returns one JSON object per trial in the format of extractor v1.1, so that the scoring of plan v2
applies unchanged. This module does not call a model. It writes the input file the model reads, and it parses and
checks the model's output file: a record that is not valid JSON in that format is "no answer" for that trial and every
type is scored as not_stated. The model runs outside this module, in a separate session that sees only the prompt and
the input file; the session, model identifier and date are recorded with each output file.

Research only; not used by any page.
"""
import hashlib
import json
from pathlib import Path

from . import eligibility_validation as v1
from .eligibility_corpus import load_corpus

DATA = Path(__file__).parent / 'data'
VERSION = 'eligibility-extractor-llm-c1'
PROMPT_PATH = DATA / 'eligibility_extractor_llm_c1_prompt.md'
PROMPT_SHA256 = '64f4da354eb669bfe9c290d5ccdb3765c0e57d19cddcaa60625fb4e727d00883'   # revision 2, frozen in the plan commit (plan v3)
TYPES = v1.TYPES
COMPARATORS = ('>=', '>', '<=', '<')
SECTIONS = ('inclusion', 'exclusion')
UNITS = {
    'kidney_function_min': ('mL/min', 'mL/min/1.73 m2', 'other'),
    'creatinine_max': ('mg/dL', 'umol/L', 'x ULN', 'other'),
    'anc_min': ('x 10^9/L', '/mm3 (= /uL)', 'cells/uL', 'x 10^3/uL (K/uL)', 'other'),
    'platelets_min': ('x 10^9/L', '/mm3 (= /uL)', 'x 10^3/uL (K/uL)', 'other'),
    'hemoglobin_min': ('g/dL', 'g/L', 'mmol/L', 'other'),
    'bilirubin_max': ('x ULN', 'mg/dL', 'umol/L', 'other'),
    'ast_alt_max': ('x ULN', 'U/L', 'other'),
    'ecog_max': ('score',),
}
EQUATIONS = ('cockcroft_gault', 'mdrd', 'ckd_epi', 'measured', 'not_stated')
MAX_VALUES = 3


def prompt_text(expected_sha256=PROMPT_SHA256):
    raw = PROMPT_PATH.read_bytes()
    if expected_sha256 is not None and hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('The extractor prompt is missing or changed; a change needs a new extractor version.')
    return raw.decode('utf-8')


def criteria_texts(nct_ids):
    by_id = {t['nct_id']: t['eligibility']['criteria_text'] for t in load_corpus()['trials']}
    return [(n, by_id[n]) for n in nct_ids]


def write_inputs(nct_ids, path):
    """One JSON line per trial: {"nct_id", "criteria_text"}. Returns the file's SHA-256."""
    lines = [json.dumps({'nct_id': n, 'criteria_text': text}, ensure_ascii=False) for n, text in criteria_texts(nct_ids)]
    Path(path).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _number(value):
    try:
        float(str(value))
    except ValueError:
        return False
    return True


def check_entry(ctype, entry):
    """The problems with one type's entry, as a list of strings (empty when valid)."""
    if not isinstance(entry, dict) or entry.get('status') not in ('stated', 'multiple', 'not_stated'):
        return ['status missing or not one of stated, multiple, not_stated']
    values = entry.get('values')
    if not isinstance(values, list):
        return ['values is not a list']
    problems = []
    if entry['status'] == 'not_stated' and values:
        problems.append('not_stated with values')
    if entry['status'] != 'not_stated' and not values:
        problems.append(f"{entry['status']} with no values")
    if len(values) > MAX_VALUES:
        problems.append(f'more than {MAX_VALUES} values')
    for v in values:
        if not isinstance(v, dict):
            problems.append('a value is not an object')
            continue
        if v.get('comparator') not in COMPARATORS:
            problems.append(f"comparator {v.get('comparator')!r}")
        if not _number(v.get('value')):
            problems.append(f"value {v.get('value')!r} is not a number")
        if v.get('unit') not in UNITS[ctype]:
            problems.append(f"unit {v.get('unit')!r} not allowed for {ctype}")
        if v.get('section') not in SECTIONS:
            problems.append(f"section {v.get('section')!r}")
        if ctype == 'kidney_function_min' and v.get('equation', 'not_stated') not in EQUATIONS:
            problems.append(f"equation {v.get('equation')!r}")
    return problems


def parse_record(raw_answer):
    """The model's answer for one trial (a string) -> (extracted, problems). Invalid -> every type not_stated."""
    try:
        answer = json.loads(raw_answer) if isinstance(raw_answer, str) else raw_answer
    except json.JSONDecodeError as exc:
        return _no_answer(), [f'not valid JSON: {exc.msg}']
    if not isinstance(answer, dict) or set(TYPES) - set(answer):
        return _no_answer(), ['not an object with all eight types']
    problems = {t: check_entry(t, answer[t]) for t in TYPES}
    if any(problems.values()):
        return _no_answer(), [f'{t}: {p}' for t, ps in problems.items() for p in ps]
    extracted = {}
    for t in TYPES:
        values = [{'comparator': v['comparator'], 'value': str(v['value']), 'unit': v['unit'], 'section': v['section'],
                   'segment': v.get('segment', ''), **({'equation': v.get('equation', 'not_stated')} if t == 'kidney_function_min' else {})}
                  for v in answer[t]['values']]
        extracted[t] = {'status': answer[t]['status'], 'values': values}
    return extracted, []


def _no_answer():
    return {t: {'status': 'not_stated', 'values': []} for t in TYPES}


def load_outputs(path, nct_ids):
    """Read a model output file (one JSON line per trial: {"nct_id", "answer"}) -> per-trial extraction and problems.
    A trial with no line, or more than one, is no answer."""
    lines = [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    by_id = {}
    for line in lines:
        by_id.setdefault(line.get('nct_id'), []).append(line.get('answer'))
    out, problems = {}, {}
    for n in nct_ids:
        answers = by_id.get(n, [])
        if len(answers) != 1:
            out[n], problems[n] = _no_answer(), [f'{len(answers)} answers']
            continue
        out[n], p = parse_record(answers[0])
        if p:
            problems[n] = p
    return {'extracted': out, 'problems': problems, 'file_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()}
