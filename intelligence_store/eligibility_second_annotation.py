"""Independent second annotation of a random sample of the eligibility v2 trials (plan eligibility_second_annotation_plan_v1.json).

A second annotator ("annotator B") reads a seeded random sample of the 200 v2 trials under annotation guide v2, in a
standalone page that holds only the guide, the criteria texts and the form: never the owner's labels, either
extractor's output, or which pairs were errors. The sample is drawn from the annotation order alone, with no use of any
result. B's record is validated by the annotation tool's own rules (eligibility_annotations_v2.parse_form).

`agreement` produces the plan's analysis: B against the owner's pinned annotation (exact, detection and kappa, per type
and overall), and, descriptively, both extractors scored against each reference on the same trials. Adjudication comes
only after both sets are locked and is not part of this module.
"""
import hashlib
import html
import json
import math
import random
import re
from pathlib import Path

from . import eligibility_annotations_v2 as ann2
from . import eligibility_shared_errors as se
from . import eligibility_validation_llm as val
from . import eligibility_validation_v2 as v2
from . import eligibility_extractor_llm as llm
from .patient_state import digest

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'eligibility_second_annotation_plan_v1.json'
PLAN_SHA256 = '2642765af8c98b17e1193d5a89cfaa9f662023419b8d657ff312053035698048'
GUIDE_PATH = ROOT / 'docs' / 'ELIGIBILITY_ANNOTATION_GUIDE_V2.md'
RECORD_SCHEMA = 'eligibility-second-annotation-record-v1'


def load_plan(path=PLAN_PATH):
    raw = Path(path).read_bytes()
    if PLAN_SHA256 is not None and hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError('The second-annotation plan is missing or changed.')
    return json.loads(raw)


def sample(plan=None):
    """(study trials in presentation order, practice trials). Uses only the annotation order and the plan's seeds."""
    plan = plan or load_plan()
    order = v2.load_sample()['annotation_order']
    s = plan['sample']
    chosen = random.Random(s['seed']).sample(order, s['size'])
    random.Random(plan['presentation_order_seed']).shuffle(chosen)
    v1_sample = json.loads((DATA / 'eligibility_validation_sample_v1.json').read_text())['annotation_order']
    p = plan['practice']
    pool = [n for n in v1_sample if n not in set(order)]
    practice = random.Random(p['seed']).sample(pool, p['size'])
    return chosen, practice


def _md(text):
    """A small Markdown subset (headings, two-level lists, tables, paragraphs, bold, code) for the guide in the standalone page."""
    def inline(t):
        t = html.escape(t)
        t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
        return re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
    out, para, table, items = [], [], [], []   # items: [kind, text, [(kind, text), ...]]

    def flush():
        nonlocal para, table, items
        if para:
            out.append('<p>' + inline(' '.join(para)) + '</p>'); para = []
        if items:
            html_items, kind = [], items[0][0]
            for _, t, subs in items:
                sub = ''
                if subs:
                    sk = subs[0][0]
                    sub = f'<{sk}>' + ''.join(f'<li>{inline(x)}</li>' for _, x in subs) + f'</{sk}>'
                html_items.append(f'<li>{inline(t)}{sub}</li>')
            out.append(f'<{kind}>' + ''.join(html_items) + f'</{kind}>'); items = []
        if table:
            rows = [r for r in table if not re.match(r'^\|[\s|:-]+\|$', r)]
            cells = [[c.strip() for c in r.strip('|').split('|')] for r in rows]
            out.append('<table><thead><tr>' + ''.join(f'<th>{inline(c)}</th>' for c in cells[0]) + '</tr></thead><tbody>' +
                       ''.join('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>' for r in cells[1:]) + '</tbody></table>')
            table = []
    for line in text.splitlines():
        s = line.strip()
        indent = len(line) - len(line.lstrip(' '))
        m = re.match(r'^(#{1,4})\s+(.*)', s)
        li = re.match(r'^([-*]|\d+\.)\s+(.*)', s)
        if not s:
            if para or table:
                flush()
        elif m:
            flush(); k = len(m.group(1)) + 1; out.append(f'<h{k}>{inline(m.group(2))}</h{k}>')
        elif s.startswith('|'):
            if para or items:
                flush()
            table.append(s)
        elif li:
            kind = 'ol' if s[0].isdigit() else 'ul'
            if para or table:
                flush()
            if indent >= 2 and items:
                items[-1][2].append((kind, li.group(2)))
            else:
                if items and items[0][0] != kind:
                    flush()
                items.append([kind, li.group(2), []])
        elif items and indent >= 2:
            if items[-1][2]:
                k, t = items[-1][2][-1]; items[-1][2][-1] = (k, t + ' ' + s)
            else:
                items[-1][1] += ' ' + s
        else:
            flush()
            para.append(s)
    flush()
    return '\n'.join(out)


