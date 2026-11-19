"""Independent second annotation of a random sample of the eligibility v2 trials (plan eligibility_second_annotation_plan_v1.json).

Module version 1.1 (16 November 2026): `agreement` takes an optional reader-A record and an optional pair subset;
with both unset its report is byte-identical to version 1, which a regression test pins. The page now carries whichever
annotation guide its plan pins.

A second annotator ("annotator B") reads a seeded random sample of the 200 v2 trials under the plan's annotation guide, in a
standalone page that holds only the guide, the criteria texts and the form: never the owner's labels, either
extractor's output, or which pairs were errors. The sample is drawn from the annotation order alone, with no use of any
result. B's record is validated by the annotation tool's own rules (eligibility_annotations_v2.parse_form).

`agreement` produces the plan's analysis: reader B against reader A (exact, detection and kappa, per type and overall),
where reader A is the owner's pinned annotation unless a reader-A record is given, and, descriptively, both extractors
scored against each reference on the same trials. Adjudication comes
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
# Every plan file this module may run, pinned by its loader as the repository convention requires. Plan v2.1 was
# reachable only by reading the file unpinned until 17 November 2026.
PLANS = {
    'eligibility-second-annotation-plan-v1.0': (PLAN_PATH, PLAN_SHA256),
    'eligibility-second-annotation-plan-v2.0': (DATA / 'eligibility_second_annotation_plan_v2.json',
                                                '15015076f61ab7d6093cf3b1ea4fe6fbc3b7b87bd0f8ffffca8cde7b19d49cf8'),
    'eligibility-second-annotation-plan-v2.1': (DATA / 'eligibility_second_annotation_plan_v2_1.json',
                                                '848a81b9750326a74128f8e0b979a0b5e2be15ff20a8cb496f014a0c1849a770'),
}
_PLAN_PINS = {str(path): sha for path, sha in PLANS.values()}
# Who a page is for. Round one had one reader and the page said so in five places, which is why round two's two
# pages both came out as annotator B's (found 17 November 2026).
READERS = {
    'owner': {'code': 'A', 'label': 'the owner', 'heading': 'the owner', 'slug': 'owner'},
    'annotator_b': {'code': 'B', 'label': 'annotator B', 'heading': 'second annotator', 'slug': 'annotator_b'},
}
GUIDE_PATH = ROOT / 'docs' / 'ELIGIBILITY_ANNOTATION_GUIDE_V2.md'


def guide_path(plan=None):
    """The guide the plan pins, so a later plan version carries its own guide into the page."""
    plan = plan or load_plan()
    named = (plan.get('inputs') or {}).get('guide', {}).get('file')
    return (ROOT / named) if named else GUIDE_PATH
RECORD_SCHEMA = 'eligibility-second-annotation-record-v1'
# Annotator B's locked record, pinned unchanged before any analysis, as plan v1 requires.
RECORD_PATH = DATA / 'eligibility_annotator_b_record_v1.json'
RECORD_SHA256 = '8a491e1a37158dfc25034687cba7b31665ad3b6acf47d4d7d9c49a19b0a8ddd0'


# Round two (plan v2.1): each reader's locked record, pinned unchanged before any analysis, as the plan requires.
ROUND_2_RECORDS = {
    'owner': (DATA / 'eligibility_round2_owner_record_v1.json',
              '0d94147c5b635b3e14af687c27f8b653938dc4b279e298d05d391d3a15cb05c9'),         # locked 18 November 2026
    'annotator_b': (DATA / 'eligibility_round2_annotator_b_record_v1.json',
                    'e4d6f34907a0b9942dc54c91800cfb55182d9565fa29f936d0d23e2032c57369'),   # locked 19 November 2026
}


def load_round_2_record(reader):
    """A round-two reader's pinned record. Refuses a changed file."""
    path, pinned = ROUND_2_RECORDS[reader]
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != pinned:
        raise ValueError(f"The round-two record of {reader_identity(reader)['label']} is missing or changed.")
    return json.loads(raw)


def load_record(path=RECORD_PATH):
    raw = Path(path).read_bytes()
    if RECORD_SHA256 is not None and hashlib.sha256(raw).hexdigest() != RECORD_SHA256:
        raise ValueError("Annotator B's record is missing or changed.")
    return json.loads(raw)


