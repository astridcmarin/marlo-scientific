"""Phase 4.1f: protocol benchmarking across the pinned myeloma eligibility corpus.

Runs the frozen extractor (eligibility-extractor-v1.1) over every trial in the corpus and summarises, per criterion
type, which thresholds trials used, with each count traceable to the trials and the clause it came from.

What is shown is decided by the locked v2 accuracy check (docs/verification/eligibility_validation_v2.json): a type
appears only if that report exists, was produced with the same plan and extractor checksums, and lists the type as
passing. Until then nothing is shown. A local preview of unvalidated types can be switched on with the app setting
ELIGIBILITY_BENCHMARK_PREVIEW; it is labelled as unvalidated on every view and is never on by default.

Grouping rules (no silent conversions across measures):
- ANC and platelets: /uL, cells/uL, x 10^9/L and K/uL are the same quantity (exact factors) and are grouped per uL.
- Haemoglobin: g/dL and g/L are grouped (x 10); mmol/L stays separate.
- Creatinine and bilirubin: mg/dL and umol/L are grouped by the plan's factors (88.42, 17.1), rounded to 2 decimals;
  x ULN stays separate (it cannot be converted to an absolute value).
- Kidney function: mL/min (creatinine clearance) and mL/min/1.73 m2 (eGFR) are different measures and stay separate.
- A threshold in the usual direction (a lower limit for counts and kidney function, an upper limit for creatinine,
  bilirubin, AST/ALT and ECOG) and one in the other direction (trials of impaired kidney function) are separate groups.
"""
import collections
import functools
import hashlib
import json
from pathlib import Path

from . import eligibility_extractor_v1_1 as ex
from . import eligibility_validation_v2 as v2
from .eligibility_corpus import CORPUS_CONTENT_SHA256, load_corpus
from .eligibility_sample import phase_group

REPORT_PATH = v2.REPORT_PATH
LABELS = {
    'kidney_function_min': 'Kidney function (CrCl or eGFR)', 'creatinine_max': 'Serum creatinine',
    'anc_min': 'Absolute neutrophil count', 'platelets_min': 'Platelet count', 'hemoglobin_min': 'Haemoglobin',
    'bilirubin_max': 'Total bilirubin', 'ast_alt_max': 'AST/ALT', 'ecog_max': 'ECOG performance status',
}
USUAL_LOWER = {'kidney_function_min', 'anc_min', 'platelets_min', 'hemoglobin_min'}
PHASE_LABELS = {'phase_1': 'Phase 1', 'phase_1_2': 'Phase 1/2', 'phase_2': 'Phase 2', 'phase_2_3_or_3': 'Phase 2/3 or 3',
                'other': 'Other or not reported'}
SYMBOL = {'>=': '≥', '<=': '≤', '>': '>', '<': '<'}


def extractor_sha256():
    return hashlib.sha256(Path(ex.__file__).read_bytes()).hexdigest()


def validation_status(path=REPORT_PATH):
    """Which types the locked v2 check passed, read only from a report that matches the pinned plan and extractor."""
    path = Path(path)
    if not path.exists():
        return {'available': False, 'reason': 'The v2 accuracy check has not been run yet (reference annotation in progress).',
                'passing_types': [], 'per_type': {}}
    report = json.loads(path.read_text(encoding='utf-8'))
    if report.get('plan_sha256') != v2.PLAN_SHA256 or report.get('extractor_sha256') != v2.EXTRACTOR_SHA256 \
            or extractor_sha256() != v2.EXTRACTOR_SHA256:
        return {'available': False, 'reason': 'The accuracy report does not match the pinned plan or extractor.',
                'passing_types': [], 'per_type': {}}
    return {'available': True, 'reason': None, 'passing_types': list(report.get('passing_types', [])),
            'per_type': report.get('per_type', {}), 'report_sha256': report.get('report_sha256')}


def group(ctype, value):
    """(group key, label, number in the group's unit) for one extracted value."""
    comp, unit, number = value['comparator'], value['unit'], float(value['value'])
    usual = (comp in ('>=', '>')) == (ctype in USUAL_LOWER)
    direction = 'usual' if usual else 'other'
    if ctype in ('anc_min', 'platelets_min'):
        factor = {'/mm3 (= /uL)': 1.0, 'cells/uL': 1.0, 'x 10^9/L': 1000.0, 'x 10^3/uL (K/uL)': 1000.0}.get(unit)
        dim, unit_label = ('per_uL', '/µL') if factor else (unit, unit)
        number = number * factor if factor else number
    elif ctype == 'hemoglobin_min' and unit in ('g/dL', 'g/L'):
        dim, unit_label, number = 'g/dL', 'g/dL', number / 10.0 if unit == 'g/L' else number
    elif ctype in ('creatinine_max', 'bilirubin_max') and unit in ('mg/dL', 'umol/L'):
        div = 88.42 if ctype == 'creatinine_max' else 17.1
        dim, unit_label, number = 'mg/dL', 'mg/dL', round(number / div, 2) if unit == 'umol/L' else number
    elif ctype == 'ecog_max':
        dim, unit_label = 'score', ''
        if comp == '<':
            comp, number = '<=', number - 1
        elif comp == '>':
            comp, number = '>=', number + 1
    else:
        dim, unit_label = unit, unit.replace('x ULN', '× ULN').replace('mL/min/1.73 m2', 'mL/min/1.73 m²')
    return (dim, direction), unit_label, comp, number


