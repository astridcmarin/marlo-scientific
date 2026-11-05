"""Kidney-function classifications and measures, side by side (reviewer's checklist R1 and R2, 5 November 2026).

Three ways of grouping kidney function meet on the lenalidomide pages, and the models use three different measures:
- the FDA 2024 renal-impairment guidance's Table 1 categories (estimated function, eGFR in mL/min or Cockcroft-Gault);
- CC-5013-PK-001's groups, which the body map's bands follow (measured 24-hour creatinine clearance);
- the REVLIMID label's dose table (Cockcroft-Gault).

Every category bound and every measure statement is read from a pinned source file by JSON pointer, after its checksum
is verified; nothing is copied by hand. The only platform-written text is in `NOTES`, marked as such on the pages.
The mapping between schemes is interval overlap on the stated bounds: it says which ranges share values, not that
the groups are equivalent (they rest on different measures). Nothing here classifies a patient or proposes a dose.
"""
import hashlib
import json
from pathlib import Path

from .patient_state import digest

ROOT = Path(__file__).resolve().parent.parent
DATA = 'intelligence_store/data/'
VIEW_VERSION = 'kidney-function-classifications-v1.0'

SOURCES = {
    'fda_2024': (DATA + 'fda_renal_impairment_guidance_2024_v1.json',
                 '9fb3498ab4d479a2ce4d523f85c5fc29648621a0cf084ef732945ce3fda362b5',
                 'FDA, Pharmacokinetics in Patients with Impaired Renal Function, final guidance, March 2024'),
    'ema_2008': (DATA + 'lenalidomide_renal_pathways_evidence_v1.json',
                 'e7c62bc477bfc6170f42f1f01e5935ea222bec0fbf513da718178030c42d2c8f',
                 'EMA 2008 assessment report, CC-5013-PK-001 (EMEA/CHMP/249329/2008)'),
    'reconciliation': (DATA + 'lenalidomide_renal_source_reconciliation_v3.json',
                       '8d076dfbb4d50ed940064c1cab798b8a3b8eca684d6ac5b383e8487d847f5292',
                       'Lenalidomide renal source reconciliation v3 (Chen 2007 and earlier labels)'),
    'label_2023': (DATA + 'lenalidomide_label_2023_v1.json',
                   'd4b02134613dc45d6b039999b37d9c94ccbc047cc0b7e811b77278c868e47a9a',
                   'REVLIMID prescribing information, revision 3/2023'),
    'hughes_extract': (DATA + 'hughes_parameter_extract_v1.json',
                       '8199220db206c3e78fd5abc40191602d5b59e6275f5c77d9e43e0f7c90ae5f74',
                       'Hughes 2019 parameter extract'),
    'hughes_weight': (DATA + 'hughes_weight_basis_assessment_v1.json',
                      'bbaffa714dd5bd2fb9773a1620fb022c35bd90175b972d0a0855d9f6916be2c6',
                      'Hughes 2019 Cockcroft-Gault weight-basis assessment'),
    'kim_extract': (DATA + 'kim_2026_model_extract_v1.json',
                    'c8d4c4bff1d84adae8016d0a1e6e864423b578d7564f2ffbf81c70501e0c25af',
                    'Kim 2026 model extract'),
    'bridoux_design': (DATA + 'lenalidomide_bridoux_design_v1.json',
                       '1af2d005528a18088382225482a3eaa32ac3c68f4f6529c5ee7958e8c1605eac',
                       'Bridoux 2016 study design extract'),
}