def load_plan(path=PLAN_PATH):
    raw = Path(path).read_bytes()
    pinned = _PLAN_PINS.get(str(Path(path)))
    if pinned is None:
        raise ValueError(f'{Path(path).name} is not a pinned second-annotation plan; add it to PLANS first.')
    if hashlib.sha256(raw).hexdigest() != pinned:
        raise ValueError('The second-annotation plan is missing or changed.')
    return json.loads(raw)


def plan_sha256(plan):
    """The checksum of the plan file in use.

    Not PLAN_SHA256, which is plan v1's and was written onto every page and every report whatever plan governed
    them: round two's pages declared plan v2.1 and carried v1's checksum (found 17 November 2026).
    """
    version = plan['plan_version']
    if version not in PLANS:
        raise ValueError(f'unknown plan version {version!r}; pin its file in PLANS first')
    path, pinned = PLANS[version]
    got = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if got != pinned:
        raise ValueError(f'The second-annotation plan {version} is missing or changed.')
    return got


def reader_identity(reader):
    """The identity a page carries. None is round one, which had annotator B alone."""
    if reader is None:
        return READERS['annotator_b']
    if reader not in READERS:
        raise ValueError(f'unknown reader {reader!r}; expected one of {", ".join(sorted(READERS))}')
    return READERS[reader]


def guide_label(plan=None):
    """How the page names the guide it carries, taken from the file the plan pins."""
    m = re.search(r'_V(\d+)\.md$', guide_path(plan).name)
    return f'version {m.group(1)}' if m else 'version 1'


def _pool(order, spec):
    """The trials a plan may draw from. Without a spec, all of them, which is what plan v1 does.

    A spec names exclusions by rule rather than by listing ids, so the pool is reproducible from pinned files:
    `exclude_round_one` drops the trials the first round used as study or practice, and `exclude_re_read` drops
    every trial appearing in the 14 November reference-review view. Round two uses both, so that annotator B has
    seen none of its trials and the owner has not seen them since the original annotation.
    """
    if not spec:
        return list(order)
    drop = set()
    if spec.get('exclude_round_one'):
        study, practice = sample(load_plan())
        drop |= set(study) | set(practice)
    if spec.get('exclude_re_read'):
        from .eligibility_reference_review import view as rr_view
        drop |= {it['nct_id'] for it in rr_view()['items']}
    pool = [n for n in order if n not in drop]
    if spec.get('expected_size') is not None and len(pool) != spec['expected_size']:
        raise ValueError(f"pool has {len(pool)} trials, the plan expects {spec['expected_size']}")
    return pool


def _order_seed(plan, reader):
    """The presentation-order seed. Plan v1 has one; plan v2 has one per reader, so the orders cannot coincide."""
    seed = plan['presentation_order_seed']
    if not isinstance(seed, dict):
        return seed
    seeds = {k: v for k, v in seed.items() if isinstance(v, int)}
    if reader is None:
        raise ValueError(f'this plan has a presentation order per reader; pass reader as one of {", ".join(sorted(seeds))}')
    if reader not in seeds:
        raise ValueError(f'unknown reader {reader!r}; expected one of {", ".join(sorted(seeds))}')
    return seeds[reader]


def sample(plan=None, reader=None):
    """(study trials in presentation order, practice trials). Uses only the annotation order and the plan's seeds.

    reader: required when the plan gives a presentation order per reader, as round two's does.
    """
    plan = plan or load_plan()
    order = v2.load_sample()['annotation_order']
    s = plan['sample']
    pool = _pool(order, s.get('pool'))
    chosen = random.Random(s['seed']).sample(pool, s['size'])
    random.Random(_order_seed(plan, reader)).shuffle(chosen)
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