def _fmt(number):
    return f'{number:,.0f}' if number >= 1000 or number == int(number) else f'{number:g}'


@functools.lru_cache(maxsize=1)
def extracted_corpus():
    """Extractor output for every corpus trial with criteria text (about 20 s; cached per process)."""
    corpus = load_corpus()
    rows = []
    for t in corpus['trials']:
        text = t['eligibility']['criteria_text']
        if not text:
            continue
        rows.append({'nct_id': t['nct_id'], 'title': t.get('brief_title') or '', 'status': t.get('overall_status') or 'UNKNOWN',
                     'phase_group': phase_group(t.get('phases') or []), 'start_year': _year(t.get('start_date')),
                     'extracted': ex.extract(text)})
    return {'corpus_content_sha256': CORPUS_CONTENT_SHA256, 'extractor_version': ex.VERSION,
            'extractor_sha256': extractor_sha256(), 'trials': rows}


def _year(date):
    try:
        return int(str(date)[:4])
    except (TypeError, ValueError):
        return None


def filter_trials(rows, phase=None, status=None, start_from=None, start_to=None):
    out = []
    for r in rows:
        if phase and r['phase_group'] != phase:
            continue
        if status and r['status'] != status:
            continue
        if start_from and (r['start_year'] is None or r['start_year'] < start_from):
            continue
        if start_to and (r['start_year'] is None or r['start_year'] > start_to):
            continue
        out.append(r)
    return out


def distribution(rows, ctype):
    """Threshold groups for one type: each bin is (comparator, number) in its group's unit, with its trials."""
    groups = collections.OrderedDict()
    stated = multiple = 0
    for r in rows:
        entry = r['extracted'][ctype]
        if entry['status'] == 'not_stated':
            continue
        stated += 1
        multiple += entry['status'] == 'multiple'
        seen = set()
        for i, v in enumerate(entry['values']):
            key, unit_label, comp, number = group(ctype, v)
            if (key, comp, number) in seen:
                continue
            seen.add((key, comp, number))
            g = groups.setdefault(key, {'unit': unit_label, 'direction': key[1], 'bins': collections.OrderedDict()})
            b = g['bins'].setdefault((comp, number), {'comparator': comp, 'value': number,
                                                      'label': f"{SYMBOL[comp]} {_fmt(number)} {unit_label}".strip(), 'trials': []})
            b['trials'].append({'nct_id': r['nct_id'], 'title': r['title'], 'segment': v['segment'], 'section': v['section'],
                                'first_value': i == 0, 'status': r['status'], 'phase_group': r['phase_group'],
                                'start_year': r['start_year']})
    out = []
    for key, g in groups.items():
        bins = sorted(g['bins'].values(), key=lambda b: (b['value'], b['comparator']))
        out.append({'key': f'{key[0]}|{key[1]}', 'unit': g['unit'], 'direction': g['direction'],
                    'trials': len({t['nct_id'] for b in bins for t in b['trials']}),
                    'bins': [dict(b, n=len(b['trials'])) for b in bins]})
    out.sort(key=lambda g: (g['direction'] != 'usual', -g['trials']))
    return {'type': ctype, 'label': LABELS[ctype], 'trials_in_selection': len(rows), 'stated': stated,
            'multiple': multiple, 'not_stated': len(rows) - stated, 'groups': out}


def _strictness(ctype, comp, number):
    """A number that grows with strictness: for a lower limit, higher is stricter; for an upper limit, lower is stricter.
    A strict comparator (>, <) is a hair stricter than the inclusive one at the same number."""
    eps = 1e-9 * max(1.0, abs(number))
    if comp in ('>=', '>'):
        return number + (eps if comp == '>' else 0.0)
    return -(number - (eps if comp == '<' else 0.0))


def compare_draft(rows, ctype, comparator, value, unit):
    """Compare a draft threshold with each trial's first value in the same group (same measure, unit family, direction)."""
    draft = {'comparator': comparator, 'value': str(value), 'unit': unit}
    key, unit_label, comp, number = group(ctype, draft)
    target = _strictness(ctype, comp, number)
    stricter, equal, permissive = [], [], []
    for r in rows:
        entry = r['extracted'][ctype]
        if not entry['values']:
            continue
        v = entry['values'][0]
        k2, _, c2, n2 = group(ctype, v)
        if k2 != key:
            continue
        s = _strictness(ctype, c2, n2)
        bucket = stricter if s > target + 1e-12 else permissive if s < target - 1e-12 else equal
        bucket.append(r['nct_id'])
    total = len(stricter) + len(equal) + len(permissive)
    return {'draft_label': f"{SYMBOL[comp]} {_fmt(number)} {unit_label}".strip(), 'comparable_trials': total,
            'stricter': stricter, 'equal': equal, 'more_permissive': permissive,
            'note': 'Compared with the first threshold each trial states for this measure, in the same unit family and direction.'}
