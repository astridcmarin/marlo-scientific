"""Blind re-reading of the eligibility v2 reference (plan eligibility_reference_review_plan_v1.json, 13 November 2026).

After both blind checks failed, the 166 trial-and-type pairs both extractors got wrong are re-read by the owner, mixed
with a seeded control sample of pairs both extractors got right, in a seeded order. For each item the owner first
records a reading of the criteria text without seeing the original annotation or either extractor's answer, under the
annotation guide v2 rules (validated by eligibility_annotations_v2.parse_form); only then are the original annotation
and the two answers revealed, and the owner decides: the annotation stands, it needs correcting (the locked reading
becomes the corrected annotation), or the trial is unclear.

The original blind results stay primary and unchanged. `sensitivity` produces the post hoc corrected-reference
sensitivity analysis the plan fixes: the same frozen outputs, scorer and pass rule, both extractors, side by side.
"""
import hashlib
import json
import random
from pathlib import Path

from . import eligibility_annotations_v2 as ann2
from . import eligibility_shared_errors as se
from . import eligibility_validation_llm as val
from . import eligibility_validation_v2 as v2
from . import eligibility_extractor_llm as llm
from .patient_state import digest

DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'eligibility_reference_review_plan_v1.json'
PLAN_SHA256 = 'df4bdbed36269b9e6bc418494bd41ba56cbaf49fb698b604dc79ede1663f4206'
DEVIATIONS_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'development' / 'eligibility_reference_review_deviations_v1.json'
DEVIATIONS_SHA256 = '2acf033e004ba2c7af5ed40ed0330c82c6dd7aa498bcb8dc240f110b5c0756a6'
DECISIONS = ('annotation_stands', 'annotation_needs_correcting', 'trial_unclear')
OK = ('tp', 'tn')


def load_plan(path=PLAN_PATH):
    raw = Path(path).read_bytes()
    if PLAN_SHA256 is not None and hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError('The reference review plan is missing or changed.')
    return json.loads(raw)


def _inputs():
    annotations = v2.load_annotations()['annotations']
    order = v2.load_sample()['annotation_order']
    texts = dict(llm.criteria_texts(order))
    model = se._llm_run_1(order)
    rule = {n: v2.ex.extract(texts[n]) for n in order}
    return annotations, order, texts, model, rule


def items(plan=None):
    """Shared-error pairs plus the seeded control sample, in the seeded presentation order."""
    plan = plan or load_plan()
    annotations, order, texts, model, rule = _inputs()
    shared, controls_pool = [], []
    for n in order:
        for t in v2.TYPES:
            a = annotations[n]['criteria'][t]
            r, m = v2.score_pair(t, a, rule[n][t])['outcome'], v2.score_pair(t, a, model[n][t])['outcome']
            if 'excluded_unclear' in (r, m):
                continue
            if r not in OK and m not in OK:
                shared.append((n, t))
            elif r in OK and m in OK:
                controls_pool.append((n, t))
    c = plan['controls']
    controls = random.Random(c['seed']).sample(controls_pool, c['size'])
    chosen = [(n, t, 'shared') for n, t in shared] + [(n, t, 'control') for n, t in controls]
    random.Random(plan['presentation_order_seed']).shuffle(chosen)
    out = []
    for k, (n, t, group) in enumerate(chosen, 1):
        out.append({'id': f'{n}:{t}', 'position': k, 'nct_id': n, 'type': t, 'group': group, 'type_label': se.LABELS[t],
                    'units': list(ann2.TYPES[t]['units']), 'equations': list(ann2.TYPES[t].get('equations', ())),
                    'relevant_lines': se._lines(texts[n], t), 'criteria_text': texts[n],
                    'reveal': {'annotated': annotations[n]['criteria'][t],
                               'v1_1': {'values': rule[n][t]['values']}, 'llm_run_1': {'values': model[n][t]['values'],
                                                                                       'status': model[n][t].get('status')}}})
    return out, {'shared': len(shared), 'controls': len(controls), 'controls_pool': len(controls_pool)}