# Each measure row: which source says what, by pointer. `note` is platform-written and labelled so on the page.
MEASURES = [
    {'id': 'cc5013', 'who': 'CC-5013-PK-001, the renal study (the body map\'s bands)',
     'facts': [('ema_2008', '/renal_function_measure/value', 'EMA 2008, page 20', 'Measure'),
               ('reconciliation', '/sources/chen_2007/quotes/stratification/quote', 'Chen 2007', 'Publication (quoted)')],
     'note': 'Measured, not estimated. The guidance\'s categories are for estimated function (eGFR or Cockcroft-Gault), '
             'so the study\'s groups and the guidance\'s categories rest on different measures.'},
    {'id': 'label', 'who': 'REVLIMID label, dose table (Table 3)',
     'facts': [('label_2023', '/renal_dose_adjustments/table', 'Section 2.6', 'Table')],
     'note': 'Cockcroft-Gault, the guidance\'s eCLcr. The label does not state which body weight to use.'},
    {'id': 'hughes', 'who': 'Hughes 2019 population model',
     'facts': [('hughes_extract', '/input_definitions/crcl', None, 'Covariate'),
               ('hughes_weight', '/source_facts/0/fact', 'Section 2.3', 'Paper'),
               ('hughes_weight', '/status', None, 'Weight basis'),
               ('hughes_weight', '/decision/primary_assumption', None, 'Weight the platform assumes'),
               ('hughes_weight', '/decision/sensitivity_bases', None, 'Sensitivity cases')],
     'note': 'The guidance suggests ideal or adjusted body weight in overweight or obese people. The paper states no '
             'weight; the platform assumes ideal body weight (Devine) and shows the others as sensitivity cases. '
             'The question is open with the authors.'},
    {'id': 'kim', 'who': 'Kim 2026 population model',
     'facts': [('kim_extract', '/covariate_definitions/egfr/formula', None, 'Equation'),
               ('kim_extract', '/covariate_definitions/egfr/unit', None, 'Unit'),
               ('kim_extract', '/transcription_notes/2', None, 'Transcription note')],
     'note': 'Indexed to 1.73 m2, as published. The guidance prefers eGFR in mL/min (not indexed) for dosing; the '
             'platform runs the model as published and does not convert. Body surface area enters the model\'s '
             'clearance as a separate covariate.'},
    {'id': 'bridoux', 'who': 'Bridoux 2016, myeloma patients (outside check)',
     'facts': [('bridoux_design', '/design/renal_function_measure/value', None, 'Measure'),
               ('bridoux_design', '/not_reported/3', None, 'Not reported by the study')],
     'note': 'Cockcroft-Gault, weight not reported. Both population models were checked against these groups.'},
]

STUDY_GROUP_LABELS = {'normal': 'Normal', 'mild': 'Mild', 'moderate': 'Moderate', 'severe_without_dialysis': 'Severe, not on dialysis'}
NOTES = {
    'mapping': 'Ranges that share values, from the stated bounds only. The schemes rest on different measures '
               '(measured clearance, Cockcroft-Gault, eGFR), so overlapping ranges are not the same groups of people.',
    'scope': 'Footnote c of the guidance: the categories are for dedicated renal impairment studies, not for '
             'classifying kidney disease. Nothing here classifies a patient or proposes a dose.',
}


class ClassificationError(ValueError):
    pass


def _resolve(document, pointer):
    node = document
    for token in pointer[1:].split('/'):
        token = token.replace('~1', '/').replace('~0', '~')
        if isinstance(node, list):
            node = node[int(token)]
        elif isinstance(node, dict) and token in node:
            node = node[token]
        else:
            raise ClassificationError(f'Pointer {pointer!r} does not resolve.')
    return node


