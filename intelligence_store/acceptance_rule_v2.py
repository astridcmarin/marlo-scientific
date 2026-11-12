"""Acceptance rule v2 for the published-model lenalidomide checks (AI review F03; plan acceptance_rule_v2_plan_v1.json).

The four checks of Hughes 2019 and Kim 2026 against kidney-function groups (CC-5013-PK-001 twice, the study-matched
recheck, Bridoux 2016) judged "consistent" with the 5th-95th percentile of simulated group values that varied only
between patients. Rule v2 adds the uncertainty of the published estimates: an outer loop of parameter sets drawn from
each paper's bootstrap 95% intervals (parameter_draws, two-piece log-normal), each with its own virtual trials. Each
check's own simulation, scenarios, group sizes, covariates and primary endpoint (the exposure ratio of each impaired
group to the normal group) are used unchanged, through optional hooks that leave their own results as they were.

A result is "indeterminate" when the observed value lies within the plan's margin of either limit, or when its class
changes between the plan's seeds. Old verdicts are not changed; they are reported beside the new ones.

The datasets were seen long ago; this is a recheck under a new rule, not a blind test.
"""
import copy
import hashlib
import json
import random
from pathlib import Path

from .parameter_draws import draw, spreads
from .patient_state import digest

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'acceptance_rule_v2_plan_v1.json'
PLAN_SHA256 = '75ea018e97adde8ec9af997f6fe0099515e0928c586d237b8fa41aa7303a4046'
REPORT_PATH = ROOT / 'docs' / 'verification' / 'acceptance_rule_v2_lenalidomide_v1.json'
SCHEMA_VERSION = 'acceptance-rule-v2-report-v1'
METHOD_VERSION = 'acceptance-rule-v2-v1.0'
CHECKS = ('hughes_cc5013', 'kim_cc5013', 'renal_recheck', 'bridoux_hughes_kim')
IMPAIRED = ('mild', 'moderate', 'severe')
HUGHES_KEYS = {'theta_cl': 'apparent_clearance', 'theta_crcl': 'crcl_exponent', 'theta_v': 'apparent_volume'}
HUGHES = 'lenalidomide_hughes_2019'
KIM = 'lenalidomide_kim_2026'


def load_plan(path=PLAN_PATH):
    raw = Path(path).read_bytes()
    if PLAN_SHA256 is not None and hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError('The acceptance rule v2 plan is missing or changed.')
    return json.loads(raw)


def _percentile(ordered, q):
    pos = (len(ordered) - 1) * q / 100.0
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def summary(values):
    ordered = sorted(values)
    return {'p05': _percentile(ordered, 5), 'p50': _percentile(ordered, 50), 'p95': _percentile(ordered, 95)}


def classify(observed, s, margin):
    """consistent, model_under_predicts, model_over_predicts, or indeterminate (within the margin of either limit)."""
    for limit in (s['p05'], s['p95']):
        if limit * (1 - margin) <= observed <= limit * (1 + margin):
            return 'indeterminate'
    if observed > s['p95']:
        return 'model_under_predicts'
    if observed < s['p05']:
        return 'model_over_predicts'
    return 'consistent'


# ---------------------------------------------------------------- parameter draws

def hughes_spread():
    from .population_pk import load_parameter_precision
    fx = load_parameter_precision()['fixed_effects']
    return spreads({k: (fx[k]['estimate'], fx[k]['bootstrap_ci95']) for k in HUGHES_KEYS})


def kim_spread():
    from .kim_model import load_extract
    p = load_extract()['parameters']
    return spreads({k: (v['value'], v['bootstrap_ci95']) for k, v in p.items() if 'bootstrap_ci95' in v and not v.get('fixed')})


def hughes_parameters(d):
    from .pk_parameter_reference import load_parameter_extract
    p = copy.deepcopy(load_parameter_extract()['parameters'])
    for k, name in HUGHES_KEYS.items():
        p[name]['value'] = d[k]
    return p


def kim_extract(d):
    from .kim_model import load_extract
    x = copy.deepcopy(load_extract())
    for k, v in d.items():
        x['parameters'][k]['value'] = v
    return x


# ---------------------------------------------------------------- the four checks, through their own simulations

