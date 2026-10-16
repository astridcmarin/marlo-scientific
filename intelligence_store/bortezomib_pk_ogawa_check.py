"""Simulation 3.0f: external consistency check of the bortezomib PK component against Ogawa 2008.

Ogawa et al. sampled plasma for only 48 h after each dose and reported non-compartmental (NCA) summaries.
The model's terminal half-life is about 98 h, so its true AUC to infinity is not what such a study measures.
The fair comparison is to sample the model at the same times and run the same kind of NCA on it, then compare
those emulated values with the reported means. The plan was locked before any of this was computed
(intelligence_store/data/bortezomib_pk_ogawa_check_plan_v1.json); nothing here tunes the model.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

import click

from .bortezomib_pk import concentration_ng_ml, disposition_rates, rate_constants, unit_bolus_coefficients
from .bortezomib_platelet_evidence import EXTRACT_SHA256, load_model_extract
from .patient_state import digest

DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'bortezomib_pk_ogawa_check_plan_v1.json'
PLAN_SHA256 = 'cfabbe78e6982269ce0d4a9317a3d216c1e1299abb93cf081dd5a66f32a08469'
OBSERVED_PATH = DATA / 'bortezomib_pk_ogawa_2008_observed_v1.json'
OBSERVED_SHA256 = 'cf1bff435354dbbb6864414fac81effadea35ed1ac3d90b7b53f64d67d8bea13'
REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'bortezomib_pk_ogawa_check_v1.json'
SCHEMA_VERSION = 'bortezomib-pk-external-check-report-v1'
METHOD_VERSION = 'bortezomib-pk-ogawa-check-v1.0'
DOSE_TIMES_H = (0.0, 72.0, 168.0, 240.0)
DAY11_START_H = 240.0
DOSE_LEVELS = ('0.7', '1.0', '1.3')
# Two-sided 95% Student t quantiles t(0.975, df) from standard tables; checked against scipy in the tests.
T975 = {1: 12.7062, 2: 4.3027, 3: 3.1824, 4: 2.7764, 5: 2.5706, 6: 2.4469, 7: 2.3646, 8: 2.3060, 9: 2.2622}


def _load(path, expected, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'{label} is missing or changed; no check was run.')
    return json.loads(raw)


def load_plan(path=PLAN_PATH):
    return _load(path, PLAN_SHA256, 'Analysis plan')


def load_observed(path=OBSERVED_PATH):
    return _load(path, OBSERVED_SHA256, 'Ogawa 2008 observed values')


def nca(times_h, conc, auc_rule, terminal_points):
    """NCA of an IV bolus profile sampled after the dose; times exclude the dose time itself.

    C0: log-linear back-extrapolation from the first two samples. AUC: trapezoids from (0, C0) to the last
    sample, either all linear or linear while rising and log while falling. Terminal rate: least-squares slope
    of ln C over the last `terminal_points` samples; AUC to infinity adds C_last / rate.
    """
    if len(times_h) != len(conc) or len(times_h) < max(3, terminal_points):
        raise ValueError('Profile too short for NCA.')
    if any(c <= 0 for c in conc):
        raise ValueError('NCA needs positive concentrations.')
    t1, t2, c1, c2 = times_h[0], times_h[1], conc[0], conc[1]
    c0 = math.exp(math.log(c1) - (math.log(c2) - math.log(c1)) / (t2 - t1) * t1)
    t = [0.0] + list(times_h)
    c = [c0] + list(conc)
    auc = 0.0
    for i in range(1, len(t)):
        dt, a, b = t[i] - t[i - 1], c[i - 1], c[i]
        if auc_rule == 'linear_up_log_down' and b < a:
            auc += dt * (a - b) / math.log(a / b)
        elif auc_rule in ('linear', 'linear_up_log_down'):
            auc += dt * (a + b) / 2.0
        else:
            raise ValueError('Unknown AUC rule.')
    xs, ys = times_h[-terminal_points:], [math.log(v) for v in conc[-terminal_points:]]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    lam = -slope
    if lam <= 0:
        raise ValueError('Terminal phase is not declining.')
    return {'c0_ng_ml': c0, 'auc_to_last_ng_h_ml': auc, 'terminal_rate_per_h': lam,
            'auc_ng_h_ml': auc + conc[-1] / lam, 'half_life_h': math.log(2) / lam}


def _ci(mean, sd, n):
    half = T975[n - 1] * sd / math.sqrt(n)
    return [mean - half, mean + half]


def _classify(value, interval):
    return ('consistent' if interval[0] <= value <= interval[1]
            else 'model_over_predicts' if value > interval[1] else 'model_under_predicts')


def model_profiles(dose_mg_m2, sampling_times_h, extract=None):
    terms = unit_bolus_coefficients(rate_constants(extract))
    events = [(t, dose_mg_m2) for t in DOSE_TIMES_H]
    day1 = [concentration_ng_ml(s, events[:1] if s < 72.0 else [e for e in events if e[0] <= s], terms)
            for s in sampling_times_h]
    day11 = [concentration_ng_ml(DAY11_START_H + s, events, terms) for s in sampling_times_h]
    return {'day1_ng_ml': day1, 'day11_ng_ml': day11}


def true_model_exposure(dose_mg_m2, extract=None):
    """Context only: the model's own AUC to infinity, without the 48 h sampling window."""
    k = rate_constants(extract)
    single = 1000.0 * dose_mg_m2 / k['cl_l_h_m2']
    terms = unit_bolus_coefficients(k)
    # Drug present from t = 240 h onward from all four doses, integrated to infinity in closed form.
    events = [(t, dose_mg_m2) for t in DOSE_TIMES_H]
    after = 1000.0 * math.fsum(d * c * math.exp(-lam * (DAY11_START_H - s)) / lam for s, d in events for c, lam in terms)
    return {'auc_single_dose_to_infinity_ng_h_ml': single, 'auc_from_day11_dose_to_infinity_ng_h_ml': after,
            'terminal_half_life_h': math.log(2) / min(disposition_rates(k))}