def page_payload(plan=None):
    """Everything the standalone page holds. Contains no label, extractor output or error selection."""
    plan = plan or load_plan()
    study, practice = sample(plan)
    texts = dict(llm.criteria_texts(study))
    v1_texts = {t['nct_id']: t['eligibility']['criteria_text'] for t in llm.load_corpus()['trials'] if t['nct_id'] in set(practice)}
    types = [{'key': k, 'label': s['label'], 'units': list(s['units']), 'equations': list(s.get('equations', ())),
              'short': se.LABELS[k]} for k, s in ann2.TYPES.items()]
    p = {'plan_version': plan['plan_version'], 'plan_sha256': PLAN_SHA256, 'guide_sha256': hashlib.sha256(GUIDE_PATH.read_bytes()).hexdigest(),
         'types': types, 'statuses': list(ann2.STATUSES), 'comparators': list(ann2.COMPARATORS), 'sections': list(ann2.SECTIONS),
         'describes': list(ann2.DESCRIBES), 'max_values': ann2.MAX_VALUES,
         'practice': [{'nct_id': n, 'criteria_text': v1_texts[n]} for n in practice],
         'trials': [{'position': k, 'nct_id': n, 'criteria_text': texts[n]} for k, n in enumerate(study, 1)]}
    p['page_sha256'] = digest(p)
    return p


def write_page(path):
    """Writes the standalone page (one HTML file, no server needed). Returns its page_sha256."""
    import jinja2
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(ROOT / 'app' / 'templates')), autoescape=True)
    p = page_payload()
    page = env.get_template('eligibility_second_annotation_standalone.html').render(p=p, guide_html=_md(GUIDE_PATH.read_text(encoding='utf-8')))
    Path(path).write_text(page, encoding='utf-8')
    return p['page_sha256']


def validate_record(record, p=None):
    """A returned record -> (problems, parsed annotations by NCT ID). Every study trial must be complete and valid."""
    p = p or page_payload()
    problems, parsed = [], {}
    if record.get('schema_version') != RECORD_SCHEMA:
        problems.append('Unknown record format.')
    if record.get('page_sha256') != p['page_sha256']:
        problems.append('The record was made from a different page (page checksum differs).')
    if not record.get('locked_at'):
        problems.append('The record was not locked.')
    texts = {t['nct_id']: t['criteria_text'] for t in p['trials']}
    got = record.get('annotations', {})
    for n in texts:
        if n not in got:
            problems.append(f'{n}: missing')
            continue
        try:
            parsed[n] = ann2.parse_form({k: str(v) for k, v in got[n].items()}, texts[n])
        except ValueError as exc:
            problems.extend(f'{n}: {e}' for e in (exc.args[0] if isinstance(exc.args[0], list) else [str(exc)]))
    for n in got:
        if n not in texts:
            problems.append(f'{n}: not in the sample')
    return problems, parsed


def _wilson(k, n, z=1.959963984540054):
    if n == 0:
        return None
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def _detect(entry):
    return {'stated': 'threshold', 'multiple': 'threshold'}.get(entry['status'], entry['status'])


def _kappa(pairs):
    n = len(pairs)
    if n == 0:
        return None
    cats = sorted({c for p in pairs for c in p})
    po = sum(1 for a, b in pairs if a == b) / n
    pe = sum((sum(1 for a, _ in pairs if a == c) / n) * (sum(1 for _, b in pairs if b == c) / n) for c in cats)
    return None if pe == 1 else round((po - pe) / (1 - pe), 4)


