"""Simulation 2.0c: end-stage renal disease and haemodialysis, against the 2.0a elimination-pathway model.

Primary question: with kidney elimination nearly gone, does the non-renal clearance calibrated on the normal group
(held constant in 2.0a and 2.0b) predict ESRD exposure on a non-dialysis day? Descriptive: the non-renal clearance
each group's own data imply, and how much of a dose one 4-hour haemodialysis session removed, from the same six
subjects' paired profiles. The plan (lenalidomide_esrd_dialysis_plan_v1.json) was locked before computation.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

import click

from .lenalidomide_renal_pathways import calibrate, load_evidence as load_pathway_evidence
from .patient_state import digest

DATA = Path(__file__).parent / 'data'
EVIDENCE_PATH = DATA / 'lenalidomide_esrd_dialysis_evidence_v1.json'
EVIDENCE_SHA256 = '7769bba1cad79392919ba02a36a24617cf2aa7bec2cfebdb2f6bc5d935c1d2b6'
PLAN_PATH = DATA / 'lenalidomide_esrd_dialysis_plan_v1.json'
PLAN_SHA256 = 'fd75e3e96bf6cd5a6de185e11fcd055bf85c378785a55396d01cc1690b231d3b'
REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'lenalidomide_esrd_dialysis_check_v1.json'
SCHEMA_VERSION = 'lenalidomide-esrd-dialysis-check-report-v1'
METHOD_VERSION = 'lenalidomide-esrd-dialysis-v1.0'
T975_DF5 = 2.5706
CAL_CRCL, CAL_FU = 110.0, 0.77


def _load(path, expected, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'{label} is missing or changed; nothing was computed.')
    return json.loads(raw)


def load_evidence(path=EVIDENCE_PATH):
    return _load(path, EVIDENCE_SHA256, 'ESRD and dialysis evidence')


def load_plan(path=PLAN_PATH):
    return _load(path, PLAN_SHA256, 'ESRD and dialysis plan')


def _cl_ml_min(dose_mg, auc):
    return dose_mg * 1e6 / auc / 60.0


def predicted_auc(cal, residual_crcl, dose_mg):
    """Intact-nephron renal clearance at the residual creatinine clearance (zero allowed) plus constant non-renal."""
    if not (math.isfinite(residual_crcl) and residual_crcl >= 0):
        raise ValueError('Residual creatinine clearance must be finite and not negative.')
    renal = cal['renal_ml_min'] * residual_crcl / cal['crcl_ml_min']
    total = renal + cal['non_renal_ml_min']
    return {'residual_crcl_ml_min': residual_crcl, 'renal_ml_min': renal, 'non_renal_ml_min': cal['non_renal_ml_min'],
            'total_ml_min': total, 'auc_ng_h_ml': dose_mg * 1e6 / (total * 60.0)}


def run_check():
    plan = load_plan()
    esrd = load_evidence()
    pathway_evidence = load_pathway_evidence()
    dose = esrd['study']['dose_mg']
    cal = calibrate(pathway_evidence, CAL_CRCL, CAL_FU)
    off = next(g for g in esrd['groups'] if g['group'] == 'esrd_off_dialysis')
    on = next(g for g in esrd['groups'] if g['group'] == 'esrd_on_dialysis')
    mean, sd = off['auc_ng_h_ml']
    half = T975_DF5 * sd / math.sqrt(off['n'])
    interval = [mean - half, mean + half]
    rows = []
    for crcl in plan['primary_prediction']['residual_creatinine_clearance_scenarios_ml_min']:
        p = predicted_auc(cal, float(crcl), dose)
        p.update(ratio_to_observed=p['auc_ng_h_ml'] / mean,
                 classification=('consistent' if interval[0] <= p['auc_ng_h_ml'] <= interval[1] else
                                 'model_over_predicts' if p['auc_ng_h_ml'] > interval[1] else 'model_under_predicts'))
        rows.append(p)
    observed_total_off = _cl_ml_min(dose, mean)
    non_renal_by_group = []
    for g in pathway_evidence['groups']:
        cl = _cl_ml_min(dose, g['auc_ng_h_ml'][0])
        non_renal_by_group.append({'group': g['group'], 'total_ml_min': cl, 'fe': g['fe_percent'] / 100.0,
                                   'renal_ml_min': cl * g['fe_percent'] / 100.0,
                                   'non_renal_ml_min': cl * (1 - g['fe_percent'] / 100.0)})
    non_renal_by_group.append({'group': 'esrd_off_dialysis', 'total_ml_min': observed_total_off, 'fe': None,
                               'renal_ml_min': None, 'non_renal_ml_min': None,
                               'note': 'Fraction excreted not reported; total clearance is an upper bound on non-renal clearance.'})
    own_routes_mg = observed_total_off * 60.0 * on['auc_ng_h_ml'][0] / 1e6
    removed_mg = dose - own_routes_mg
    dialysis = {'cl_off_ml_min': observed_total_off, 'auc_on_ng_h_ml': on['auc_ng_h_ml'][0],
                'eliminated_by_own_routes_mg': own_routes_mg, 'removed_by_dialysis_mg': removed_mg,
                'removed_fraction_of_dose': removed_mg / dose,
                'auc_ratio_on_over_off': on['auc_ng_h_ml'][0] / mean,
                'assumption': plan['descriptive_methods']['dialysis_removal']}
    over_all = all(r['classification'] == 'model_over_predicts' for r in rows)
    consistent_at_zero = rows[0]['classification'] == 'consistent'
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'evidence_sha256': EVIDENCE_SHA256, 'classification': plan['classification'],
              'calibration': {k: cal[k] for k in ('crcl_ml_min', 'fu', 'total_ml_min', 'renal_ml_min', 'non_renal_ml_min')},
              'primary': {'observed_auc_mean': mean, 'observed_auc_sd': sd, 'n': off['n'], 'interval_95': interval,
                          'scenarios': rows},
              'descriptive': {'non_renal_by_group': non_renal_by_group, 'dialysis': dialysis},
              'decision': {'constant_non_renal_consistent_at_zero_residual': consistent_at_zero,
                           'finding_esrd_elimination_exceeds_normal_non_renal': over_all},
              'not_this': copy.deepcopy(plan['not_this']), 'known_differences': copy.deepcopy(plan['known_differences']),
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_esrd_dialysis_commands(app):
    @app.cli.command('lenalidomide-esrd-dialysis-check')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(output):
        """Run the locked ESRD and dialysis check (Simulation 2.0c). Exploratory; not validation."""
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