def _load_sources():
    docs = {}
    for alias, (path, sha, _title) in SOURCES.items():
        raw = (ROOT / path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ClassificationError(f'{path} is missing or changed; the comparison was not built.')
        docs[alias] = json.loads(raw)
    return docs


def _interval(lo, lo_incl, hi, hi_incl):
    return {'lower': lo, 'lower_inclusive': lo_incl, 'upper': hi, 'upper_inclusive': hi_incl}


def _from_bounds(b):
    """Bounds as written in the pinned files: lower_inclusive / lower_exclusive / lower, and the same for upper."""
    lo = next((b[k] for k in ('lower_inclusive', 'lower_exclusive', 'lower') if k in b), None)
    hi = next((b[k] for k in ('upper_inclusive', 'upper_exclusive', 'upper') if k in b), None)
    return _interval(lo, 'lower_inclusive' in b, hi, 'upper_inclusive' in b)


def contains(iv, x):
    if iv['lower'] is not None and (x < iv['lower'] or (x == iv['lower'] and not iv['lower_inclusive'])):
        return False
    if iv['upper'] is not None and (x > iv['upper'] or (x == iv['upper'] and not iv['upper_inclusive'])):
        return False
    return True


def overlap(a, b):
    """'range' when two intervals share a range of values, 'point' when they share a single boundary value, else None."""
    lo = max((v for v in (a['lower'], b['lower']) if v is not None), default=None)
    hi = min((v for v in (a['upper'], b['upper']) if v is not None), default=None)
    if lo is None or hi is None or lo < hi:
        return 'range'
    return 'point' if lo == hi and contains(a, lo) and contains(b, lo) else None


def text(iv):
    lo, hi = iv['lower'], iv['upper']
    if lo is None:
        return f"{'≤' if iv['upper_inclusive'] else '<'} {hi:g}"
    if hi is None:
        return f"{'≥' if iv['lower_inclusive'] else '>'} {lo:g}"
    left = f'{lo:g}' if iv['lower_inclusive'] else f'> {lo:g}'
    return f"{left} to {'' if iv['upper_inclusive'] else '< '}{hi:g}"


def schemes(docs=None):
    docs = docs or _load_sources()
    fda = docs['fda_2024']['table_1']
    fda_rows = [{'id': c['id'], 'label': c['description'], 'printed': c['printed'],
                 'interval': _interval(c['range_ml_min']['lower_inclusive'], True, c['range_ml_min']['upper_exclusive'], False)}
                for c in fda['categories']]
    study_rows = [{'id': g['group'], 'label': STUDY_GROUP_LABELS[g['group']], 'interval': _from_bounds(g['clcr_ml_min'])}
                  for g in docs['ema_2008']['groups']]
    label_rows = [{'id': f'row_{i}', 'label': f'Row {i + 1}' + (', requiring dialysis' if r['dialysis'] else ''),
                   'quoted_dose': r['mm_combination'],
                   'interval': _interval(r['crcl_ml_min'][0], r['crcl_ml_min'][0] is not None, r['crcl_ml_min'][1],
                                         r['crcl_ml_min'][0] is not None),
                   'dialysis': r['dialysis']}
                  for i, r in enumerate(docs['label_2023']['renal_dose_adjustments']['rows'])]
    for r in fda_rows + study_rows + label_rows:
        r['range_text'] = text(r['interval']) + ' mL/min'
    return {
        'fda_2024': {'title': 'FDA 2024 renal-impairment guidance, Table 1', 'table_title': fda['title'], 'location': fda['location'], 'measure': 'eGFR in mL/min, or Cockcroft-Gault',
                     'rows': fda_rows, 'range_reading': fda['range_reading'], 'scope_footnote': fda['footnotes']['c']},
        'cc5013': {'title': 'CC-5013-PK-001 groups (the body map\'s bands)', 'location': 'EMA 2008, page 20',
                   'measure': 'measured 24-hour creatinine clearance', 'rows': study_rows},
        'label': {'title': 'REVLIMID label, Table 3 dose rows (multiple myeloma, combination)', 'location': 'Section 2.6',
                  'measure': 'Cockcroft-Gault creatinine clearance', 'rows': label_rows},
    }


def build(docs=None):
    docs = docs or _load_sources()
    sch = schemes(docs)
    mapping = []
    def shared(cat, rows):
        out = []
        for r in rows:
            kind = overlap(cat['interval'], r['interval'])
            if kind:
                point = max(v for v in (cat['interval']['lower'], r['interval']['lower']) if v is not None) \
                    if kind == 'point' else None
                out.append({'label': r['label'], 'range_text': r['range_text'], 'overlap': kind,
                            'note': f'shares only the value {point:g} mL/min' if kind == 'point' else None})
        return out

    for cat in sch['fda_2024']['rows']:
        mapping.append({'fda': cat['id'], 'fda_label': cat['label'], 'fda_range': cat['range_text'],
                        'cc5013': shared(cat, sch['cc5013']['rows']), 'label': shared(cat, sch['label']['rows'])})
    measures = []
    for m in MEASURES:
        facts = [{'field': field, 'source': SOURCES[ref][2], 'location': loc, 'value': _resolve(docs[ref], ptr),
                  'file': SOURCES[ref][0], 'pointer': ptr} for ref, ptr, loc, field in m['facts']]
        measures.append({'id': m['id'], 'who': m['who'], 'facts': facts, 'platform_note': m['note']})
    guidance = docs['fda_2024']
    view = {
        'view_version': VIEW_VERSION, 'drug': 'lenalidomide', 'schemes': sch, 'mapping': mapping, 'measures': measures,
        'guidance_quotes': [dict(q, topic=k) for k, q in guidance['renal_function_measure'].items()],
        'notes': NOTES,
        'sources': [{'alias': a, 'file': p, 'sha256': s, 'title': t} for a, (p, s, t) in SOURCES.items()],
        'guidance_extraction': guidance['source']['extraction'], 'guidance_url': guidance['source']['url'],
        'clinical_prediction_validated': False,
    }
    view['view_sha256'] = digest(view)
    return view


def classify(crcl_ml_min, docs=None):
    """Which range of each scheme contains a value. The value's measure is not converted: the caller says what it is."""
    sch = schemes(docs)
    out = {}
    for key, scheme in sch.items():
        rows = [r for r in scheme['rows'] if not r.get('dialysis') and contains(r['interval'], crcl_ml_min)]
        out[key] = {'title': scheme['title'], 'measure': scheme['measure'],
                    'row': ({'label': rows[0]['label'], 'range_text': rows[0]['range_text']} if rows else None),
                    'note': None if rows else 'No range in this scheme contains the value.'}
    return out
