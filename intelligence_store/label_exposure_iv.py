"""Phase 3.1f: label-based exposure for an intravenous infusion, and the melphalan (EVOMELA) consistency check.

One compartment, linear, constant-rate infusion of duration T, per m2 of body surface area:
  during the infusion  C(t) = R / CL (1 - e^(-k t)),   R = dose / T,  k = CL / V
  after it             C(t) = C(T) e^(-k (t - T))
Cmax is C(T); AUC from zero to infinity is dose / CL. The rules are fixed in
label_exposure_consistency_plan_melphalan_v1.json, locked before this module was written.
Units: dose in mg/m2, CL in L/h/m2, V in L/m2, concentration in ug/mL (= mg/L), AUC reported in ug.min/mL like the label.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

import click

from .patient_state import digest

DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'label_exposure_consistency_plan_melphalan_v1.json'
PLAN_SHA256 = 'c59e3a523a3211a319388e3a4839f9fce777f6df2d0c8496a16882638f4530f9'
LABEL_PATH = DATA / 'label_pk_melphalan_evomela_v1.json'
LABEL_SHA256 = '0d09f06e1e9d7d9feb887d815074dbd5e1589e449067f32078f1aa8f9dd2d968'
REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'label_exposure_melphalan_consistency_v1.json'
SCHEMA_VERSION = 'label-exposure-consistency-report-v1'
METHOD_VERSION = 'label-exposure-iv-v1.0'
TOLERANCE = (0.67, 1.5)
PASS_FAIL = ('C1_clearance_vs_exposure', 'C2_half_life', 'C3_cmax_end_of_infusion', 'C4_auc_inf')
GRID_H = 0.0005


def _load(path, expected, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'{label} is missing or changed; nothing was run.')
    return json.loads(raw)


def load_plan(path=PLAN_PATH):
    return _load(path, PLAN_SHA256, 'Melphalan consistency plan')


def load_label(path=LABEL_PATH):
    return _load(path, LABEL_SHA256, 'Melphalan label extract')


def infusion_ug_ml(t_h, dose_mg_m2, infusion_h, cl_l_h, v_l):
    """Concentration (mg/L = ug/mL) of one constant-rate infusion starting at t = 0."""
    if t_h <= 0:
        return 0.0
    k = cl_l_h / v_l
    rate = dose_mg_m2 / infusion_h
    if t_h <= infusion_h:
        return rate / cl_l_h * (1 - math.exp(-k * t_h))
    return rate / cl_l_h * (1 - math.exp(-k * infusion_h)) * math.exp(-k * (t_h - infusion_h))


def bolus_ug_ml(t_h, dose_mg_m2, cl_l_h, v_l):
    return dose_mg_m2 / v_l * math.exp(-cl_l_h / v_l * t_h) if t_h >= 0 else 0.0


def summary(dose_mg_m2, infusion_h, cl_l_h, v_l, horizon_h=24.0):
    n = int(round(horizon_h / GRID_H))
    conc = [infusion_ug_ml(i * GRID_H, dose_mg_m2, infusion_h, cl_l_h, v_l) for i in range(n + 1)]
    i_max = max(range(n + 1), key=conc.__getitem__)
    k = cl_l_h / v_l
    tail = conc[-1] / k
    auc_h = GRID_H * (sum(conc) - (conc[0] + conc[-1]) / 2) + tail
    return {'cmax_ug_ml': infusion_ug_ml(infusion_h, dose_mg_m2, infusion_h, cl_l_h, v_l), 'tmax_h_grid': i_max * GRID_H,
            'auc_inf_ug_min_ml_numerical': 60.0 * auc_h, 'auc_inf_ug_min_ml_exact': 60.0 * dose_mg_m2 / cl_l_h,
            'remaining_fraction_at_24_h': math.exp(-k * 24.0)}


def parameter_sets(label):
    v = label['values']
    dose = label['regimen']['dose_mg_m2']
    half_life_h = v['terminal_half_life_min']['value'] / 60.0
    cl_a = dose / (v['auc_inf_single_100_mg_m2_ug_min_ml']['value'] / 60.0)          # mg/m2 / (mg.h/L) = L/h/m2
    lo, hi = v['clearance_ml_min_m2']['range']
    vlo, vhi = v['volume_of_distribution_l_m2']['range']
    return {
        'A_exposure_derived_mm': {'cl_l_h_m2': cl_a, 'v_l_m2': cl_a * half_life_h / math.log(2),
                                  'provenance': {'cl': 'Dose / AUC0-inf = 100 mg/m2 / 451 ug.min/mL (myeloma patients)',
                                                 'v': 'CL x 75 min / ln 2 (label terminal half-life)'}},
        'B_stated_ranges': {'cl_l_h_m2': math.sqrt(lo * hi) * 60 / 1000, 'v_l_m2': math.sqrt(vlo * vhi),
                            'provenance': {'cl': 'geometric midpoint of 250-325 mL/min/m2', 'v': 'geometric midpoint of 35.5-185.7 L/m2'}}}


def _ratio(model, label_value, judged=True):
    r = model / label_value
    return {'model': model, 'label': label_value, 'ratio': r,
            'result': ('pass' if TOLERANCE[0] <= r <= TOLERANCE[1] else 'fail') if judged else None}


def check_set(pset, label, infusion_h):
    v = label['values']
    dose = label['regimen']['dose_mg_m2']
    cl, vol = pset['cl_l_h_m2'], pset['v_l_m2']
    s = summary(dose, infusion_h, cl, vol)
    auc_label = v['auc_inf_single_100_mg_m2_ug_min_ml']['value']
    vlo, vhi = v['volume_of_distribution_l_m2']['range']
    clo, chi = v['clearance_ml_min_m2']['range']
    cl_ml_min = cl * 1000 / 60
    checks = {
        'C1_clearance_vs_exposure': _ratio(cl_ml_min, dose * 1000 / auc_label),
        'C2_half_life': _ratio(60 * math.log(2) * vol / cl, v['terminal_half_life_min']['value']),
        'C3_cmax_end_of_infusion': _ratio(s['cmax_ug_ml'], v['cmax_single_100_mg_m2_ug_ml']['value']),
        'C4_auc_inf': _ratio(s['auc_inf_ug_min_ml_numerical'], auc_label),
        'C5_volume_in_stated_range': {'model': vol, 'label_range': [vlo, vhi], 'inside': vlo <= vol <= vhi, 'result': None},
        'C6_clearance_in_stated_range': {'model': cl_ml_min, 'label_range': [clo, chi], 'inside': clo <= cl_ml_min <= chi, 'result': None}}
    return {'infusion_h': infusion_h, 'summary': s, 'checks': checks,
            'passes_c1_to_c4': all(checks[c]['result'] == 'pass' for c in PASS_FAIL)}


def numerical_checks(sets, label):
    dose = label['regimen']['dose_mg_m2']
    worst_auc, worst_bolus, worst_cont = 0.0, 0.0, 0.0
    for p in sets.values():
        s = summary(dose, 0.5, p['cl_l_h_m2'], p['v_l_m2'])
        worst_auc = max(worst_auc, abs(s['auc_inf_ug_min_ml_numerical'] - s['auc_inf_ug_min_ml_exact']) / s['auc_inf_ug_min_ml_exact'])
        # A very short infusion approaches a bolus.
        for t in (0.5, 1.0, 3.0):
            short = infusion_ug_ml(t, dose, 1e-6, p['cl_l_h_m2'], p['v_l_m2'])
            worst_bolus = max(worst_bolus, abs(short - bolus_ug_ml(t, dose, p['cl_l_h_m2'], p['v_l_m2'])) / short)
        # The curve is continuous at the end of the infusion.
        a = infusion_ug_ml(0.5 - 1e-9, dose, 0.5, p['cl_l_h_m2'], p['v_l_m2'])
        b = infusion_ug_ml(0.5 + 1e-9, dose, 0.5, p['cl_l_h_m2'], p['v_l_m2'])
        worst_cont = max(worst_cont, abs(a - b) / a)
    return {'auc_numerical_vs_exact_max_relative_difference': worst_auc, 'auc_passed': worst_auc < 1e-6,
            'short_infusion_vs_bolus_max_relative_difference': worst_bolus, 'bolus_limit_passed': worst_bolus < 1e-5,
            'end_of_infusion_continuity_max_relative_difference': worst_cont, 'continuity_passed': worst_cont < 1e-6}


def run_check():
    plan = load_plan()
    label = load_label()
    sets = parameter_sets(label)
    results = {}
    for name in plan['parameter_sets']['order_of_preference']:
        p = sets[name]
        primary = check_set(p, label, 0.5)
        sens = [check_set(p, label, t) for t in (24 / 60, 48 / 60)]
        results[name] = {'cl_l_h_m2': p['cl_l_h_m2'], 'cl_ml_min_m2': p['cl_l_h_m2'] * 1000 / 60, 'v_l_m2': p['v_l_m2'],
                         'provenance': p['provenance'], 'primary': primary,
                         'infusion_sensitivity': [{'infusion_min': round(s['infusion_h'] * 60), 'cmax_ug_ml': s['summary']['cmax_ug_ml'],
                                                   'cmax_ratio': s['checks']['C3_cmax_end_of_infusion']['ratio'],
                                                   'cmax_result': s['checks']['C3_cmax_end_of_infusion']['result']} for s in sens]}
    selected = next((n for n in plan['parameter_sets']['order_of_preference'] if results[n]['primary']['passes_c1_to_c4']), None)
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'label_extract_sha256': LABEL_SHA256,
              'label_source': {k: label['source'][k] for k in ('dailymed_set_id', 'revised', 'file_reviewed')},
              'drug': 'melphalan', 'target_population': plan['inputs']['target_population'],
              'regimen': {'dose_mg_m2': label['regimen']['dose_mg_m2'], 'infusion_h': 0.5, 'evaluated_as': 'single infusion'},
              'tolerance': list(TOLERANCE), 'which_checks_are_informative': plan['checks']['which_checks_are_informative'],
              'numerical_checks': numerical_checks(sets, label), 'parameter_sets': results,
              'decision': {'selected_set': selected, 'eligible': selected is not None, 'rule': plan['decision_rule']['selection']},
              'not_this': copy.deepcopy(plan['not_this']), 'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_label_exposure_iv_commands(app):
    @app.cli.command('label-exposure-melphalan-consistency')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(output):
        """Check the label-based melphalan infusion curve against its own label (Phase 3.1f). Not validation."""
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
