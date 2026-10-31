"""Simulation 3.0m: the constant-clearance bortezomib PK component against MMY-3021 day 11 exposure.

MMY-3021 (Moreau et al. 2012, PK substudy, IV arm, n = 14) sampled day 11 of cycle 1 for 72 h at 1.3 mg/m2. This
module samples the unchanged model at the MMY-3021 times, runs the same non-compartmental emulation as 3.0f and 3.0h,
and classifies the result exactly as fixed in bortezomib_pk_mmy3021_check_plan_v1.json (locked at commit b921f21,
before computation). No parameter is estimated or tuned.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

import click

from .bortezomib_pk import concentration_ng_ml, rate_constants, unit_bolus_coefficients
from .bortezomib_pk_ogawa_check import _classify, nca
from .bortezomib_platelet_evidence import EXTRACT_SHA256, load_model_extract
from .patient_state import digest

DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'bortezomib_pk_mmy3021_check_plan_v1.json'
PLAN_SHA256 = 'd57359a990e176a6d4b796d455195d22ce7875dabe20b1a8a0aabbb3df08ad02'
OBSERVED_PATH = DATA / 'bortezomib_pk_mmy3021_observed_v1.json'
OBSERVED_SHA256 = '8dadf8ce11d33d32842bdcc61890400f5a8d400b1e41bdadffde0ed2a445d2c9'
REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'bortezomib_pk_mmy3021_check_v1.json'
SCHEMA_VERSION = 'bortezomib-pk-external-check-report-v1'
METHOD_VERSION = 'bortezomib-pk-mmy3021-check-v1.0'
DOSE_MG_M2 = 1.3
DOSE_TIMES_H = (0.0, 72.0, 168.0, 240.0)
DAY11_START_H = 240.0
T975_13 = 2.1604


def _load(path, expected, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'{label} is missing or changed; no check was run.')
    return json.loads(raw)


def load_plan(path=PLAN_PATH):
    return _load(path, PLAN_SHA256, 'MMY-3021 check plan')


def load_observed(path=OBSERVED_PATH):
    return _load(path, OBSERVED_SHA256, 'MMY-3021 observed values')


def day11_profile(sampling_times_h, extract=None):
    terms = unit_bolus_coefficients(rate_constants(extract))
    events = [(t, DOSE_MG_M2) for t in DOSE_TIMES_H]
    return [concentration_ng_ml(DAY11_START_H + s, [e for e in events if e[0] < DAY11_START_H + s], terms)
            for s in sampling_times_h]


def _interval(mean, sd, n):
    if n != 14:
        raise ValueError('The plan fixes t(0.975, 13) for n = 14.')
    half = T975_13 * sd / math.sqrt(n)
    return [mean - half, mean + half]


def run_check():
    plan = load_plan()
    observed = load_observed()
    extract = load_model_extract()
    if plan['data']['observed_sha256'] != OBSERVED_SHA256:
        raise ValueError('Plan and observed file disagree.')
    times = observed['design']['pk_sampling_times_after_dose_h']
    can_times = [t for t in times if t != 32]
    obs = observed['table1_iv_day11']
    n = obs['n']
    readings = [dict(plan['nca_emulation']['readings']['primary'], role='primary')] + [
        dict(r, role='sensitivity') for r in plan['nca_emulation']['readings']['sensitivity']]
    by_reading = []
    for r in readings:
        t = can_times if r.get('schedule') == 'can1004' else times
        prof = day11_profile(t, extract)
        d11 = nca(t, prof, r['auc_rule'], r['terminal_points'])
        values = {'auc_last_day11': d11['auc_to_last_ng_h_ml'], 'cmax_day11': max(prof)}
        targets = {'auc_last_day11': obs['auc_last_ng_h_ml'], 'cmax_day11': obs['cmax_ng_ml']}
        endpoints = {}
        for name, (mean, sd) in targets.items():
            interval = _interval(mean, sd, n)
            endpoints[name] = {'model_emulated': values[name], 'observed_mean': mean, 'observed_sd': sd, 'n': n,
                               'interval_95': interval, 'ratio_model_to_observed': values[name] / mean,
                               'classification': _classify(values[name], interval)}
        by_reading.append({'auc_rule': r['auc_rule'], 'terminal_points': r['terminal_points'],
                           'schedule': r.get('schedule', 'mmy3021'), 'role': r['role'], 'endpoints': endpoints})
    primary = by_reading[0]['endpoints']
    robust = {k: sorted({br['endpoints'][k]['classification'] for br in by_reading}) for k in primary}
    consistent = primary['auc_last_day11']['classification'] == 'consistent'
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'plan_locked_at_commit': 'b921f21', 'observed_sha256': OBSERVED_SHA256,
              'model_extract_sha256': EXTRACT_SHA256, 'classification': plan['classification'], 'dose_mg_m2': DOSE_MG_M2,
              'sampling_times_h': times, 'model_day11_profile_ng_ml': day11_profile(times, extract), 'readings': by_reading,
              'classifications_across_readings': robust,
              'side_by_side': {'ogawa_2008_day11': 'consistent (3.0f)', 'can1004_day11_auc_last': 'model_under_predicts (3.0h; model 127 vs 241)',
                               'mmy3021_day11_auc_last': primary['auc_last_day11']['classification'],
                               'observed_can1004_over_mmy3021_day11_mean': 241 / obs['auc_last_ng_h_ml'][0]},
              'decision': {'consistent_with_mmy3021_day11': consistent,
                           'can1004_day11_finding_reproduced': primary['auc_last_day11']['classification'] == 'model_under_predicts',
                           'robust_primary': len(robust['auc_last_day11']) == 1,
                           'rule': plan['decision_rule']['summary']},
              'not_this': copy.deepcopy(plan['not_this']), 'known_differences': copy.deepcopy(plan['known_differences']),
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_bortezomib_pk_mmy3021_commands(app):
    @app.cli.command('bortezomib-pk-mmy3021-check')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(output):
        """Run the locked MMY-3021 day 11 check of the bortezomib PK component (Simulation 3.0m). Exploratory; not validation."""
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
