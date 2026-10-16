"""Simulation 2.0a: lenalidomide elimination split into filtration, tubular secretion and non-renal pathways.

Lenalidomide leaves the body mainly unchanged in urine (85% of a dose with normal renal function), and its renal
clearance exceeds what filtration of unbound drug alone could achieve, so the tubules also secrete it. This module
calibrates the three pathways on the normal-renal-function group of study CC-5013-PK-001 only, then predicts the
impaired groups under two readings of how secretion changes as kidney function falls:

  A, intact nephron: filtration and secretion both fall in proportion to creatinine clearance;
  B, secretion preserved: filtration falls with creatinine clearance, secretion stays at its normal value.

The plan (lenalidomide_renal_pathways_plan_v1.json) was locked before any of this was computed. No parameter is
fitted to the impaired groups.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

import click

from .patient_state import digest

DATA = Path(__file__).parent / 'data'
EVIDENCE_PATH = DATA / 'lenalidomide_renal_pathways_evidence_v1.json'
EVIDENCE_SHA256 = 'e7c62bc477bfc6170f42f1f01e5935ea222bec0fbf513da718178030c42d2c8f'
PLAN_PATH = DATA / 'lenalidomide_renal_pathways_plan_v1.json'
PLAN_SHA256 = '591e032c7bf96f80b8bcae217a171b258923875bdfd7a37cd81baa86939f194a'
REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'lenalidomide_renal_pathways_check_v1.json'
SCHEMA_VERSION = 'lenalidomide-renal-pathways-check-report-v1'
METHOD_VERSION = 'lenalidomide-renal-pathways-v1.0'
IMPAIRED = ('mild', 'moderate', 'severe_without_dialysis')
READINGS = ('A_intact_nephron', 'B_secretion_preserved')
T975 = {4: 2.7764, 5: 2.5706, 6: 2.4469}


def _load(path, expected, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'{label} is missing or changed; nothing was computed.')
    return json.loads(raw)


def load_evidence(path=EVIDENCE_PATH):
    return _load(path, EVIDENCE_SHA256, 'Renal pathway evidence')


def load_plan(path=PLAN_PATH):
    return _load(path, PLAN_SHA256, 'Renal pathway plan')


def _ml_min(dose_mg, auc_ng_h_ml):
    return dose_mg * 1e6 / auc_ng_h_ml / 60.0


def calibrate(evidence, crcl_normal, fu):
    """Pathway clearances (mL/min) for the normal group, from its mean AUC and mean fraction excreted unchanged."""
    dose = evidence['study']['dose_mg']
    normal = next(g for g in evidence['groups'] if g['group'] == 'normal')
    cl = _ml_min(dose, normal['auc_ng_h_ml'][0])
    clr = normal['fe_percent'] / 100.0 * cl
    filtration = fu * crcl_normal
    return {'crcl_ml_min': crcl_normal, 'fu': fu, 'total_ml_min': cl, 'renal_ml_min': clr,
            'non_renal_ml_min': cl - clr, 'filtration_ml_min': filtration, 'secretion_ml_min': clr - filtration}


def pathways(cal, crcl, reading):
    """Clearance pathways (mL/min) at a given creatinine clearance under one reading."""
    if not (math.isfinite(crcl) and crcl > 0):
        raise ValueError('Creatinine clearance must be a finite positive number.')
    scale = crcl / cal['crcl_ml_min']
    filtration = cal['fu'] * crcl
    if reading == 'A_intact_nephron':
        secretion = cal['secretion_ml_min'] * scale
    elif reading == 'B_secretion_preserved':
        secretion = cal['secretion_ml_min']
    else:
        raise ValueError('Unknown reading.')
    renal = filtration + secretion
    total = renal + cal['non_renal_ml_min']
    return {'crcl_ml_min': crcl, 'filtration_ml_min': filtration, 'secretion_ml_min': secretion,
            'renal_ml_min': renal, 'non_renal_ml_min': cal['non_renal_ml_min'], 'total_ml_min': total,
            'fe': renal / total}


def _scenarios(plan):
    base = dict(plan['creatinine_clearance_scenarios']['primary'])
    out = [('primary', dict(base, fu=0.77))]
    for s in plan['creatinine_clearance_scenarios']['sensitivity']:
        merged = dict(base, fu=0.77)
        merged.update({k: v for k, v in s.items() if k != 'label'})
        out.append((s['label'], merged))
    return out


def run_check():
    plan = load_plan()
    evidence = load_evidence()
    dose = evidence['study']['dose_mg']
    groups = {g['group']: g for g in evidence['groups']}
    scenarios = []
    for label, s in _scenarios(plan):
        cal = calibrate(evidence, s['normal'], s['fu'])
        rows = []
        for name in IMPAIRED:
            g = groups[name]
            mean, sd = g['auc_ng_h_ml']
            half = T975[g['n'] - 1] * sd / math.sqrt(g['n'])
            interval = [mean - half, mean + half]
            by_reading = {}
            for reading in READINGS:
                p = pathways(cal, s[name], reading)
                auc = dose * 1e6 / (p['total_ml_min'] * 60.0)
                by_reading[reading] = dict(p, auc_ng_h_ml=auc, ratio_to_observed=auc / mean,
                                           classification=('consistent' if interval[0] <= auc <= interval[1] else
                                                           'model_over_predicts' if auc > interval[1] else 'model_under_predicts'),
                                           fe_observed=g['fe_percent'] / 100.0)
            rows.append({'group': name, 'n': g['n'], 'observed_auc_mean': mean, 'observed_auc_sd': sd,
                         'interval_95': interval, 'readings': by_reading})
        scenarios.append({'label': label, 'settings': s, 'calibration': cal,
                          'secretion_positive': cal['secretion_ml_min'] > 0, 'groups': rows})
    primary = scenarios[0]
    supported = [r for r in READINGS if all(g['readings'][r]['classification'] == 'consistent' for g in primary['groups'])]
    steeper = any(g['readings']['A_intact_nephron']['classification'] == 'model_under_predicts'
                  for g in primary['groups'] if g['group'] in ('moderate', 'severe_without_dialysis'))
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'evidence_sha256': EVIDENCE_SHA256, 'classification': plan['classification'],
              'scenarios': scenarios,
              'decision': {'supported_readings_primary': supported,
                           'finding_renal_elimination_falls_faster_than_proportional': steeper,
                           'classification_by_scenario': {s['label']: {g['group']: {r: g['readings'][r]['classification'] for r in READINGS}
                                                                         for g in s['groups']} for s in scenarios}},
              'not_this': copy.deepcopy(plan['not_this']), 'known_differences': copy.deepcopy(plan['known_differences']),
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_renal_pathway_commands(app):
    @app.cli.command('lenalidomide-renal-pathways-check')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(output):
        """Run the locked renal-pathway check (Simulation 2.0a). Exploratory; not validation."""
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