def _adapters():
    """For each check: its scenarios, the models per scenario, the observed ratio per (model, group), the old (v1)
    class per (scenario, model, group), and a function that runs one parameter set and returns raw group values."""
    from . import renal_group_check as rg, kim_renal_group_check as kc, renal_group_recheck as rc
    from . import lenalidomide_bridoux_check as bc
    from .covariate_estimation import load_variability_extract
    from .kim_model import load_extract

    def committed(path):
        return json.loads((ROOT / path).read_text())

    out = {}
    # Hughes against CC-5013-PK-001
    plan = rg.load_plan(); observed = rg.load_observed(plan)
    omega = load_variability_extract()['random_effects']['omega_matrix']
    old = committed('docs/verification/hughes_renal_group_check_v1.json')

    def run_h(name, seed, trials, hd, kd, plan=plan, observed=observed):
        c = {}
        rg.simulate_scenario(plan, rg._scenario(plan, name), observed, hughes_parameters(hd), omega, trials, seed, c)
        return {HUGHES: c['auc_means']}
    out['hughes_cc5013'] = {
        'scenarios': {n: (HUGHES,) for n in plan['scenarios']}, 'run': run_h,
        'observed': {HUGHES: {g: observed[g]['auc_infinity_mean'] / observed['normal']['auc_infinity_mean'] for g in IMPAIRED}},
        'old': {n: {HUGHES: {r['group']: r['auc_ratio_to_normal']['classification'] for r in s['groups'] if r['group'] in IMPAIRED}}
                for n, s in old['scenarios'].items()},
        'endpoint': 'AUC to infinity, each impaired group relative to normal'}
    # Kim against CC-5013-PK-001
    kplan = kc.load_plan(); kobserved = rg.load_observed(kplan)
    old = committed('docs/verification/kim_renal_group_check_v1.json')

    def run_k(name, seed, trials, hd, kd, plan=kplan, observed=kobserved):
        c = {}
        kc.simulate_scenario(plan, kc.scenario_settings(plan, name), observed, kim_extract(kd), trials, seed, c)
        return {KIM: c['auc_means']}
    out['kim_cc5013'] = {
        'scenarios': {n: (KIM,) for n in kplan['scenarios']}, 'run': run_k,
        'observed': {KIM: {g: kobserved[g]['auc_infinity_mean'] / kobserved['normal']['auc_infinity_mean'] for g in IMPAIRED}},
        'old': {n: {KIM: {r['group']: r['auc_ratio_to_normal']['classification'] for r in s['groups'] if r['group'] in IMPAIRED}}
                for n, s in old['scenarios'].items()},
        'endpoint': 'AUC to infinity, each impaired group relative to normal'}
    # Study-matched recheck
    rplan = rc.load_plan(); demo = rc.load_demographics(rplan)
    robserved = rg.load_observed({'observed_data': rplan['observed_data']})
    old = committed('docs/verification/lenalidomide_renal_recheck_v1.json')
    rmodels = {n: ((KIM,) if n == 'sensitivity_kim_exponential' else tuple(rc.V1_PRIMARY)) for n in rplan['scenarios']}

    def run_r(name, seed, trials, hd, kd, plan=rplan, observed=robserved, demo=demo):
        c = {}
        rc.simulate(plan, name, rmodels[name], demo, observed, trials, seed, c, hughes_parameters(hd), kim_extract(kd))
        return c['means']
    ratio = {g: robserved[g]['auc_infinity_mean'] / robserved['normal']['auc_infinity_mean'] for g in IMPAIRED}
    out['renal_recheck'] = {
        'scenarios': rmodels, 'run': run_r, 'observed': {m: dict(ratio) for m in rc.V1_PRIMARY},
        'old': {n: {m: {r['group']: r['auc_ratio_to_normal']['classification'] for r in rows if r['group'] in IMPAIRED}
                    for m, rows in s.items()} for n, s in old['scenarios'].items()},
        'endpoint': 'AUC to infinity, each impaired group relative to normal'}
    # Bridoux 2016
    bplan, design, bobserved = bc.load_plan(), bc.load_design(), bc.load_observed()
    bdemo = bc.demographics(design)
    old = committed('docs/verification/lenalidomide_bridoux_check_v1.json')
    bmodels = {n: ((KIM,) if n in ('sensitivity_kim_exponential', 'sensitivity_ideal_weight_basis') else bc.MODELS)
               for n in bplan['scenarios']}

    def run_b(name, seed, trials, hd, kd, observed=bobserved, demo=bdemo):
        c = {}
        bc.simulate(name, bmodels[name], demo, observed, trials, seed, c, hughes_parameters(hd), kim_extract(kd))
        return c['dn']
    obs = bobserved['groups']
    dn = {g: obs[g]['auc24_gm'] / obs[g]['dose_mg_per_24h'] for g in ('normal',) + IMPAIRED}
    out['bridoux_hughes_kim'] = {
        'scenarios': bmodels, 'run': run_b, 'observed': {m: {g: dn[g] / dn['normal'] for g in IMPAIRED} for m in bc.MODELS},
        'old': {n: {m: {r['group']: r['dose_normalised_ratio_to_normal']['classification'] for r in rows if r['group'] in IMPAIRED}
                    for m, rows in s.items()} for n, s in old['scenarios'].items()},
        'endpoint': 'Dose-normalised AUC24, each impaired group relative to normal'}
    return out