def _same(a, b):
    from .eligibility_reference_review import _same as same
    return same(None, a, b)


def agreement(record, p=None):
    """The plan's analysis. Raises if the record is invalid."""
    p = p or page_payload()
    problems, b = validate_record(record, p)
    if problems:
        raise ValueError(problems)
    plan = load_plan()
    a_all = v2.load_annotations()['annotations']
    trials = [t['nct_id'] for t in p['trials']]
    per_type, all_exact, all_detect = {}, {}, []
    for t in v2.TYPES:
        exact = [_same(a_all[n]['criteria'][t], b[n][t]) for n in trials]
        det = [(_detect(a_all[n]['criteria'][t]), _detect(b[n][t])) for n in trials]
        both = [n for n in trials if _detect(a_all[n]['criteria'][t]) == 'threshold' == _detect(b[n][t])]
        row = {'trials': len(trials), 'exact_agreement': sum(exact), 'exact_rate': round(sum(exact) / len(trials), 4),
               'exact_wilson_95': _wilson(sum(exact), len(trials)),
               'detection_agreement': sum(1 for x, y in det if x == y), 'detection_kappa': _kappa(det),
               'both_threshold': len(both), 'values_agree_when_both_threshold': sum(1 for n in both if _same(a_all[n]['criteria'][t], b[n][t]))}
        if t == 'kidney_function_min':
            row['equation_agree_when_both_threshold'] = sum(1 for n in both if a_all[n]['criteria'][t].get('equation') == b[n][t].get('equation'))
        per_type[t] = row
        for n, e in zip(trials, exact):
            all_exact.setdefault(n, []).append(e)
        all_detect += det
    total = sum(len(v) for v in all_exact.values())
    hits = sum(sum(v) for v in all_exact.values())
    rng = random.Random(plan['analysis']['bootstrap_seed'])
    boots = []
    for _ in range(plan['analysis']['bootstrap_resamples']):
        draw = [all_exact[rng.choice(trials)] for _ in trials]
        boots.append(sum(sum(v) for v in draw) / sum(len(v) for v in draw))
    boots.sort()
    lo, hi = boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots)) - 1]
    overall = {'pairs': total, 'exact_agreement': hits, 'exact_rate': round(hits / total, 4),
               'exact_trial_bootstrap_95': [round(lo, 4), round(hi, 4)], 'detection_kappa': _kappa(all_detect)}
    bar = plan['analysis']['reliability_bar']
    reading = ('adequate' if lo >= bar else 'not_adequate')

    b_ref = {n: {'criteria': b[n]} for n in trials}
    a_ref = {n: a_all[n] for n in trials}
    texts = {t['nct_id']: t['criteria_text'] for t in p['trials']}
    rule = {n: v2.ex.extract(texts[n]) for n in trials}
    model_all = se._llm_run_1(v2.load_sample()['annotation_order'])
    model = {n: model_all[n] for n in trials}
    extractors = {ref_name: {'v1_1': v2.summarise(val.score_run(ref, trials, rule)),
                             'llm_run_1': v2.summarise(val.score_run(ref, trials, model))}
                  for ref_name, ref in (('owner_annotation', a_ref), ('annotator_b', b_ref))}
    disagreements = [{'nct_id': n, 'type': t} for n in trials for t in v2.TYPES if not _same(a_all[n]['criteria'][t], b[n][t])]
    report = {'schema_version': 'eligibility-second-annotation-report-v1', 'plan_version': plan['plan_version'], 'plan_sha256': PLAN_SHA256,
              'page_sha256': p['page_sha256'], 'annotator': record.get('annotator', {}),
              'per_type': per_type, 'overall': overall,
              'reliability_reading': {'bar': bar, 'statistic': 'lower bound of the trial-bootstrap 95% interval of overall exact agreement',
                                      'value': round(lo, 4), 'reading': reading},
              'extractors_on_sample_descriptive': extractors,
              'disagreements_for_adjudication': disagreements,
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report
