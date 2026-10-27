"""Phase 4.1c: reference annotation of the eligibility validation sample (rules in ELIGIBILITY_ANNOTATION_GUIDE.md).

Annotations are saved to a local JSON file (instance/eligibility_annotations_v1.json by default; never committed)
after every trial, with the time. Re-saving a trial needs a reason and keeps the earlier version in a correction log.
When all 120 trials are done, `eligibility-annotations-export` writes a checksummed copy for pinning. Nothing here
reads or runs the extractor.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import tempfile
import unicodedata

import click

from .eligibility_corpus import load_corpus
from .patient_state import digest

DATA = Path(__file__).parent / 'data'
SAMPLE_PATH = DATA / 'eligibility_validation_sample_v1.json'
PLAN_SHA256 = '2061c0a0a9a4ee94fd9331a47d6ca5692d23ef3cffac3081ebfacf63eb4c0b8c'
SAMPLE_SHA256 = 'b49e505c3d9004de5047e3fc56920bc012df606d24517e8fbbae79db39f8b93d'
GUIDE_SHA256 = '3818133ea58d172bad0369fbe4b33f08018e169e7f86182eabe313b888f29a45'
SCHEMA_VERSION = 'eligibility-annotations-v1'
STATUSES = ('stated', 'multiple', 'not_stated', 'unclear')
COMPARATORS = ('>=', '>', '<=', '<')
SECTIONS = ('inclusion', 'exclusion')
MAX_VALUES = 3
TYPES = {
    'kidney_function_min': {'label': 'Kidney function, minimum (CrCl or eGFR)', 'units': ('mL/min', 'mL/min/1.73 m2', 'other'),
                            'equations': ('cockcroft_gault', 'mdrd', 'ckd_epi', 'measured', 'not_stated')},
    'creatinine_max': {'label': 'Serum creatinine, maximum', 'units': ('mg/dL', 'umol/L', 'x ULN', 'other')},
    'anc_min': {'label': 'Absolute neutrophil count, minimum', 'units': ('x 10^9/L', '/mm3 (= /uL)', 'cells/uL', 'other')},
    'platelets_min': {'label': 'Platelet count, minimum', 'units': ('x 10^9/L', '/mm3 (= /uL)', 'other')},
    'hemoglobin_min': {'label': 'Haemoglobin, minimum', 'units': ('g/dL', 'g/L', 'mmol/L', 'other')},
    'bilirubin_max': {'label': 'Total bilirubin, maximum', 'units': ('x ULN', 'mg/dL', 'umol/L', 'other')},
    'ast_alt_max': {'label': 'AST/ALT, maximum', 'units': ('x ULN', 'U/L', 'other')},
    'ecog_max': {'label': 'ECOG performance status, maximum', 'units': ('score',)},
}
NUMBER = re.compile(r'^\d+(\.\d+)?$')


def load_sample(path=SAMPLE_PATH):
    import hashlib
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SAMPLE_SHA256:
        raise ValueError('Validation sample is missing or changed.')
    return json.loads(raw)


def sample_trials():
    """Annotation order and the criteria text of each sample trial (nothing else is shown to the annotator)."""
    sample = load_sample()
    texts = {t['nct_id']: t['eligibility']['criteria_text'] for t in load_corpus()['trials']}
    return [{'nct_id': n, 'criteria_text': texts[n]} for n in sample['annotation_order']]


def _normal(text):
    text = unicodedata.normalize('NFKC', text or '').casefold()
    return ' '.join(text.replace('*', ' ').split())


def parse_form(form, criteria_text):
    """Turn submitted fields into one annotation; raise ValueError with every problem found."""
    errors, result = [], {}
    haystack = _normal(criteria_text)
    for key, spec in TYPES.items():
        status = form.get(f'{key}__status', '')
        if status not in STATUSES:
            errors.append(f"{spec['label']}: choose a status.")
            continue
        entry = {'status': status, 'note': (form.get(f'{key}__note') or '').strip()[:500], 'values': []}
        for i in range(1, MAX_VALUES + 1):
            raw = {f: (form.get(f'{key}__v{i}__{f}') or '').strip() for f in ('comparator', 'value', 'unit', 'section', 'sentence', 'qualifier')}
            if not any(raw[f] for f in ('value', 'sentence')):
                continue
            where = f"{spec['label']}, value {i}"
            if raw['comparator'] not in COMPARATORS:
                errors.append(f'{where}: choose a comparator.')
            if not NUMBER.match(raw['value'].replace(',', '')):
                errors.append(f'{where}: the value must be a number as written (for example 30, 1.5 or 75000).')
            if raw['unit'] not in spec['units']:
                errors.append(f'{where}: choose a unit.')
            if raw['section'] not in SECTIONS:
                errors.append(f'{where}: choose inclusion or exclusion.')
            if not raw['sentence']:
                errors.append(f'{where}: copy the sentence it comes from.')
            elif _normal(raw['sentence']) not in haystack:
                errors.append(f'{where}: the sentence was not found in the criteria text; copy it exactly.')
            entry['values'].append({**raw, 'value': raw['value'].replace(',', ''), 'qualifier': raw['qualifier'][:300]})
        if 'equations' in spec and entry['values']:
            equation = form.get(f'{key}__equation', '')
            if equation not in spec['equations']:
                errors.append(f"{spec['label']}: choose the estimating method (or not stated).")
            entry['equation'] = equation
        need = {'stated': (1, 1), 'multiple': (2, MAX_VALUES), 'not_stated': (0, 0), 'unclear': (0, MAX_VALUES)}[status]
        if not need[0] <= len(entry['values']) <= need[1]:
            errors.append(f"{spec['label']}: '{status}' needs " +
                          {'stated': 'exactly one value.', 'multiple': 'two or three values.', 'not_stated': 'no values.',
                           'unclear': 'at most three values.'}[status])
        if status == 'unclear' and not entry['note']:
            errors.append(f"{spec['label']}: say briefly why it is unclear.")
        result[key] = entry
    if errors:
        raise ValueError(errors)
    return result


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def empty_store():
    return {'schema_version': SCHEMA_VERSION, 'plan_sha256': PLAN_SHA256, 'sample_sha256': SAMPLE_SHA256,
            'guide_sha256': GUIDE_SHA256, 'annotations': {}, 'corrections': []}


def load_store(path):
    path = Path(path)
    if not path.exists():
        return empty_store()
    store = json.loads(path.read_text(encoding='utf-8'))
    if (store.get('schema_version'), store.get('plan_sha256'), store.get('sample_sha256'), store.get('guide_sha256')) != \
            (SCHEMA_VERSION, PLAN_SHA256, SAMPLE_SHA256, GUIDE_SHA256):
        raise ValueError('The annotation file belongs to a different plan, sample or guide.')
    return store


def save_annotation(path, nct_id, annotation, reason=None):
    """Write one trial's annotation atomically; a re-save needs a reason and keeps the earlier version."""
    path = Path(path)
    store = load_store(path)
    previous = store['annotations'].get(nct_id)
    if previous is not None:
        if not (reason or '').strip():
            raise ValueError(['This trial is already saved. Give a reason to correct it.'])
        store['corrections'].append({'nct_id': nct_id, 'corrected_at_utc': _now(), 'reason': reason.strip()[:300], 'previous': previous})
    store['annotations'][nct_id] = {'criteria': annotation, 'saved_at_utc': _now()}
    _write(path, store)
    return store