def simulate_ratios(adapter, name, seed, n_outer, inner, hs, ks):
    """Pooled ratio-to-normal values per (model, group) over n_outer parameter sets of inner virtual trials each."""
    pooled = {m: {g: [] for g in IMPAIRED} for m in adapter['scenarios'][name]}
    rng = random.Random(seed)
    for _ in range(n_outer):
        hd, kd = draw(rng, hs), draw(rng, ks)
        raw = adapter['run'](name, rng.randrange(2 ** 62), inner, hd, kd)
        for m in pooled:
            for g in IMPAIRED:
                pooled[m][g].extend(a / b for a, b in zip(raw[m][g], raw[m]['normal']))
    return pooled


def run_check(plan=None, observed_override=None, n_outer=None, inner=None, seeds=None, checks=CHECKS):
    """The rule over the four checks. observed_override ({check: {model: {group: ratio}}}) replaces the observed
    ratios, for the synthetic dry run committed with the plan; n_outer, inner and seeds only for tests."""
    plan = plan or load_plan()
    rule = plan['rule']
    n_outer, inner = n_outer or rule['outer_parameter_sets'], inner or rule['inner_trials_per_set']
    seeds = seeds or rule['seeds']
    margin = rule['indeterminate_margin']
    hs, ks = hughes_spread(), kim_spread()
    adapters = _adapters()
    results, changes = {}, []
    for check in checks:
        a = adapters[check]
        observed = (observed_override or {}).get(check, a['observed'])
        rows = []
        for si, name in enumerate(a['scenarios']):
            by_seed = [simulate_ratios(a, name, seed + 1000 * si, n_outer, inner, hs, ks) for seed in seeds]
            for m in a['scenarios'][name]:
                for g in IMPAIRED:
                    sums = [summary(p[m][g]) for p in by_seed]
                    classes = [classify(observed[m][g], s, margin) for s in sums]
                    verdict = classes[0] if len(set(classes)) == 1 else 'indeterminate'
                    old = a['old'].get(name, {}).get(m, {}).get(g)
                    row = {'scenario': name, 'model': m, 'group': g, 'observed_ratio': observed[m][g],
                           'simulated_ratio_first_seed': sums[0], 'class_by_seed': classes, 'verdict_v2': verdict,
                           'verdict_v1': old, 'changed': verdict != old,
                           'margin_to_nearest_limit': min(abs(observed[m][g] / s[k] - 1) for s in sums for k in ('p05', 'p95'))}
                    rows.append(row)
                    if row['changed']:
                        changes.append({k: row[k] for k in ('scenario', 'model', 'group', 'verdict_v1', 'verdict_v2')} | {'check': check})
        primary = {m: {r['group']: r['verdict_v2'] for r in rows if r['scenario'] == 'primary' and r['model'] == m}
                   for m in {r['model'] for r in rows}}
        results[check] = {'endpoint': a['endpoint'], 'primary_v2': primary, 'rows': rows}
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'synthetic_observed': observed_override is not None,
              'outer_parameter_sets': n_outer, 'inner_trials_per_set': inner, 'seeds': seeds, 'indeterminate_margin': margin,
              'results': results, 'changes_from_v1': changes, 'not_this': plan['not_this'],
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report
