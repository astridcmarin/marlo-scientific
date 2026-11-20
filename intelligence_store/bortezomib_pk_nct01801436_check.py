"""Simulation 3.0n: blind check of two bortezomib PK models against NCT01801436 day 1 and day 11 results.

NCT01801436 (post-approval PK study in Taiwan, 1.3 mg/m2 on days 1, 4, 8 and 11; per-protocol n = 10) posted
non-compartmental results for days 1 and 11 of cycle 1, sampled 0.08-72 h after the dose. Apart from the day 1
clearance seen in a search snippet (ledger v19), the values are unread (dataset nct01801436_bortezomib_pk_unread).

This module samples each model at the study's times, runs a non-compartmental emulation that follows the outcome
definitions posted with the results, and classifies each endpoint as fixed in
bortezomib_pk_nct01801436_check_plan_v1.json (locked before computation). Nothing is estimated or tuned.
run_check() refuses to run until the observed file is pinned; dry_run() runs the same code on synthetic values.
"""
import hashlib
import json
import math
from pathlib import Path

import click

from . import bortezomib_pbpk_iwasaki as iwasaki_model
from . import dataset_ledger
from .bortezomib_pbpk_iwasaki_check import bsa_du_bois, simulate as iwasaki_simulate
from .bortezomib_pk import concentration_ng_ml, rate_constants, unit_bolus_coefficients
from .bortezomib_pk_ogawa_check import _classify

DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'bortezomib_pk_nct01801436_check_plan_v1.json'
PLAN_SHA256 = 'a2face39c78f84a044db24b3381d5d12e72431b0b3cc751f985a22e1ffa85d61'
OBSERVED_PATH = DATA / 'bortezomib_pk_nct01801436_observed_v1.json'
OBSERVED_SHA256 = 'ac0a819e6e1e777c88124a770eee8c87cb3ae478341949b04888e40ee5a7a910'
REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'bortezomib_pk_nct01801436_check_v1.json'
SCHEMA_VERSION = 'bortezomib-pk-external-check-report-v1'
METHOD_VERSION = 'bortezomib-pk-nct01801436-check-v1.0'

DATASET = 'nct01801436_bortezomib_pk_unread'
MODELS = ('bortezomib_pk_lignet_2022', 'bortezomib_pbpk_iwasaki_2020_candidate')
DOSE_MG_M2 = 1.3
DOSE_TIMES_H = (0.0, 72.0, 168.0, 240.0)
DAY11_START_H = 240.0
SAMPLING_H = (0.08, 0.25, 0.5, 1.0, 2.0, 4.0, 6.0, 8.0, 12.0, 24.0, 48.0, 72.0)
SAMPLING_H_FIVE_MIN = (5.0 / 60.0,) + SAMPLING_H[1:]
N = 10
T975_9 = 2.2622
BODY = {'weight_kg': 60.0, 'height_cm': 160.0}
BODY_SENSITIVITY = ({'weight_kg': 50.0, 'height_cm': 155.0}, {'weight_kg': 72.0, 'height_cm': 168.0})
NCA_READINGS = (('linear', 3), ('linear', 4), ('linear_up_log_down', 3), ('linear_up_log_down', 4))
PRIMARY_READING = ('linear', 3)
IWASAKI_STEP_H = 0.00025

BLIND_ENDPOINTS = ('auc_last_day11', 'cmax_day11', 'cl_day11', 'vss_day11', 'half_life_day11', 'cmax_day1')
PRIMARY_ENDPOINT = 'auc_last_day11'
NOT_BLIND_ENDPOINTS = ('auc_last_day1', 'vss_day1', 'auc_last_ratio_day11_over_day1')
EXCLUDED = ('cl_day1', 'auc_inf_day1')
OBSERVED_KEYS = BLIND_ENDPOINTS + ('auc_last_day1', 'vss_day1')


def _pinned(path, expected, label):
    if expected is None:
        raise ValueError(f'{label} is not locked yet; nothing was computed.')
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'{label} is missing or changed; nothing was computed.')
    return json.loads(raw)


def load_plan(path=PLAN_PATH):
    return _pinned(path, PLAN_SHA256, 'NCT01801436 check plan')


def load_observed(path=OBSERVED_PATH):
    return _pinned(path, OBSERVED_SHA256, 'NCT01801436 observed values')


