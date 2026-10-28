"""Phase 4.2a: reference annotation of the v2 validation sample (rules in ELIGIBILITY_ANNOTATION_GUIDE_V2.md).

Differences from v1 (eligibility_annotations.py), from the v1 post-hoc analysis:
- the annotator records the comparator as written and whether the sentence describes eligible or excluded patients;
  the eligible-side comparator ('comparator', the field the scoring and review use) is derived here;
- thresholds may be in either direction for every type;
- platelets and ANC accept 'x 10^3/uL (K/uL)'.
Storage, corrections, self-review marks and export work as in v1, in a separate file (eligibility_annotations_v2.json).
"""
import hashlib
import json
from pathlib import Path

import click

from . import eligibility_annotations as v1
from .eligibility_corpus import load_corpus
from .patient_state import digest

DATA = Path(__file__).parent / 'data'
SAMPLE_PATH = DATA / 'eligibility_validation_sample_v2.json'
PLAN_SHA256 = '8a543d7df767afd3ec729a6c5c61d22dd9324392dccac59412cac4ee9e8643a8'
SAMPLE_SHA256 = '5b7b4718957f03cd3cffd99886f39add228135517b0dbcac474899edf996c20f'
GUIDE_SHA256 = '96fdfefe45ba54933d07a2befe728b21ad40b4f9227183e48dfc4ca4c3987b8f'
SCHEMA_VERSION = 'eligibility-annotations-v2'
STORE_NAME = 'eligibility_annotations_v2.json'
STATUSES, COMPARATORS, SECTIONS, MAX_VALUES = v1.STATUSES, v1.COMPARATORS, v1.SECTIONS, v1.MAX_VALUES
DESCRIBES = ('eligible', 'excluded')
FLIP = {'>=': '<', '>': '<=', '<=': '>', '<': '>='}
K_UL = 'x 10^3/uL (K/uL)'
TYPES = {
    'kidney_function_min': dict(v1.TYPES['kidney_function_min'], label='Kidney function threshold (CrCl or eGFR)'),
    'creatinine_max': dict(v1.TYPES['creatinine_max'], label='Serum creatinine threshold'),
    'anc_min': dict(v1.TYPES['anc_min'], label='Absolute neutrophil count threshold',
                    units=('x 10^9/L', '/mm3 (= /uL)', 'cells/uL', K_UL, 'other')),
    'platelets_min': dict(v1.TYPES['platelets_min'], label='Platelet count threshold', units=('x 10^9/L', '/mm3 (= /uL)', K_UL, 'other')),
    'hemoglobin_min': dict(v1.TYPES['hemoglobin_min'], label='Haemoglobin threshold'),
    'bilirubin_max': dict(v1.TYPES['bilirubin_max'], label='Total bilirubin threshold'),
    'ast_alt_max': dict(v1.TYPES['ast_alt_max'], label='AST/ALT threshold'),
    'ecog_max': dict(v1.TYPES['ecog_max'], label='ECOG performance status threshold (incl. WHO, Zubrod, SWOG)'),
}


def load_sample(path=SAMPLE_PATH):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SAMPLE_SHA256:
        raise ValueError('Validation sample v2 is missing or changed.')
    return json.loads(raw)


def sample_trials():
    sample = load_sample()
    texts = {t['nct_id']: t['eligibility']['criteria_text'] for t in load_corpus()['trials']}
    return [{'nct_id': n, 'criteria_text': texts[n]} for n in sample['annotation_order']]


def eligible_comparator(as_written, describes):
    return as_written if describes == 'eligible' else FLIP[as_written]


