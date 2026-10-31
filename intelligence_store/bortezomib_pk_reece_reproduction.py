"""Simulation 3.0n: reproduction check of the bortezomib PK component against Reece 2011.

Lignet 2022 compared its PK graphically with mean profiles from Reece et al. 2011. This module samples the unchanged
model at the Reece times on days 1 and 11 of cycles 1 and 3 at 1.0 and 1.3 mg/m2, emulates AUC48h and Cmax, and
classifies them exactly as fixed in bortezomib_pk_reece_reproduction_plan_v1.json (locked at commit 1c3591f, before
computation). No parameter is estimated or tuned. This is a reproduction check, not an outside check.
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
PLAN_PATH = DATA / 'bortezomib_pk_reece_reproduction_plan_v1.json'
PLAN_SHA256 = '5aef94884fe3dc65e417e897ca798447587fb69465eca054949bbdcb2128d8be'
OBSERVED_PATH = DATA / 'bortezomib_pk_reece_2011_observed_v1.json'
OBSERVED_SHA256 = '83f6ee4cb444ce049ab004131e04283b317cf536c8de6ab07411d180c01a3c7e'
REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'bortezomib_pk_reece_reproduction_v1.json'
SCHEMA_VERSION = 'bortezomib-pk-reproduction-report-v1'
METHOD_VERSION = 'bortezomib-pk-reece-reproduction-v1.0'
CYCLE_H = 504.0
DAYS_H = (0.0, 72.0, 168.0, 240.0)
OCCASIONS = {'c1d1': 0.0, 'c1d11': 240.0, 'c3d1': 2 * CYCLE_H, 'c3d11': 2 * CYCLE_H + 240.0}
T975 = {9: 2.3060, 11: 2.2281, 12: 2.2010}
PRIMARY = ('auc48_c1d1_1.3', 'auc48_c1d11_1.3')


def _load(path, expected, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'{label} is missing or changed; no check was run.')
    return json.loads(raw)


def load_plan(path=PLAN_PATH):
    return _load(path, PLAN_SHA256, 'Reece reproduction plan')


def load_observed(path=OBSERVED_PATH):
    return _load(path, OBSERVED_SHA256, 'Reece observed values')


def profile(dose_mg_m2, start_h, sampling_times_h, extract=None):
    """Concentrations after the dose at start_h; doses on days 1, 4, 8, 11 of cycles 1-3 strictly before each time count."""
    terms = unit_bolus_coefficients(rate_constants(extract))
    events = [(c * CYCLE_H + d, dose_mg_m2) for c in range(3) for d in DAYS_H]
    return [concentration_ng_ml(start_h + s, [e for e in events if e[0] < start_h + s], terms) for s in sampling_times_h]


def _interval(mean, sd, n):
    half = T975[n] * sd / math.sqrt(n)
    return [mean - half, mean + half]


def run_check():
    plan = load_plan()
    observed = load_observed()
    extract = load_model_extract()
    if plan['data']['observed_sha256'] != OBSERVED_SHA256:
        raise ValueError('Plan and observed file disagree.')
    times = observed['design']['pk_sampling_times_after_dose_h']
    t2 = observed['table2']
    readings = [dict(plan['nca_emulation']['readings']['primary'], role='primary')] + [
        dict(r, role='sensitivity') for r in plan['nca_emulation']['readings']['sensitivity']]
    profiles = {f'{occ}_{dose}': profile(float(dose), start, times, extract) for dose in ('1.0', '1.3') for occ, start in OCCASIONS.items()}
    by_reading = []
    for r in readings:
        endpoints = {}
        for dose in ('1.0', '1.3'):
            for occ in OCCASIONS:
                prof = profiles[f'{occ}_{dose}']
                res = nca(times, prof, r['auc_rule'], r['terminal_points'])
                for metric, value in (('auc48', res['auc_to_last_ng_h_ml']), ('cmax', max(prof))):
                    mean, sd, n = t2[dose][occ][metric]
                    interval = _interval(mean, sd, n)
                    endpoints[f'{metric}_{occ}_{dose}'] = {'model_emulated': value, 'observed_mean': mean, 'observed_sd': sd, 'n': n,
                                                          'interval_95': interval, 'ratio_model_to_observed': value / mean,
                                                          'classification': _classify(value, interval)}
            endpoints[f'ratio_auc48_c1d11_over_c1d1_{dose}'] = {
                'model_emulated': endpoints[f'auc48_c1d11_{dose}']['model_emulated'] / endpoints[f'auc48_c1d1_{dose}']['model_emulated'],
                'observed': t2[dose]['c1d11']['auc48'][0] / t2[dose]['c1d1']['auc48'][0], 'classification': None}
        by_reading.append({'auc_rule': r['auc_rule'], 'terminal_points': r['terminal_points'], 'role': r['role'], 'endpoints': endpoints})
    primary = by_reading[0]['endpoints']
    classified = [k for k in primary if primary[k]['classification'] is not None]
    robust = {k: sorted({br['endpoints'][k]['classification'] for br in by_reading}) for k in classified}
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'plan_locked_at_commit': '1c3591f', 'observed_sha256': OBSERVED_SHA256,
              'model_extract_sha256': EXTRACT_SHA256, 'classification': plan['classification'], 'sampling_times_h': times,
              'model_profiles_ng_ml': profiles, 'readings': by_reading, 'classifications_across_readings': robust,
              'decision': {'reproduces_reece_at_1_3': all(primary[k]['classification'] == 'consistent' for k in PRIMARY),
                           'result': {k: primary[k]['classification'] for k in PRIMARY},
                           'robust_primary': all(len(robust[k]) == 1 for k in PRIMARY), 'rule': plan['decision_rule']['summary']},
              'not_this': copy.deepcopy(plan['not_this']), 'known_differences': copy.deepcopy(plan['known_differences']),
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_bortezomib_pk_reece_commands(app):
    @app.cli.command('bortezomib-pk-reece-reproduction')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(output):
        """Run the locked Reece 2011 reproduction check of the bortezomib PK component (Simulation 3.0n)."""
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