def view():
    plan = load_plan()
    its, counts = items(plan)
    v = {'plan_version': plan['plan_version'], 'plan_sha256': PLAN_SHA256, 'counts': counts, 'total': len(its), 'items': its,
         'statuses': list(ann2.STATUSES), 'comparators': list(ann2.COMPARATORS), 'sections': list(ann2.SECTIONS)}
    v['view_sha256'] = digest({k: v[k] for k in ('plan_version', 'plan_sha256', 'counts', 'items')})
    return v


def client_view(v=None):
    """What the page receives: items without their group (shared or control stays hidden), reveals kept apart."""
    v = v or view()
    keep = ('id', 'position', 'nct_id', 'type', 'type_label', 'units', 'equations', 'relevant_lines', 'criteria_text')
    return {'plan_version': v['plan_version'], 'view_sha256': v['view_sha256'], 'total': v['total'],
            'statuses': v['statuses'], 'comparators': v['comparators'], 'sections': v['sections'],
            'describes': list(ann2.DESCRIBES), 'max_values': ann2.MAX_VALUES, 'decisions': list(DECISIONS),
            'items': [{k: i[k] for k in keep} for i in v['items']],
            'reveals': {i['id']: i['reveal'] for i in v['items']}}


def check_reading(v, item_id, reading):
    """Before a reading is locked: the problems the annotation tool's rules find in it (empty if valid)."""
    it = next((i for i in v['items'] if i['id'] == item_id), None)
    if it is None:
        return ['Not in the list.']
    try:
        parse_reading(it['type'], reading, it['criteria_text'])
    except ValueError as exc:
        return exc.args[0] if isinstance(exc.args[0], list) else [str(exc)]
    return []


def parse_reading(ctype, reading, criteria_text):
    """A recorded reading (form-style fields for one type) -> the annotation entry, by the annotation tool's own rules."""
    form = {f'{t}__status': 'not_stated' for t in ann2.TYPES}
    form.update({k: str(v) for k, v in reading.items()})
    form[f'{ctype}__status'] = reading.get(f'{ctype}__status', '')
    return ann2.parse_form(form, criteria_text)[ctype]


def validate_record(record, v=None):
    """A downloaded review record -> (problems, parsed readings by id)."""
    v = v or view()
    by_id = {i['id']: i for i in v['items']}
    problems, parsed = [], {}
    if record.get('view_sha256') != v['view_sha256']:
        problems.append('The record was made from a different list (view checksum differs).')
    for k, d in record.get('items', {}).items():
        it = by_id.get(k)
        if it is None:
            problems.append(f'{k}: not in the list')
            continue
        if not d.get('locked_at'):
            problems.append(f'{k}: no locked reading')
            continue
        try:
            parsed[k] = parse_reading(it['type'], d.get('reading', {}), it['criteria_text'])
        except ValueError as exc:
            problems.append(f'{k}: reading invalid: ' + '; '.join(exc.args[0] if isinstance(exc.args[0], list) else [str(exc)]))
        if d.get('decision') is not None:
            if d['decision'] not in DECISIONS:
                problems.append(f'{k}: unknown decision')
            elif not d.get('decided_at') or d['decided_at'] < d['locked_at']:
                problems.append(f'{k}: decided before the reading was locked')
            elif d['decision'] in ('annotation_needs_correcting', 'trial_unclear') and not (d.get('note') or '').strip():
                problems.append(f'{k}: this decision needs a note')
    return problems, parsed


def _same(ctype, a, b):
    if a['status'] != b['status']:
        return False
    return sorted((x['comparator'], str(x['value']), x['unit']) for x in a['values']) == \
        sorted((x['comparator'], str(x['value']), x['unit']) for x in b['values'])


def unblinded_items():
    """Pairs seen with the answers before their blind reading (recorded deviation, 13 November 2026)."""
    raw = DEVIATIONS_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DEVIATIONS_SHA256:
        raise ValueError('The deviation record is missing or changed.')
    return tuple(json.loads(raw)['items_seen_unblinded'])