def run_check():
    plan = load_plan()
    observed = load_observed()
    extract = load_model_extract()
    times = observed['design']['sampling_times_h']
    readings = [dict(plan['nca_emulation']['readings']['primary'], role='primary')] + [
        dict(r, role='sensitivity') for r in plan['nca_emulation']['readings']['sensitivity']]
    rows = []
    for dose_key in DOSE_LEVELS:
        obs = observed['table3']['dose_levels'][dose_key]
        dose = float(dose_key)
        prof = model_profiles(dose, times, extract)
        n1, n11 = obs['n_day1'], obs['n_day11']
        targets = {
            'auc_day1': (obs['AUC_ng_h_ml']['day1'], n1), 'auc_day11': (obs['AUC_ng_h_ml']['day11'], n11),
            'auc_ratio_day11_over_day1': (obs['AUC_ratio_day11_over_day1'], n11),
            'c0_day1': (obs['C0_ng_ml']['day1'], n1), 'c0_day11': (obs['C0_ng_ml']['day11'], n11),
            'half_life_day1': (obs['half_life_h']['day1'], n1), 'half_life_day11': (obs['half_life_h']['day11'], n11)}
        by_reading = []
        for r in readings:
            d1 = nca(times, prof['day1_ng_ml'], r['auc_rule'], r['terminal_points'])
            d11 = nca(times, prof['day11_ng_ml'], r['auc_rule'], r['terminal_points'])
            values = {'auc_day1': d1['auc_ng_h_ml'], 'auc_day11': d11['auc_ng_h_ml'],
                      'auc_ratio_day11_over_day1': d11['auc_ng_h_ml'] / d1['auc_ng_h_ml'],
                      'c0_day1': d1['c0_ng_ml'], 'c0_day11': d11['c0_ng_ml'],
                      'half_life_day1': d1['half_life_h'], 'half_life_day11': d11['half_life_h']}
            endpoints = {}
            for name, ((mean, sd), n) in targets.items():
                interval = _ci(mean, sd, n)
                endpoints[name] = {'model_emulated': values[name], 'observed_mean': mean, 'observed_sd': sd, 'n': n,
                                   'interval_95': interval, 'ratio_model_to_observed': values[name] / mean,
                                   'classification': (None if name.startswith('half_life') else _classify(values[name], interval))}
            by_reading.append({'auc_rule': r['auc_rule'], 'terminal_points': r['terminal_points'], 'role': r['role'],
                               'endpoints': endpoints})
        primary = by_reading[0]['endpoints']
        classified = [k for k in primary if primary[k]['classification'] is not None]
        robust = {k: len({br['endpoints'][k]['classification'] for br in by_reading}) == 1 for k in classified}
        primary_names = ('auc_day1', 'auc_day11', 'auc_ratio_day11_over_day1')
        rows.append({'dose_mg_m2': dose, 'readings': by_reading, 'robust_across_readings': robust,
                     'primary_endpoints_consistent': all(primary[k]['classification'] == 'consistent' for k in primary_names),
                     'primary_endpoint_role': 'primary' if dose_key == '1.3' else 'secondary',
                     'model_without_emulation': true_model_exposure(dose, extract)})
    lead = next(r for r in rows if r['dose_mg_m2'] == 1.3)
    findings = [f"{k}: {lead['readings'][0]['endpoints'][k]['classification'].replace('_', ' ')} "
                f"(model {lead['readings'][0]['endpoints'][k]['model_emulated']:.3g} vs observed "
                f"{lead['readings'][0]['endpoints'][k]['observed_mean']:.3g})"
                for k in ('auc_day1', 'auc_day11', 'auc_ratio_day11_over_day1')
                if lead['readings'][0]['endpoints'][k]['classification'] != 'consistent']
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'observed_sha256': OBSERVED_SHA256, 'model_extract_sha256': EXTRACT_SHA256,
              'classification': plan['classification'], 'sampling_times_h': times, 'rows': rows,
              'decision': {'externally_consistent_at_1_3_mg_m2': lead['primary_endpoints_consistent'],
                           'findings_at_1_3_mg_m2': findings,
                           'rule': plan['decision_rule']['summary']},
              'not_this': copy.deepcopy(plan['not_this']), 'known_differences': copy.deepcopy(plan['known_differences']),
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_bortezomib_pk_ogawa_commands(app):
    @app.cli.command('bortezomib-pk-ogawa-check')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(output):
        """Run the locked Ogawa 2008 PK check. Exploratory external consistency only; not validation."""
        try:
            report = run_check()
        except (ValueError, OSError, KeyError) as exc:
            raise click.ClickException(str(exc)) from exc
        payload = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
        if output:
            with output.open('x', encoding='utf-8') as handle:
                handle.write(payload)
            click.echo(f'Saved report: {output}\nReport SHA256: {report["report_sha256"]}')
        else:
            click.echo(payload, nl=False)