def nca(times_h, conc, auc_rule, terminal_points, dose_ug):
    """Emulation of the posted definitions for one profile sampled after a dose (times exclude the dose time).

    C0 by log-linear back-extrapolation from the first two samples; Cmax and tmax read from the samples. AUC0-t by
    trapezoids from (0, C0) to the last sample (linear, or linear-up/log-down). Lambda z: least-squares slope of ln C
    over the last `terminal_points` samples. AUCinf = AUC0-t + Clast / lambda z. AUMC by linear trapezoids on t x C
    plus Clast tlast / lambda z + Clast / lambda z^2, as the posted AUMC formula. MRT = AUMCinf / AUCinf;
    CL = dose / AUCinf; Vss = CL x MRT (the posted formulas, applied on day 11 as written).
    """
    if len(times_h) != len(conc) or len(times_h) < max(3, terminal_points) or any(not math.isfinite(c) or c <= 0 for c in conc):
        raise ValueError('Profile unusable for NCA.')
    t1, t2, c1, c2 = times_h[0], times_h[1], conc[0], conc[1]
    c0 = math.exp(math.log(c1) - (math.log(c2) - math.log(c1)) / (t2 - t1) * t1)
    t, c = [0.0] + list(times_h), [c0] + list(conc)
    auc = aumc = 0.0
    for i in range(1, len(t)):
        dt, a, b = t[i] - t[i - 1], c[i - 1], c[i]
        if auc_rule == 'linear_up_log_down' and b < a:
            auc += dt * (a - b) / math.log(a / b)
        elif auc_rule in ('linear', 'linear_up_log_down'):
            auc += dt * (a + b) / 2.0
        else:
            raise ValueError('Unknown AUC rule.')
        aumc += dt * (a * t[i - 1] + b * t[i]) / 2.0
    xs, ys = times_h[-terminal_points:], [math.log(v) for v in conc[-terminal_points:]]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    lam = -sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    if lam <= 0:
        raise ValueError('Terminal phase is not declining.')
    c_last, t_last = conc[-1], times_h[-1]
    auc_inf = auc + c_last / lam
    aumc_inf = aumc + c_last * t_last / lam + c_last / lam ** 2
    imax = max(range(len(conc)), key=lambda i: conc[i])
    cl = dose_ug / auc_inf  # ug / (ng h/mL) = L/h
    mrt = aumc_inf / auc_inf
    return {'c0_ng_ml': c0, 'cmax_ng_ml': conc[imax], 'tmax_h': times_h[imax], 'auc_last_ng_h_ml': auc,
            'lambda_z_per_h': lam, 'half_life_h': math.log(2) / lam, 'auc_inf_ng_h_ml': auc_inf,
            'aumc_inf_ng_h2_ml': aumc_inf, 'mrt_h': mrt, 'cl_l_h': cl, 'vss_l': cl * mrt}


def lignet_profiles(times, extract=None):
    """Constant-clearance three-compartment model (bortezomib_pk, Lignet 2022 per-m2 parameters). A sample at a dose
    time is taken before that dose (the day 1 72 h sample is the day 4 pre-dose sample)."""
    terms = unit_bolus_coefficients(rate_constants(extract))
    events = [(t, DOSE_MG_M2) for t in DOSE_TIMES_H]
    def at(t):
        return concentration_ng_ml(t, [e for e in events if e[0] < t], terms)
    return {'day1': [at(s) for s in times], 'day11': [at(DAY11_START_H + s) for s in times]}


def iwasaki_profiles(times, body, step_h=IWASAKI_STEP_H, extract=None):
    """Iwasaki 2020 PBPK (unchanged module), dosed in ug/kg from the assumed body size; same pre-dose convention
    (bortezomib_pbpk_iwasaki_check.simulate reads a sample at a dose time before the dose)."""
    p = iwasaki_model.parameters(extract)
    dose_ug_kg = DOSE_MG_M2 * 1000.0 * bsa_du_bois(body['weight_kg'], body['height_cm']) / body['weight_kg']
    day1, day11 = list(times), [DAY11_START_H + s for s in times]
    sim = iwasaki_simulate(p, dose_ug_kg, set(day1) | set(day11), step_h=step_h)
    return {'day1': [sim['conc'][s] for s in day1], 'day11': [sim['conc'][s] for s in day11],
            'mass_balance_error': sim['mass_balance_error']}