def report(record, v=None):
    """The result as the deviation record fixes it: the analysis with all decisions, and with the unblinded items' decisions set aside."""
    v = v or view()
    skip = set(unblinded_items())
    kept = json.loads(json.dumps(record))
    for k in skip & set(kept.get('items', {})):
        kept['items'][k]['decision'] = None
    out = {'deviation': {'file': 'docs/development/eligibility_reference_review_deviations_v1.json', 'sha256': DEVIATIONS_SHA256,
                         'items_seen_unblinded': sorted(skip)},
           'all_decisions': sensitivity(record, v, not_blind=skip),
           'without_unblinded_items': sensitivity(kept, v, not_blind=skip)}
    out['report_sha256'] = digest(out)
    return out


def sensitivity(record, v=None, not_blind=()):
    """The plan's post hoc corrected-reference sensitivity analysis. Raises if the record is invalid."""
    v = v or view()
    problems, parsed = validate_record(record, v)
    if problems:
        raise ValueError(problems)
    plan = load_plan()
    annotations, order, texts, model, rule = _inputs()
    by_id = {i['id']: i for i in v['items']}
    decided = {k: d for k, d in record['items'].items() if d.get('decision')}
    corrections, unclear = [], []
    corrected_a = json.loads(json.dumps(annotations))
    corrected_b = json.loads(json.dumps(annotations))
    for k, d in sorted(decided.items()):
        n, t = k.split(':', 1)
        if d['decision'] == 'annotation_needs_correcting':
            corrections.append({'id': k, 'group': by_id[k]['group'], 'from': annotations[n]['criteria'][t], 'to': parsed[k], 'note': d['note']})
            corrected_a[n]['criteria'][t] = parsed[k]
            corrected_b[n]['criteria'][t] = parsed[k]
        elif d['decision'] == 'trial_unclear':
            unclear.append({'id': k, 'group': by_id[k]['group'], 'note': d['note']})
            corrected_b[n]['criteria'][t] = {'status': 'unclear', 'note': d['note'], 'values': []}

    def scores(ref):
        return {'v1_1': v2.summarise(val.score_run(ref, order, rule)), 'llm_run_1': v2.summarise(val.score_run(ref, order, model))}

    original = scores(annotations)
    analyses = {'original_primary': original,
                'corrected_unclear_kept': scores(corrected_a),
                'corrected_unclear_excluded': scores(corrected_b)}
    transitions = []
    for name in ('corrected_unclear_kept', 'corrected_unclear_excluded'):
        for ex in ('v1_1', 'llm_run_1'):
            for t in v2.TYPES:
                before, after = original[ex][t]['decision'], analyses[name][ex][t]['decision']
                if before != after:
                    transitions.append({'analysis': name, 'extractor': ex, 'type': t, 'from': before, 'to': after})
    reproducibility = {}
    for g in ('shared', 'control'):
        ids = [k for k in parsed if by_id[k]['group'] == g and k not in not_blind]
        same = sum(1 for k in ids if _same(by_id[k]['type'], parsed[k], annotations[k.split(':')[0]]['criteria'][by_id[k]['type']]))
        reproducibility[g] = {'blind_reading_equals_original': same, 'of': len(ids)}
    rate = {g: {'corrections': sum(1 for c in corrections if c['group'] == g), 'unclear': sum(1 for u in unclear if u['group'] == g),
                'decided': sum(1 for k in decided if by_id[k]['group'] == g)} for g in ('shared', 'control')}
    report = {'schema_version': 'eligibility-reference-review-report-v1', 'plan_version': plan['plan_version'], 'plan_sha256': PLAN_SHA256,
              'view_sha256': v['view_sha256'], 'label': plan['reporting']['label'], 'items_listed': v['total'],
              'readings_locked': len(parsed), 'decisions': len(decided),
              'blind_reading_reproducibility': reproducibility, 'correction_rates': rate,
              'corrections': corrections, 'unclear': unclear, 'analyses': analyses, 'pass_fail_transitions': transitions,
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report