def page_payload(plan=None, reader=None):
    """Everything the standalone page holds. Contains no label, extractor output or error selection."""
    plan = plan or load_plan()
    study, practice = sample(plan, reader)
    texts = dict(llm.criteria_texts(study))
    v1_texts = {t['nct_id']: t['eligibility']['criteria_text'] for t in llm.load_corpus()['trials'] if t['nct_id'] in set(practice)}
    types = [{'key': k, 'label': s['label'], 'units': list(s['units']), 'equations': list(s.get('equations', ())),
              'short': se.LABELS[k]} for k, s in ann2.TYPES.items()]
    p = {'plan_version': plan['plan_version'], 'plan_sha256': plan_sha256(plan), 'guide_sha256': hashlib.sha256(guide_path(plan).read_bytes()).hexdigest(),
         'types': types, 'statuses': list(ann2.STATUSES), 'comparators': list(ann2.COMPARATORS), 'sections': list(ann2.SECTIONS),
         'describes': list(ann2.DESCRIBES), 'max_values': ann2.MAX_VALUES,
         'practice': [{'nct_id': n, 'criteria_text': v1_texts[n]} for n in practice],
         'trials': [{'position': k, 'nct_id': n, 'criteria_text': texts[n]} for k, n in enumerate(study, 1)]}
    p['page_sha256'] = digest(p)
    return p


def write_page(path, plan=None, reader=None):
    """Writes the standalone page (one HTML file, no server needed). Returns its page_sha256.

    plan and reader are needed from round two on, where each reader has its own presentation order, so each
    reader gets their own page and their own page checksum.
    """
    import jinja2
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(ROOT / 'app' / 'templates')), autoescape=True)
    p = page_payload(plan, reader)
    page = env.get_template('eligibility_second_annotation_standalone.html').render(
        p=p, reader=reader_identity(reader), guide_label=guide_label(plan),
        guide_html=_md(guide_path(plan).read_text(encoding='utf-8')))
    Path(path).write_text(page, encoding='utf-8')
    return p['page_sha256']


def validate_record(record, p=None, reader=None, plan=None):
    """A returned record -> (problems, parsed annotations by NCT ID). Every study trial must be complete and valid.

    reader: who the record should be from ('owner' or 'annotator_b'). Checked against the record's own annotator
    code, so the two readers' records cannot be passed the wrong way round without the analysis saying so.
    plan: with reader, builds the payload for that reader's page instead of round one's.
    """
    if p is None:
        p = page_payload(plan, reader) if (plan is not None or reader is not None) else page_payload()
    problems, parsed = [], {}
    if record.get('schema_version') != RECORD_SCHEMA:
        problems.append('Unknown record format.')
    if reader is not None:
        want = reader_identity(reader)['code']
        got = (record.get('annotator') or {}).get('code')
        if got != want:
            problems.append(f'The record is from reader {got!r}, but reader {want!r} was expected.')
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


def _comparison(name):
    """The comparison a plan pins. v1 is as written, v2 applies the platform's equivalences (decision 0002)."""
    from .eligibility_reference_review import COMPARISONS
    if name not in COMPARISONS:
        raise ValueError(f'unknown comparison {name!r}; expected one of {", ".join(sorted(COMPARISONS))}')
    return COMPARISONS[name]