def model_endpoints(profiles, times, reading, body):
    dose_ug = DOSE_MG_M2 * 1000.0 * bsa_du_bois(body['weight_kg'], body['height_cm'])
    d1 = nca(times, profiles['day1'], reading[0], reading[1], dose_ug)
    d11 = nca(times, profiles['day11'], reading[0], reading[1], dose_ug)
    return {'auc_last_day11': d11['auc_last_ng_h_ml'], 'cmax_day11': d11['cmax_ng_ml'], 'cl_day11': d11['cl_l_h'],
            'vss_day11': d11['vss_l'], 'half_life_day11': d11['half_life_h'], 'cmax_day1': d1['cmax_ng_ml'],
            'auc_last_day1': d1['auc_last_ng_h_ml'], 'vss_day1': d1['vss_l'],
            'auc_last_ratio_day11_over_day1': d11['auc_last_ng_h_ml'] / d1['auc_last_ng_h_ml'],
            'context_not_compared': {'cl_day1': d1['cl_l_h'], 'auc_inf_day1': d1['auc_inf_ng_h_ml'],
                                     'tmax_day1': d1['tmax_h'], 'tmax_day11': d11['tmax_h']}}


def interval(mean, sd, n=N):
    if n != N:
        raise ValueError('The plan fixes t(0.975, 9) for n = 10; a different n needs a plan amendment.')
    half = T975_9 * sd / math.sqrt(n)
    return [mean - half, mean + half]


def _validate_observed(observed):
    vals = observed['endpoints']
    missing = [k for k in OBSERVED_KEYS if k not in vals]
    if missing:
        raise ValueError(f'Observed file lacks {missing}.')
    for k in EXCLUDED:
        if k in vals:
            raise ValueError(f'{k} is excluded by the plan and must not be in the observed file.')
    for k in OBSERVED_KEYS:
        if vals[k]['n'] != N:
            raise ValueError(f'{k}: n = {vals[k]["n"]}, plan fixes n = {N}.')
    return vals


def _compare(observed, scenarios):
    """scenarios: {model: {label: endpoints}}, label 'primary' plus sensitivity labels."""
    vals = _validate_observed(observed)
    out = {}
    for model, by_label in scenarios.items():
        rows = {}
        for ep in BLIND_ENDPOINTS:
            o = vals[ep]
            ci = interval(o['mean'], o['sd'])
            classes = {label: _classify(e[ep], ci) for label, e in by_label.items()}
            rows[ep] = {'observed_mean': o['mean'], 'observed_sd': o['sd'], 'n': o['n'], 'interval_95': ci,
                        'model_primary': by_label['primary'][ep], 'class_primary': classes['primary'],
                        'classes_all_readings': classes, 'robust': len(set(classes.values())) == 1}
        descriptive = {ep: {'observed_mean': vals[ep]['mean'] if ep in vals else None,
                            'model_primary': by_label['primary'][ep], 'not_blind': True}
                       for ep in NOT_BLIND_ENDPOINTS}
        if 'auc_last_day1' in vals:
            descriptive['auc_last_ratio_day11_over_day1']['observed_ratio_of_means'] = (
                vals['auc_last_day11']['mean'] / vals['auc_last_day1']['mean'])
        prim = rows[PRIMARY_ENDPOINT]['class_primary']
        out[model] = {'blind_endpoints': rows, 'descriptive_not_blind': descriptive,
                      'primary_class': prim, 'primary_robust': rows[PRIMARY_ENDPOINT]['robust'],
                      'recorded_as': 'consistent' if prim == 'consistent' else prim}
    return out


