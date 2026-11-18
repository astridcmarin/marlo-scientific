"""Acceptance rule v2 extended to the Gupta 2017 ixazomib check and the second Luo 2021 daratumumab check
(plan acceptance_rule_v2_plan_v2.json; decision 0004).

The rule is plan v1's: pool the check's own simulated endpoint over an outer loop of parameter sets drawn from the
published uncertainty, each with its own virtual trials; classify the observed value against the 5th-95th percentile
with a 5% margin, under five seeds. What is new is where the draws come from. Gupta and Luo publish %RSE, not bootstrap
intervals, so each estimate is converted as the plan states (parameter_uncertainty), and the conversion itself is
varied in five uncertainty scenarios: independent (primary), two correlation scenarios, normal on the natural scale,
and each %RSE at the upper end of its rounding. A verdict that changes between them is reported as undecided.

Each check's own simulate_scenario is called unchanged, with a copy of its pinned extract in which the drawn
estimates replace the published ones. Neither check module is edited, and their committed reports stay as they are.

The observed values were seen long ago; this is a recheck under a new rule, not a blind test.
"""
import copy
import hashlib
import json
import random
from pathlib import Path

from . import parameter_uncertainty as pu
from .acceptance_rule_v2 import classify, summary
from .patient_state import digest

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'acceptance_rule_v2_plan_v2.json'
PLAN_SHA256 = 'fb790f68d960afc336ce8d3a25ecbb42126cce45930b7e744c963a0ae3c13d95'
REPORT_PATH = ROOT / 'docs' / 'verification' / 'acceptance_rule_v2_gupta_luo_v1.json'
SCHEMA_VERSION = 'acceptance-rule-v2-report-v2'
METHOD_VERSION = 'acceptance-rule-v2-gupta-luo-v1.0'
CHECKS = ('gupta_ixazomib', 'luo_daratumumab')
MODEL_KEY = {'gupta_ixazomib': 'gupta_2017', 'luo_daratumumab': 'luo_2021'}
UNDECIDED = 'undecided_across_uncertainty_scenarios'


def load_plan(path=PLAN_PATH):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError('The acceptance rule v2 plan v2 is missing or changed.')
    return json.loads(raw)