def agreement(record, p=None, record_a=None, pair_subset=None, comparison='v1', plan=None, p_a=None):
    """The plan's analysis. Raises if a record is invalid.

    record_a: an optional reader-A record, used in place of the owner's pinned annotation. Plan v2 has both
    readers work under annotation guide v3, so neither side is the pinned v2 annotation.
    pair_subset: optional "NCT:type" ids; adds an `overall_subset` block restricted to them, for the pairs
    the owner did not re-read in November.
    comparison: 'v1' (default) compares the value and unit as written; 'v2' applies the equivalences the extractor
    scoring already uses, which round two's plan pins. See docs/decisions/0002.
    plan: the plan whose analysis parameters govern. Defaults to plan v1, which is what produced the locked result;
    round two must pass its own, or the bootstrap seed and the bar would come from the wrong plan.
    p_a: reader A's own page payload, needed from round two on because each reader reads from their own page and a
    record carries the checksum of the page it was made from. Defaults to p, which is round one's arrangement.

    With all three left at their defaults the report is byte-identical to the plan v1 path, digest included.
    """
    p = p or page_payload()
    problems, b = validate_record(record, p)
    if problems:
        raise ValueError(problems)
    plan = plan or load_plan()
    trials = [t['nct_id'] for t in p['trials']]
    if (plan['analysis'].get('trial_order') or 'page') == 'sorted':
        # Each reader has their own page order from round two on, and the bootstrap resamples this list, so the
        # interval would depend on whose page was passed. Sorting makes it the same either way.
        trials = sorted(trials)
    if record_a is None:
        a_all = v2.load_annotations()['annotations']
        def a_get(n, t):
            return a_all[n]['criteria'][t]
        a_ref = {n: a_all[n] for n in trials}
    else:
        problems_a, a_parsed = validate_record(record_a, p_a or p)
        if problems_a:
            raise ValueError(problems_a)
        def a_get(n, t):
            return a_parsed[n][t]
        a_ref = {n: {'criteria': a_parsed[n]} for n in trials}
    cmp = _comparison(comparison)

    def agree(t, x, y):
        return cmp(t, x, y)

    per_type, all_exact, all_detect, pair_exact = {}, {}, [], {}
    for t in v2.TYPES:
        exact = [agree(t, a_get(n, t), b[n][t]) for n in trials]
        det = [(_detect(a_get(n, t)), _detect(b[n][t])) for n in trials]
        both = [n for n in trials if _detect(a_get(n, t)) == 'threshold' == _detect(b[n][t])]
        row = {'trials': len(trials), 'exact_agreement': sum(exact), 'exact_rate': round(sum(exact) / len(trials), 4),
               'exact_wilson_95': _wilson(sum(exact), len(trials)),
               'detection_agreement': sum(1 for x, y in det if x == y), 'detection_kappa': _kappa(det),
               'both_threshold': len(both), 'values_agree_when_both_threshold': sum(1 for n in both if agree(t, a_get(n, t), b[n][t]))}
        if t == 'kidney_function_min':
            row['equation_agree_when_both_threshold'] = sum(1 for n in both if a_get(n, t).get('equation') == b[n][t].get('equation'))
        per_type[t] = row
        for n, e in zip(trials, exact):
            all_exact.setdefault(n, []).append(e)
            pair_exact[f'{n}:{t}'] = e
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
    texts = {t['nct_id']: t['criteria_text'] for t in p['trials']}
    rule = {n: v2.ex.extract(texts[n]) for n in trials}
    model_all = se._llm_run_1(v2.load_sample()['annotation_order'])
    model = {n: model_all[n] for n in trials}
    extractors = {ref_name: {'v1_1': v2.summarise(val.score_run(ref, trials, rule)),
                             'llm_run_1': v2.summarise(val.score_run(ref, trials, model))}
                  for ref_name, ref in (('owner_annotation', a_ref), ('annotator_b', b_ref))}
    disagreements = [{'nct_id': n, 'type': t} for n in trials for t in v2.TYPES if not agree(t, a_get(n, t), b[n][t])]
    report = {'schema_version': 'eligibility-second-annotation-report-v1', 'plan_version': plan['plan_version'], 'plan_sha256': plan_sha256(plan),
              'page_sha256': p['page_sha256'], 'annotator': record.get('annotator', {}),
              'per_type': per_type, 'overall': overall,
              'reliability_reading': {'bar': bar, 'statistic': 'lower bound of the trial-bootstrap 95% interval of overall exact agreement',
                                      'value': round(lo, 4), 'reading': reading},
              'extractors_on_sample_descriptive': extractors,
              'disagreements_for_adjudication': disagreements,
              'clinical_prediction_validated': False}
    if comparison != 'v1':
        report['comparison'] = comparison
    if record_a is not None:
        report['readers'] = {'a': 'record', 'b': 'record'}
    if pair_subset is not None:
        keys = [k for k in pair_subset if k in pair_exact]
        n_sub, hits_sub = len(keys), sum(1 for k in keys if pair_exact[k])
        report['overall_subset'] = {'pairs': n_sub, 'exact_agreement': hits_sub,
                                    'exact_rate': round(hits_sub / n_sub, 4) if n_sub else None,
                                    'exact_wilson_95': _wilson(hits_sub, n_sub) if n_sub else None,
                                    'note': 'a prespecified subset of the 400 pairs; see the plan'}
    report['report_sha256'] = digest(report)
    return report