def mark_reviewed(path, nct_id):
    """Record that the annotator re-read a saved trial before export (the self-review pass)."""
    path = Path(path)
    store = load_store(path)
    if nct_id not in store['annotations']:
        raise ValueError(['Save this trial before marking it reviewed.'])
    store.setdefault('reviews', {})[nct_id] = {'reviewed_at_utc': _now(), 'of_version_saved_at_utc': store['annotations'][nct_id]['saved_at_utc']}
    _write(path, store)
    return store


def review_is_current(store, nct_id):
    review = store.get('reviews', {}).get(nct_id)
    saved = store['annotations'].get(nct_id)
    return bool(review and saved and review['of_version_saved_at_utc'] == saved['saved_at_utc'])


def _write(path, store):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.annotations-', suffix='.json')
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        json.dump(store, handle, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def export(path):
    store = load_store(path)
    order = load_sample()['annotation_order']
    missing = [n for n in order if n not in store['annotations']]
    if missing:
        raise ValueError(f'{len(missing)} of {len(order)} trials are not annotated yet (next: {missing[0]}).')
    payload = dict(store, annotated=len(order), exported_at_utc=_now())
    payload['annotations_sha256'] = digest(payload)
    return payload


def register_eligibility_annotation_commands(app):
    @app.cli.command('eligibility-annotations-export')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path), required=True)
    def command(output):
        """Export the finished reference annotation (Phase 4.1e) for pinning."""
        path = Path(app.config.get('ELIGIBILITY_ANNOTATIONS_PATH') or Path(app.instance_path) / 'eligibility_annotations_v1.json')
        try:
            payload = export(path)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        with output.open('x', encoding='utf-8') as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=1) + '\n')
        click.echo(f"Exported {payload['annotated']} annotated trials to {output}\nSHA256 of content: {payload['annotations_sha256']}")