def _pinned_json(ref):
    raw = (ROOT / ref['file']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref['sha256']:
        raise ValueError(f"{ref['file']} does not match the checksum the plan pins.")
    return json.loads(raw)


def _check_spec(plan, check):
    return next(c for c in plan['scope']['checks'] if c['id'] == check)


# ---------------------------------------------------------------- the parameter draws the plan defines

def marginals(plan, check, extract, scenario):
    """The plan's marginals for one check under one uncertainty scenario."""
    key = MODEL_KEY[check]
    fx = extract['parameters']['fixed_effects']
    add = plan['uncertainty_scenarios'][scenario]['rse_add_percentage_points'][key]
    return [pu.marginal(d['name'], fx[d['name']], d['distribution'], d['sd'], add)
            for d in plan['parameter_uncertainty'][key]['draw']]


def cholesky_for(plan, check, margs, scenario):
    key = MODEL_KEY[check]
    names = [m['name'] for m in margs]
    spec = plan['uncertainty_scenarios'][scenario]['correlation']
    if spec is None:
        r = pu.correlation_matrix(names)
    elif 'uniform' in spec:
        among = [m['name'] for m in margs if m['distribution'] == spec['among']]
        r = pu.correlation_matrix(names, uniform=spec['uniform'], uniform_among=among)
    else:
        r = pu.correlation_matrix(names, pairs=[tuple(p) for p in spec['pairs'][key]])
    return pu.cholesky(r)


def with_values(extract, values):
    """A copy of a pinned extract with drawn fixed-effect values in place of the published ones."""
    x = copy.deepcopy(extract)
    for name, v in values.items():
        x['parameters']['fixed_effects'][name]['value'] = v
    return x


# ---------------------------------------------------------------- the two checks, through their own simulations

def _adapters(plan):
    """Per check: its extract, its simulation scenarios, its endpoints with observed values and old (v1) classes,
    a function running one parameter set's virtual trials, and one turning pooled raw output into endpoint values."""
    from . import ixazomib_pk_gupta_check as g
    from . import daratumumab_pk_luo_check as l1
    from . import daratumumab_pk_luo_check_v2 as l2
    out = {}

    gspec = _check_spec(plan, 'gupta_ixazomib')
    gplan = g.load_plan()
    if hashlib.sha256(g.PLAN_PATH.read_bytes()).hexdigest() != gspec['plan']['sha256']:
        raise ValueError('The Gupta check plan differs from the one this plan pins.')
    gex, gobs = g.load_inputs(gplan)
    if hashlib.sha256((ROOT / gspec['extract']['file']).read_bytes()).hexdigest() != gspec['extract']['sha256']:
        raise ValueError('The Gupta extract differs from the one this plan pins.')
    gold = _pinned_json(gspec['report'])
    obs = g._observed(gobs)

    def g_observed():
        o = {}
        for study, group, *_ in g.GROUPS:
            for ep in ('auc_last', 'cmax'):
                o[f'{study}.{group}.{ep}'] = obs[(study, group)][ep]
        for study, group in g.RATIOS:
            for ep in ('auc_last', 'cmax'):
                o[f'{study}.{group}_vs_normal.{ep}'] = (
                    (obs[(study, group)][ep] / obs[(study, group)]['dose_mg']) / (obs[(study, 'normal')][ep] / obs[(study, 'normal')]['dose_mg']))
        return o

    def g_old():
        o = {}
        for name, s in gold['scenarios'].items():
            o[name] = {}
            for r in s['groups']:
                for ep in ('auc_last', 'cmax'):
                    o[name][f"{r['study']}.{r['group']}.{ep}"] = r[ep]['classification']
            for r in s['ratios']:
                for ep in ('auc_last', 'cmax'):
                    o[name][f"{r['study']}.{r['group']}_vs_normal.{ep}"] = r[ep]['classification']
        return o

    def g_run(extract, settings, trials, seed):
        gm, _, info = g.simulate_scenario(extract, gobs, settings, trials, seed)
        return gm

    def g_pool(chunks):
        pooled = {}
        for gm in chunks:
            for key, eps in gm.items():
                for ep, vals in eps.items():
                    pooled.setdefault(key, {}).setdefault(ep, []).extend(vals)
        values = {}
        for study, group, dose, *_ in g.GROUPS:
            for ep in ('auc_last', 'cmax'):
                values[f'{study}.{group}.{ep}'] = [v * dose for v in pooled[(study, group)][ep]]
        for study, group in g.RATIOS:
            for ep in ('auc_last', 'cmax'):
                values[f'{study}.{group}_vs_normal.{ep}'] = [a / b for a, b in zip(pooled[(study, group)][ep], pooled[(study, 'normal')][ep])]
        return values

    gendpoints = list(gold['classification_by_endpoint'])
    out['gupta_ixazomib'] = {'extract': gex, 'scenarios': dict(g.SCENARIOS), 'endpoints': gendpoints,
                             'kind': {e: 'primary' for e in gendpoints}, 'observed': g_observed(), 'old': g_old(),
                             'run': g_run, 'pool': g_pool}

    lspec = _check_spec(plan, 'luo_daratumumab')
    lplan = l2.load_plan()
    if hashlib.sha256(l2.PLAN_PATH.read_bytes()).hexdigest() != lspec['plan']['sha256']:
        raise ValueError('The Luo check plan differs from the one this plan pins.')
    lex, lobs, sup = l2.load_inputs(lplan)
    if hashlib.sha256((ROOT / lspec['extract']['file']).read_bytes()).hexdigest() != lspec['extract']['sha256']:
        raise ValueError('The Luo extract differs from the one this plan pins.')
    covariates = l2.study_covariates(sup)
    lold = _pinned_json(lspec['report'])

    def l_run(extract, settings, trials, seed):
        return l2.simulate_scenario(extract, covariates, settings, trials, seed)

    def l_pool(chunks):
        values = {}
        for means in chunks:
            for eid, vals in means.items():
                values.setdefault(eid, []).extend(vals)
        return values

    out['luo_daratumumab'] = {
        'extract': lex, 'scenarios': dict(l1.SCENARIOS), 'endpoints': [e[0] for e in l1.ENDPOINTS],
        'kind': {e[0]: e[-1] for e in l1.ENDPOINTS},
        'observed': {e[0]: l1.observed_value(lobs, e[5])['mean'] for e in l1.ENDPOINTS},
        'old': {name: {r['endpoint']: r['classification'] for r in s['endpoints']} for name, s in lold['scenarios'].items()},
        'run': l_run, 'pool': l_pool}
    return out


def cell(plan, check, adapter, sim_name, sim_index, unc_name, seed, n_outer, inner):
    """One (check, simulation scenario, uncertainty scenario, seed): pooled endpoint summaries and redraw count."""
    margs = marginals(plan, check, adapter['extract'], unc_name)
    low = cholesky_for(plan, check, margs, unc_name)
    shape = plan['uncertainty_scenarios'][unc_name]['shape']
    param_rng = random.Random(seed + 1000 * sim_index)
    sim_rng = random.Random(seed + 1000 * sim_index + 500)
    settings = adapter['scenarios'][sim_name]
    chunks, redraws = [], 0
    for _ in range(n_outer):
        values, r = pu.draw(param_rng, margs, low, shape)
        redraws += r
        chunks.append(adapter['run'](with_values(adapter['extract'], values), settings, inner, sim_rng.randrange(2 ** 62)))
    pooled = adapter['pool'](chunks)
    return {'summaries': {e: summary(pooled[e]) for e in adapter['endpoints']}, 'redraws': redraws}


def reading(on_primary, independent, verdict_v1):
    """The plan's reading of one endpoint. on_primary: {uncertainty scenario: verdict} on the primary simulation
    scenario; independent: {simulation scenario: verdict} under the independent scenario."""
    v2 = on_primary['independent']
    stable = len(set(on_primary.values())) == 1
    r = v2 if stable else UNDECIDED
    return {'verdict_v2': v2, 'by_uncertainty_scenario': on_primary, 'stable': stable, 'reading': r,
            'by_simulation_scenario': independent, 'robust_across_simulation_scenarios': len(set(independent.values())) == 1,
            'verdict_v1': verdict_v1, 'changed': r != verdict_v1}


_STATE = {}


def _cell_task(task):
    """One cell in a worker process. Under fork the parent's plan and adapters are inherited; otherwise (spawn, as on
    macOS) they are rebuilt from the pinned plan, which is why only the pinned plan can run in parallel."""
    if not _STATE:
        plan = load_plan()
        _STATE.update(plan=plan, adapters=_adapters(plan))
    check, sim_name, si, unc_name, seed, outer, per_set = task
    return task, cell(_STATE['plan'], check, _STATE['adapters'][check], sim_name, si, unc_name, seed, outer, per_set)


def run_check(plan=None, observed_override=None, n_outer=None, inner=None, seeds=None, checks=CHECKS,
              simulation_scenarios=None, workers=1):
    """The rule over both checks. observed_override ({check: {endpoint: value}}) replaces the observed values, for the
    synthetic dry run committed with the plan; n_outer, inner, seeds and simulation_scenarios only for tests.
    workers: cells run in that many processes. Each cell has its own generators, so the report is the same for any
    number of workers."""
    plan = plan or load_plan()
    rule = plan['rule']
    seeds = seeds or rule['seeds']
    margin = rule['indeterminate_margin']
    adapters = _adapters(plan)
    unc = plan['uncertainty_scenarios']
    results = {}
    for check in checks:
        a = adapters[check]
        outer = n_outer or rule['outer_parameter_sets'][check]
        per_set = inner or rule['inner_trials_per_set'][check]
        if observed_override is not None:
            synthetic = observed_override.get(check, {})
            if set(synthetic) != set(a['endpoints']):
                raise ValueError(f'{check}: a synthetic run must replace every observed value, and only those.')
            observed = dict(synthetic)
        else:
            observed = dict(a['observed'])
        sims = list(a['scenarios'])
        if simulation_scenarios:
            sims = [s for s in sims if s in simulation_scenarios]
        if sims[0] != 'primary':
            raise ValueError('The primary simulation scenario must be run first.')
        tasks = []
        for si, sim_name in enumerate(a['scenarios']):
            if sim_name not in sims:
                continue
            for unc_name, spec in unc.items():
                if spec['run_on'] == 'primary simulation scenario' and sim_name != 'primary':
                    continue
                tasks += [(check, sim_name, si, unc_name, seed, outer, per_set) for seed in seeds]
        if workers > 1:
            import multiprocessing
            _STATE.clear()
            _STATE.update(plan=plan, adapters=adapters)
            with multiprocessing.Pool(workers) as pool:
                done = dict(pool.map(_cell_task, tasks))
            _STATE.clear()
        else:
            done = {t: cell(plan, check, a, t[1], t[2], t[3], t[4], outer, per_set) for t in tasks}
        cells, redraws = {}, {}
        for t in tasks:
            key = (t[1], t[3])
            cells.setdefault(key, []).append(done[t]['summaries'])
            redraws[f'{t[1]}/{t[3]}'] = redraws.get(f'{t[1]}/{t[3]}', 0) + done[t]['redraws']
        rows, endpoints = [], {}
        for (sim_name, unc_name), by_seed in cells.items():
            for e in a['endpoints']:
                classes = [classify(observed[e], s[e], margin) for s in by_seed]
                verdict = classes[0] if len(set(classes)) == 1 else 'indeterminate'
                rows.append({'endpoint': e, 'simulation_scenario': sim_name, 'uncertainty_scenario': unc_name,
                             'observed': observed[e], 'simulated_first_seed': by_seed[0][e], 'class_by_seed': classes,
                             'verdict': verdict})
        for e in a['endpoints']:
            on_primary = {r['uncertainty_scenario']: r['verdict'] for r in rows
                          if r['endpoint'] == e and r['simulation_scenario'] == 'primary'}
            independent = {r['simulation_scenario']: r['verdict'] for r in rows
                           if r['endpoint'] == e and r['uncertainty_scenario'] == 'independent'}
            endpoints[e] = dict(kind=a['kind'][e], **reading(on_primary, independent, a['old'].get('primary', {}).get(e)))
        results[check] = {'outer_parameter_sets': outer, 'inner_trials_per_set': per_set, 'endpoints': endpoints,
                          'redraws_non_positive': redraws, 'rows': rows}
    changes = [{'check': c, 'endpoint': e, 'verdict_v1': v['verdict_v1'], 'reading': v['reading']}
               for c, r in results.items() for e, v in r['endpoints'].items() if v['changed']]
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'synthetic_observed': observed_override is not None, 'seeds': seeds,
              'indeterminate_margin': margin, 'uncertainty_scenarios': list(unc), 'results': results,
              'changes_from_v1': changes, 'not_this': plan['not_this'], 'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report
