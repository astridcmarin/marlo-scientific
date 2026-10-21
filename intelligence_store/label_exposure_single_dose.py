"""Phase 3.1f: label-based oral exposure from single-dose label values, and the dexamethasone (HEMADY) consistency check.

Uses the oral one-compartment functions of label_exposure.py (pomalidomide), applied to one dose. The rules are fixed
in label_exposure_consistency_plan_dexamethasone_v1.json, locked before this module was written. The HEMADY label
reports single-dose values in 'subjects' without saying whether they were patients; every output carries that note.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

import click

from . import label_exposure as le
from .patient_state import digest

DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'label_exposure_consistency_plan_dexamethasone_v1.json'
PLAN_SHA256 = 'a2016bac0589b65d3268523d41efce2896cc51888920e7060f929ffa5c0745c8'
LABEL_PATH = DATA / 'label_pk_dexamethasone_hemady_v1.json'
LABEL_SHA256 = 'f764633f39576fd65ebc7b0a3cc3e22ddb362756b3c9c0838434cb0dab28605c'
REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'label_exposure_dexamethasone_consistency_v1.json'
SCHEMA_VERSION = 'label-exposure-consistency-report-v1'
METHOD_VERSION = 'label-exposure-single-dose-v1.0'
TOLERANCE = (0.67, 1.5)
PASS_FAIL = ('C1_clearance_vs_exposure', 'C2_half_life', 'C3_single_dose_cmax', 'C4_single_dose_auc')
HORIZON_H = 48.0
POPULATION_NOTE = "Single-dose values from 'subjects'; the label does not say whether they had multiple myeloma."


def _load(path, expected, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'{label} is missing or changed; nothing was run.')
    return json.loads(raw)


def load_plan(path=PLAN_PATH):
    return _load(path, PLAN_SHA256, 'Dexamethasone consistency plan')


def load_label(path=LABEL_PATH):
    return _load(path, LABEL_SHA256, 'Dexamethasone label extract')


def single_dose_summary(dose_mg, cl, v, ka):
    n = int(round(HORIZON_H / le.GRID_H))
    conc = [le.single_dose_ng_ml(i * le.GRID_H, dose_mg, cl, v, ka) for i in range(n + 1)]
    i_max = max(range(n + 1), key=conc.__getitem__)
    k = cl / v
    auc = le.GRID_H * (sum(conc) - (conc[0] + conc[-1]) / 2) + conc[-1] / k
    return {'cmax_ng_ml': conc[i_max], 'tmax_h_grid': i_max * le.GRID_H, 'tmax_h_exact': math.log(ka / k) / (ka - k),
            'auc_inf_ng_h_ml_numerical': auc, 'auc_inf_ng_h_ml_exact': 1000.0 * dose_mg / cl,
            'remaining_fraction_at_24_h': math.exp(-k * 24.0)}


def parameter_set(label):
    v = label['values']
    cl = v['cl_f_l_h']['value']
    return {'cl_f_l_h': cl, 'v_f_l': cl * v['half_life_h']['value'] / math.log(2),
            'provenance': {'cl_f_l_h': 'stated oral clearance after a single dose, 15.7 L/h',
                           'v_f_l': 'CL/F x 4 h / ln 2 (mean terminal half-life); the label states no volume'}}


def _ratio(model, label_value):
    r = model / label_value
    return {'model': model, 'label': label_value, 'ratio': r, 'result': 'pass' if TOLERANCE[0] <= r <= TOLERANCE[1] else 'fail'}


def check(p, label, tmax_for_ka):
    v = label['values']
    dose = label['regimen']['dose_mg']
    k = p['cl_f_l_h'] / p['v_f_l']
    ka = le.ka_from_tmax(tmax_for_ka, k)
    s = single_dose_summary(dose, p['cl_f_l_h'], p['v_f_l'], ka)
    checks = {'C1_clearance_vs_exposure': _ratio(p['cl_f_l_h'], 1000.0 * dose / v['auc_inf_single_20mg_ng_h_ml']['value']),
              'C2_half_life': _ratio(math.log(2) / k, v['half_life_h']['value']),
              'C3_single_dose_cmax': _ratio(s['cmax_ng_ml'], v['cmax_single_20mg_ng_ml']['value']),
              'C4_single_dose_auc': _ratio(s['auc_inf_ng_h_ml_numerical'], v['auc_inf_single_20mg_ng_h_ml']['value']),
              'C6_tmax': {'model': s['tmax_h_grid'], 'label': v['tmax_h']['value'], 'result': None}}
    return {'tmax_used_for_ka_h': tmax_for_ka, 'ka_per_h': ka, 'k_per_h': k, 'summary': s, 'checks': checks,
            'passes_c1_to_c4': all(checks[c]['result'] == 'pass' for c in PASS_FAIL)}


def run_check():
    plan = load_plan()
    label = load_label()
    p = parameter_set(label)
    primary = check(p, label, label['values']['tmax_h']['value'])
    lo, hi = label['values']['tmax_h']['range']
    sensitivity = [{'tmax_used_for_ka_h': s['tmax_used_for_ka_h'], 'ka_per_h': s['ka_per_h'],
                    'cmax_ng_ml': s['summary']['cmax_ng_ml'], 'cmax_ratio': s['checks']['C3_single_dose_cmax']['ratio'],
                    'cmax_result': s['checks']['C3_single_dose_cmax']['result']} for s in (check(p, label, lo), check(p, label, hi))]
    s = primary['summary']
    numerical = {'auc_numerical_vs_exact_relative_difference': abs(s['auc_inf_ng_h_ml_numerical'] - s['auc_inf_ng_h_ml_exact']) / s['auc_inf_ng_h_ml_exact'],
                 'tmax_grid_vs_exact_difference_h': abs(s['tmax_h_grid'] - s['tmax_h_exact'])}
    numerical['passed'] = numerical['auc_numerical_vs_exact_relative_difference'] < 1e-6 and numerical['tmax_grid_vs_exact_difference_h'] <= le.GRID_H
    eligible = primary['passes_c1_to_c4']
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'label_extract_sha256': LABEL_SHA256,
              'label_source': {k: label['source'][k] for k in ('dailymed_set_id', 'revised', 'file_reviewed')},
              'drug': 'dexamethasone', 'population_note': POPULATION_NOTE,
              'regimen': {'dose_mg': label['regimen']['dose_mg'], 'evaluated_as': 'single oral dose'},
              'tolerance': list(TOLERANCE), 'which_checks_are_informative': plan['checks']['which_checks_are_informative'],
              'numerical_checks': numerical,
              'parameter_set': {'id': 'A_stated_label', 'cl_f_l_h': p['cl_f_l_h'], 'v_f_l': p['v_f_l'], 'provenance': p['provenance'],
                                'primary': primary, 'tmax_sensitivity': sensitivity},
              'decision': {'selected_set': 'A_stated_label' if eligible else None, 'eligible': eligible,
                           'rule': plan['decision_rule']['selection']},
              'not_this': copy.deepcopy(plan['not_this']), 'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_label_exposure_single_dose_commands(app):
    @app.cli.command('label-exposure-dexamethasone-consistency')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(output):
        """Check the label-based dexamethasone curve against its own label (Phase 3.1f). Not validation."""
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