def parse_form(form, criteria_text):
    """Turn submitted fields into one annotation; raise ValueError with every problem found."""
    errors, result = [], {}
    haystack = v1._normal(criteria_text)
    for key, spec in TYPES.items():
        status = form.get(f'{key}__status', '')
        if status not in STATUSES:
            errors.append(f"{spec['label']}: choose a status.")
            continue
        entry = {'status': status, 'note': (form.get(f'{key}__note') or '').strip()[:500], 'values': []}
        for i in range(1, MAX_VALUES + 1):
            raw = {f: (form.get(f'{key}__v{i}__{f}') or '').strip()
                   for f in ('comparator_as_written', 'value', 'unit', 'section', 'describes', 'sentence', 'qualifier')}
            if not any(raw[f] for f in ('value', 'sentence')):
                continue
            where = f"{spec['label']}, value {i}"
            if raw['comparator_as_written'] not in COMPARATORS:
                errors.append(f'{where}: choose the comparator as written.')
            if not v1.NUMBER.match(raw['value'].replace(',', '')):
                errors.append(f'{where}: the value must be a number as written (for example 30, 1.5 or 75000).')
            if raw['unit'] not in spec['units']:
                errors.append(f'{where}: choose a unit.')
            if raw['section'] not in SECTIONS:
                errors.append(f'{where}: choose inclusion or exclusion.')
            describes = raw['describes'] or ('eligible' if raw['section'] == 'inclusion' else 'excluded' if raw['section'] == 'exclusion' else '')
            if describes not in DESCRIBES:
                errors.append(f'{where}: say whether the sentence describes eligible or excluded patients.')
            if not raw['sentence']:
                errors.append(f'{where}: copy the sentence it comes from.')
            elif v1._normal(raw['sentence']) not in haystack:
                errors.append(f'{where}: the sentence was not found in the criteria text; copy it exactly.')
            value = {'comparator_as_written': raw['comparator_as_written'], 'describes': describes,
                     'describes_from_section': not raw['describes'],
                     'comparator': eligible_comparator(raw['comparator_as_written'], describes)
                     if raw['comparator_as_written'] in COMPARATORS and describes in DESCRIBES else '',
                     'value': raw['value'].replace(',', ''), 'unit': raw['unit'], 'section': raw['section'],
                     'sentence': raw['sentence'], 'qualifier': raw['qualifier'][:300]}
            entry['values'].append(value)
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
    path = Path(path)
    store = load_store(path)
    previous = store['annotations'].get(nct_id)
    if previous is not None:
        if not (reason or '').strip():
            raise ValueError(['This trial is already saved. Give a reason to correct it.'])
        store['corrections'].append({'nct_id': nct_id, 'corrected_at_utc': v1._now(), 'reason': reason.strip()[:300], 'previous': previous})
    store['annotations'][nct_id] = {'criteria': annotation, 'saved_at_utc': v1._now()}
    v1._write(path, store)
    return store


def mark_reviewed(path, nct_id):
    path = Path(path)
    store = load_store(path)
    if nct_id not in store['annotations']:
        raise ValueError(['Save this trial before marking it reviewed.'])
    store.setdefault('reviews', {})[nct_id] = {'reviewed_at_utc': v1._now(), 'of_version_saved_at_utc': store['annotations'][nct_id]['saved_at_utc']}
    v1._write(path, store)
    return store


review_is_current = v1.review_is_current


def export(path):
    store = load_store(path)
    order = load_sample()['annotation_order']
    missing = [n for n in order if n not in store['annotations']]
    if missing:
        raise ValueError(f'{len(missing)} of {len(order)} trials are not annotated yet (next: {missing[0]}).')
    unreviewed = [n for n in order if not review_is_current(store, n)]
    payload = dict(store, annotated=len(order), reviewed=len(order) - len(unreviewed), exported_at_utc=v1._now())
    payload['annotations_sha256'] = digest(payload)
    return payload


def store_path(app):
    return Path(app.config.get('ELIGIBILITY_ANNOTATIONS_V2_PATH') or Path(app.instance_path) / STORE_NAME)


def register_eligibility_annotation_v2_commands(app):
    @app.cli.command('eligibility-annotations-v2-export')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path), required=True)
    def command(output):
        """Export the finished v2 reference annotation (Phase 4.2) for pinning."""
        try:
            payload = export(store_path(app))
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        with output.open('x', encoding='utf-8') as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=1) + '\n')
        click.echo(f"Exported {payload['annotated']} annotated trials ({payload['reviewed']} reviewed) to {output}\n"
                   f"SHA256 of content: {payload['annotations_sha256']}")
