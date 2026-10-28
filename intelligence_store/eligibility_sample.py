"""Phase 4.1c: the validation sample and development set for eligibility-threshold extraction.

Drawn once, by fixed rules, from the pinned corpus (eligibility_corpus_mm_cohort3_v1). The validation sample is
annotated by hand and used only to measure the extractor; the extractor is developed on the separate development set,
so its rules are never tuned on the trials that judge it. The rules are fixed in eligibility_validation_plan_v1.json.
"""
import random

from .eligibility_corpus import load_corpus

SEED = 20261022
SAMPLE_SIZE = 120
DEVELOPMENT_SIZE = 200
PHASE_GROUPS = (
    ('phase_1', {('PHASE1',), ('EARLY_PHASE1',)}),
    ('phase_1_2', {('PHASE1', 'PHASE2')}),
    ('phase_2', {('PHASE2',)}),
    ('phase_2_3_or_3', {('PHASE2', 'PHASE3'), ('PHASE3',)}),
    ('other', None),          # phase 4, not applicable, or not reported
)


def phase_group(phases):
    key = tuple(phases)
    for name, members in PHASE_GROUPS:
        if members is None or key in members:
            return name
    return 'other'


def allocation(counts, total):
    """Largest-remainder proportional allocation of `total` across groups (ties broken by group order)."""
    n = sum(counts.values())
    exact = {g: total * c / n for g, c in counts.items()}
    alloc = {g: int(v) for g, v in exact.items()}
    order = sorted(counts, key=lambda g: (-(exact[g] - alloc[g]), [p[0] for p in PHASE_GROUPS].index(g)))
    for g in order[:total - sum(alloc.values())]:
        alloc[g] += 1
    return alloc


def draw(corpus=None):
    corpus = corpus or load_corpus()
    eligible = sorted((t for t in corpus['trials'] if t['eligibility']['criteria_text']), key=lambda t: t['nct_id'])
    groups = {name: [t['nct_id'] for t in eligible if phase_group(t['phases']) == name] for name, _ in PHASE_GROUPS}
    alloc = allocation({g: len(ids) for g, ids in groups.items()}, SAMPLE_SIZE)
    rng = random.Random(SEED)
    sample = []
    for name, _ in PHASE_GROUPS:
        sample += sorted(rng.sample(groups[name], alloc[name]))
    chosen = set(sample)
    rest = [t['nct_id'] for t in eligible if t['nct_id'] not in chosen]
    development = sorted(rng.sample(rest, DEVELOPMENT_SIZE))
    order = list(sample)
    random.Random(SEED + 1).shuffle(order)        # annotation order mixes phases, so fatigue does not track phase
    return {'seed': SEED, 'corpus_content_sha256': corpus['corpus_sha256'], 'eligible_trials': len(eligible),
            'group_sizes': {g: len(ids) for g, ids in groups.items()}, 'allocation': alloc,
            'validation_sample': sample, 'annotation_order': order, 'development_set': development}


# ---------------------------------------------------------------- version 2 (Phase 4.2a)
SEED_V2 = 20261028
SAMPLE_SIZE_V2 = 200


def draw_v2(corpus=None, v1=None):
    """A fresh 200-trial validation sample, disjoint from the v1 sample and v1 development set (both of which are now
    development material), stratified by phase group as in v1."""
    corpus = corpus or load_corpus()
    v1 = v1 or draw(corpus)
    used = set(v1['validation_sample']) | set(v1['development_set'])
    eligible = sorted((t for t in corpus['trials'] if t['eligibility']['criteria_text'] and t['nct_id'] not in used),
                      key=lambda t: t['nct_id'])
    groups = {name: [t['nct_id'] for t in eligible if phase_group(t['phases']) == name] for name, _ in PHASE_GROUPS}
    alloc = allocation({g: len(ids) for g, ids in groups.items()}, SAMPLE_SIZE_V2)
    rng = random.Random(SEED_V2)
    sample = []
    for name, _ in PHASE_GROUPS:
        sample += sorted(rng.sample(groups[name], alloc[name]))
    order = list(sample)
    random.Random(SEED_V2 + 1).shuffle(order)
    return {'seed': SEED_V2, 'corpus_content_sha256': corpus['corpus_sha256'], 'excluded_as_used_in_v1': len(used),
            'eligible_trials': len(eligible), 'group_sizes': {g: len(ids) for g, ids in groups.items()}, 'allocation': alloc,
            'validation_sample': sample, 'annotation_order': order,
            'development_material': {'v1_development_set': len(v1['development_set']), 'v1_validation_sample': len(v1['validation_sample'])}}