def model_scenarios(iwasaki_step_h=IWASAKI_STEP_H, extract_lignet=None, extract_iwasaki=None):
    """Every model value the comparison needs: primary reading, the other NCA readings, the 5-minute first sample,
    and (for anything in absolute units, and for every Iwasaki value) the two other body sizes."""
    scen = {m: {} for m in MODELS}
    for times, tlabel in ((SAMPLING_H, ''), (SAMPLING_H_FIVE_MIN, '_first_sample_5min')):
        lig = lignet_profiles(times, extract_lignet)
        iwa = {i: iwasaki_profiles(times, b, iwasaki_step_h, extract_iwasaki)
               for i, b in enumerate((BODY,) + BODY_SENSITIVITY)}
        for reading in NCA_READINGS:
            rlabel = 'primary' if (reading == PRIMARY_READING and not tlabel) else f'{reading[0]}_{reading[1]}pt{tlabel}'
            if reading != PRIMARY_READING and tlabel:
                continue
            scen[MODELS[0]][rlabel] = model_endpoints(lig, times, reading, BODY)
            scen[MODELS[1]][rlabel] = model_endpoints(iwa[0], times, reading, BODY)
            if rlabel == 'primary':
                for i, b in enumerate(BODY_SENSITIVITY, start=1):
                    scen[MODELS[0]][f'body_{b["weight_kg"]:g}kg_{b["height_cm"]:g}cm'] = model_endpoints(lig, times, reading, b)
                    scen[MODELS[1]][f'body_{b["weight_kg"]:g}kg_{b["height_cm"]:g}cm'] = model_endpoints(iwa[i], times, reading, b)
    mass_balance = max(p['mass_balance_error'] for p in iwa.values())
    return scen, {'iwasaki_max_mass_balance_error': mass_balance, 'iwasaki_step_h': iwasaki_step_h}


def check_blind_allowed(ledger=None):
    """Before the result: the ledger gate. After it: the ledger must hold this plan's checked_blind use for each model
    (the dataset is then marked seen, so the gate alone would refuse a rerun of the recorded check)."""
    ledger = ledger or dataset_ledger.load_ledger()
    plan_path = 'intelligence_store/data/' + PLAN_PATH.name
    for m in MODELS:
        if any(u['model'] == m and u['dataset'] == DATASET and u['role'] == 'checked_blind' and u.get('plan') == plan_path
               for u in ledger['uses']):
            continue
        dataset_ledger.assert_blind_allowed(m, DATASET, ledger)


def _report(plan_meta, observed, scen, numerics, synthetic):
    body = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan': plan_meta,
            'synthetic_dry_run': synthetic, 'dataset': DATASET, 'excluded_endpoints': list(EXCLUDED),
            'numerics': numerics, 'results': _compare(observed, scen), 'model_values': scen,
            'not_validation': 'Exploratory external consistency check; no model is validated or qualified.'}
    raw = json.dumps(body, sort_keys=True, allow_nan=False).encode()
    body['report_sha256'] = hashlib.sha256(raw).hexdigest()
    return body


def run_check():
    plan = load_plan()
    check_blind_allowed()
    observed = load_observed()
    scen, numerics = model_scenarios()
    return _report({'path': str(PLAN_PATH.name), 'sha256': PLAN_SHA256, 'version': plan['plan_version']},
                   observed, scen, numerics, synthetic=False)


def synthetic_observed(seed_values=None):
    """Made-up observed values in the observed file's shape, for the dry run only. Not derived from the record."""
    v = seed_values or {'auc_last_day11': (150.0, 60.0), 'cmax_day11': (200.0, 90.0), 'cl_day11': (15.0, 8.0),
                        'vss_day11': (900.0, 500.0), 'half_life_day11': (60.0, 30.0), 'cmax_day1': (100.0, 50.0),
                        'auc_last_day1': (60.0, 30.0), 'vss_day1': (1500.0, 900.0)}
    return {'synthetic': True, 'endpoints': {k: {'mean': m, 'sd': s, 'n': N} for k, (m, s) in v.items()}}


def dry_run(plan, iwasaki_step_h=IWASAKI_STEP_H):
    """Same comparison code on synthetic observed values, with the plan object passed in (not the pinned file)."""
    scen, numerics = model_scenarios(iwasaki_step_h)
    return _report({'version': plan['plan_version'], 'status': plan['status']}, synthetic_observed(), scen,
                   numerics, synthetic=True)


def register_bortezomib_pk_nct01801436_commands(app):
    @app.cli.command('bortezomib-pk-nct01801436-check')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(output):
        """Run the locked NCT01801436 blind check (Simulation 3.0n). Exploratory; not validation."""
        try:
            report = run_check()
        except (ValueError, OSError, KeyError, dataset_ledger.LedgerError) as exc:
            raise click.ClickException(str(exc)) from exc
        payload = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
        if output:
            with output.open('x', encoding='utf-8') as handle:
                handle.write(payload)
            click.echo(f'Saved report: {output}\nReport SHA256: {report["report_sha256"]}')
        else:
            click.echo(payload, nl=False)
