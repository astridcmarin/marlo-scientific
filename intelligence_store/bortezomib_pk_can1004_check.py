"""Simulation 3.0h: the constant-clearance bortezomib PK component against a second outside study, CAN-1004.

3.0f compared the model with Ogawa 2008 (Japanese patients, 48 h sampling). CAN-1004 (FDA review of NDA 021602
S-027, Table 7) sampled IV patients for 72 h on day 1 and day 11 at 1.3 mg/m2. This module samples the unchanged
3.0f model at the CAN-1004 times, runs the same non-compartmental emulation, and classifies the results exactly as
fixed in bortezomib_pk_can1004_check_plan_v1.json (locked before computation). No parameter is estimated or tuned.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

import click

from .bortezomib_pk import concentration_ng_ml, rate_constants, unit_bolus_coefficients
from .bortezomib_pk_ogawa_check import T975, _ci, _classify, nca
from .bortezomib_platelet_evidence import EXTRACT_SHA256, load_model_extract
from .patient_state import digest

DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'bortezomib_pk_can1004_check_plan_v1.json'
PLAN_SHA256 = 'aff510dde860101d96ca19e94e6e0f803b7e76f589efc2759273fa379d61ffa7'
OBSERVED_PATH = DATA / 'bortezomib_pk_can1004_observed_v1.json'
OBSERVED_SHA256 = '60b4dbb2bba6a8a56a15080cded7dc33e187d3fa0688a9a0788c6a5b66ab80c4'
REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'bortezomib_pk_can1004_check_v1.json'
SCHEMA_VERSION = 'bortezomib-pk-external-check-report-v1'
METHOD_VERSION = 'bortezomib-pk-can1004-check-v1.0'
DOSE_MG_M2 = 1.3
DOSE_TIMES_H = (0.0, 72.0, 168.0, 240.0)
DAY11_START_H = 240.0
PRIMARY = ('auc_last_day1', 'auc_last_day11')


def _load(path, expected, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'{label} is missing or changed; no check was run.')
    return json.loads(raw)


def load_plan(path=PLAN_PATH):
    return _load(path, PLAN_SHA256, 'CAN-1004 check plan')


def load_observed(path=OBSERVED_PATH):
    return _load(path, OBSERVED_SHA256, 'CAN-1004 observed values')


def model_profiles(sampling_times_h, extract=None):
    """A sample taken at the time of a dose is a pre-dose sample: only doses strictly before it count."""
    terms = unit_bolus_coefficients(rate_constants(extract))
    events = [(t, DOSE_MG_M2) for t in DOSE_TIMES_H]

    def conc(t):
        return concentration_ng_ml(t, [e for e in events if e[0] < t], terms)

    return {'day1_ng_ml': [conc(s) for s in sampling_times_h],
            'day11_ng_ml': [conc(DAY11_START_H + s) for s in sampling_times_h]}


def run_check():
    plan = load_plan()
    observed = load_observed()
    extract = load_model_extract()
    times = observed['design']['pk_sampling_times_after_dose_h']
    iv = observed['table7']['iv']
    n1, n11 = observed['table7']['iv_n']['day1'], observed['table7']['iv_n']['day11']
    prof = model_profiles(times, extract)
    readings = [dict(plan['nca_emulation']['readings']['primary'], role='primary')] + [
        dict(r, role='sensitivity') for r in plan['nca_emulation']['readings']['sensitivity']]
    targets = {'auc_last_day1': (iv['auc_last_ng_h_ml']['day1'], n1), 'auc_last_day11': (iv['auc_last_ng_h_ml']['day11'], n11),
               'auc_inf_day1': (iv['auc_inf_ng_h_ml']['day1'], n1), 'auc_inf_day11': (iv['auc_inf_ng_h_ml']['day11'], n11),
               'c0_day1': (iv['c0_ng_ml']['day1'], n1), 'c0_day11': (iv['c0_ng_ml']['day11'], n11)}
    by_reading = []
    for r in readings:
        d1 = nca(times, prof['day1_ng_ml'], r['auc_rule'], r['terminal_points'])
        d11 = nca(times, prof['day11_ng_ml'], r['auc_rule'], r['terminal_points'])
        values = {'auc_last_day1': d1['auc_to_last_ng_h_ml'], 'auc_last_day11': d11['auc_to_last_ng_h_ml'],
                  'auc_inf_day1': d1['auc_ng_h_ml'], 'auc_inf_day11': d11['auc_ng_h_ml'],
                  'c0_day1': d1['c0_ng_ml'], 'c0_day11': d11['c0_ng_ml']}
        endpoints = {}
        for name, ((mean, sd), n) in targets.items():
            interval = _ci(mean, sd, n)
            endpoints[name] = {'model_emulated': values[name], 'observed_mean': mean, 'observed_sd': sd, 'n': n,
                               'interval_95': interval, 'ratio_model_to_observed': values[name] / mean,
                               'classification': _classify(values[name], interval)}
        endpoints['ratio_of_means_auc_last_day11_over_day1'] = {
            'model_emulated': values['auc_last_day11'] / values['auc_last_day1'],
            'observed': iv['auc_last_ng_h_ml']['day11'][0] / iv['auc_last_ng_h_ml']['day1'][0], 'classification': None}
        endpoints['half_life_day1'] = {'model_emulated': d1['half_life_h'], 'observed_mean': iv['half_life_h']['day1'][0],
                                       'classification': None}
        endpoints['half_life_day11'] = {'model_emulated': d11['half_life_h'], 'observed_mean': iv['half_life_h']['day11'][0],
                                        'classification': None}
        by_reading.append({'auc_rule': r['auc_rule'], 'terminal_points': r['terminal_points'], 'role': r['role'],
                           'endpoints': endpoints})
    primary = by_reading[0]['endpoints']
    classified = [k for k in primary if primary[k]['classification'] is not None]
    robust = {k: sorted({br['endpoints'][k]['classification'] for br in by_reading}) for k in classified}
    day1 = primary['auc_last_day1']['classification']
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'observed_sha256': OBSERVED_SHA256, 'model_extract_sha256': EXTRACT_SHA256,
              'classification': plan['classification'], 'dose_mg_m2': DOSE_MG_M2, 'sampling_times_h': times,
              'model_profiles_ng_ml': prof, 'readings': by_reading,
              'classifications_across_readings': robust,
              'decision': {'consistent_with_can1004': all(primary[k]['classification'] == 'consistent' for k in PRIMARY),
                           'result': {k: primary[k]['classification'] for k in PRIMARY},
                           'ogawa_day1_finding_reproduced': day1 == 'model_over_predicts',
                           'robust_primary': all(len(robust[k]) == 1 for k in PRIMARY),
                           'rule': plan['decision_rule']['summary']},
              'not_this': copy.deepcopy(plan['not_this']), 'known_differences': copy.deepcopy(plan['known_differences']),
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_bortezomib_pk_can1004_commands(app):
    @app.cli.command('bortezomib-pk-can1004-check')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(output):
        """Run the locked CAN-1004 check of the bortezomib PK component (Simulation 3.0h). Exploratory; not validation."""
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
