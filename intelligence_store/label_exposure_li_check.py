"""Phase 3.1d: the label-based pomalidomide curve against the Li 2017 population PK model (model-to-model check).

Li et al. 2017 fitted a one-compartment model with first-order absorption and a lag time to 63 myeloma patients
with normal to dialysis-dependent kidney function. It reports typical parameters and simulated exposures, not
observed concentration summaries, so this check compares two models. The comparison is fixed in
label_exposure_pomalidomide_li_check_plan_v1.json, locked before any Li curve was computed.
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
PLAN_PATH = DATA / 'label_exposure_pomalidomide_li_check_plan_v1.json'
PLAN_SHA256 = '45f451cf18e4b0bafb425dbdcba7c262ed02751bb895d990b877388a4aadb447'
LI_PATH = DATA / 'pomalidomide_popk_li_2017_extract_v1.json'
LI_SHA256 = '4d9c9d27608f4ae91b5f5ee3dde3ea41019cf7b4d1a4ed918d51970e05e34f1b'
REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'label_exposure_pomalidomide_li_check_v1.json'
SCHEMA_VERSION = 'label-exposure-outside-check-report-v1'
METHOD_VERSION = 'label-exposure-li-check-v1.0'
CURVE_RATIO_BAND = (0.8, 1.25)
DOSE_MG, TAU_H = 4.0, 24.0


def _load(path, expected, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'{label} is missing or changed; nothing was run.')
    return json.loads(raw)


def load_plan(path=PLAN_PATH):
    return _load(path, PLAN_SHA256, 'Li check plan')


def load_li(path=LI_PATH):
    return _load(path, LI_SHA256, 'Li 2017 extract')


def li_typical(li):
    t3 = li['table3_categorical_renal']
    return {'cl_f_l_h': t3['cl_f_normal_renal_l_h']['estimate'], 'v_f_l': t3['v_f_l']['estimate'],
            'ka_per_h': t3['ka_per_h']['estimate'], 'tlag_h': t3['tlag_h']['estimate']}


def li_steady_state_ng_ml(t_h, p):
    """Steady state with an absorption lag: within an interval, time since the effective start is shifted by the lag."""
    shifted = t_h - p['tlag_h']
    if shifted < 0:
        shifted += TAU_H
    return le.steady_state_ng_ml(shifted, DOSE_MG, TAU_H, p['cl_f_l_h'], p['v_f_l'], p['ka_per_h'])


def _summary(fn):
    n = int(round(TAU_H / le.GRID_H))
    conc = [fn(i * le.GRID_H) for i in range(n + 1)]
    i_max = max(range(n + 1), key=conc.__getitem__)
    return {'cmax_ng_ml': conc[i_max], 'tmax_h': i_max * le.GRID_H, 'ctrough_ng_ml': conc[-1],
            'auc_0_24_ng_h_ml': le.GRID_H * (sum(conc) - (conc[0] + conc[-1]) / 2)}


def _classify(value, interval):
    return ('consistent' if interval[0] <= value <= interval[1]
            else 'model_over_predicts' if value > interval[1] else 'model_under_predicts')


def run_check():
    plan = load_plan()
    li = load_li()
    label = le.load_label('pomalidomide')
    label_set = le.parameter_sets(label)['A_exposure_derived_mm']
    k = label_set['cl_f_l_h'] / label_set['v_f_l']
    ka = le.ka_from_tmax(2.5, k)
    p_li = li_typical(li)

    def label_curve(t, ka_used=ka):
        return le.steady_state_ng_ml(t, DOSE_MG, TAU_H, label_set['cl_f_l_h'], label_set['v_f_l'], ka_used)

    lab = _summary(label_curve)
    ref = _summary(lambda t: li_steady_state_ng_ml(t, p_li))

    t4 = li['table4_simulated_auc_0_24_ss']
    primary_interval = t4['normal']['ci90']
    primary = {'label_engine_auc_0_24': lab['auc_0_24_ng_h_ml'], 'li_table4_mean': t4['normal']['mean'],
               'li_table4_ci90': primary_interval,
               'classification': _classify(lab['auc_0_24_ng_h_ml'], primary_interval)}

    ratios = {}
    for name, key in (('cmax', 'cmax_ng_ml'), ('ctrough', 'ctrough_ng_ml'), ('auc_0_24', 'auc_0_24_ng_h_ml')):
        r = lab[key] / ref[key]
        ratios[name] = {'label_engine': lab[key], 'li_typical': ref[key], 'ratio': r,
                        'result': 'pass' if CURVE_RATIO_BAND[0] <= r <= CURVE_RATIO_BAND[1] else 'fail'}

    t3 = li['table3_categorical_renal']
    label_dialysis = label['scenarios']['renal_severe_requiring_dialysis']['auc_fold']
    norm_ci = [x / 100.0 for x in (107.5, 170.0)]
    dialysis = {'label_auc_fold': label_dialysis, 'li_inverse_cl_ratio': 1.0 / t3['cl_f_ratio_severe_dialysis']['estimate'],
                'li_table4_normalized_mean': t4['severe_dialysis']['mean'] / t4['normal']['mean'],
                'li_table4_normalized_ci90': norm_ci, 'source_note': 'Table 4 normalized AUC 135.8% (107.5-170.0%)',
                'classification': _classify(label_dialysis, norm_ci)}
    no_effect = {g: {'li_cl_ratio': t3[f'cl_f_ratio_{g}']['estimate'], 'bootstrap_ci90': t3[f'cl_f_ratio_{g}']['bootstrap_ci90'],
                     'includes_1': t3[f'cl_f_ratio_{g}']['bootstrap_ci90'][0] <= 1.0 <= t3[f'cl_f_ratio_{g}']['bootstrap_ci90'][1]}
                 for g in ('moderate', 'severe_no_dialysis')}
    no_effect_consistent = all(v['includes_1'] for v in no_effect.values())

    descriptive_params = {
        'cl_f_l_h': (label_set['cl_f_l_h'], t3['cl_f_normal_renal_l_h']),
        'v_f_l': (label_set['v_f_l'], t3['v_f_l']), 'ka_per_h': (ka, t3['ka_per_h'])}
    params = {n: {'label_engine': v, 'li_estimate': ref_['estimate'], 'li_bootstrap_ci90': ref_['bootstrap_ci90'],
                  'inside_li_interval': ref_['bootstrap_ci90'][0] <= v <= ref_['bootstrap_ci90'][1]}
              for n, (v, ref_) in descriptive_params.items()}
    curves = {'times_h': [i * 0.25 for i in range(97)]}
    curves['label_engine_ng_ml'] = [label_curve(t) for t in curves['times_h']]
    curves['li_typical_ng_ml'] = [li_steady_state_ng_ml(t, p_li) for t in curves['times_h']]
    tmax_sensitivity = []
    for tmax in (2.0, 3.0):
        ka_s = le.ka_from_tmax(tmax, k)
        s = _summary(lambda t: label_curve(t, ka_s))
        tmax_sensitivity.append({'tmax_for_ka_h': tmax, 'ka_per_h': ka_s,
                                 'cmax_ratio_to_li': s['cmax_ng_ml'] / ref['cmax_ng_ml'],
                                 'ctrough_ratio_to_li': s['ctrough_ng_ml'] / ref['ctrough_ng_ml']})

    consistent = primary['classification'] == 'consistent' and all(r['result'] == 'pass' for r in ratios.values())
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'li_extract_sha256': LI_SHA256, 'label_extract_sha256': le.LABEL_PATHS['pomalidomide'][1],
              'classification': plan['classification'],
              'regimen': {'dose_mg': DOSE_MG, 'interval_h': TAU_H, 'evaluated_at': 'steady state'},
              'label_engine_parameters': {'cl_f_l_h': label_set['cl_f_l_h'], 'v_f_l': label_set['v_f_l'], 'ka_per_h': ka},
              'li_typical_parameters': p_li,
              'label_engine_summary': lab, 'li_typical_summary': ref,
              'primary': primary, 'typical_curve_ratios': ratios, 'curve_ratio_band': list(CURVE_RATIO_BAND),
              'dialysis_scenario': dialysis,
              'no_effect_moderate_severe_without_dialysis': {'groups': no_effect, 'consistent': no_effect_consistent},
              'descriptive': {'parameters_against_li_intervals': params, 'ka_sensitivity': tmax_sensitivity, 'curves': curves},
              'decision': {'curve_consistent_with_li_2017': consistent,
                           'dialysis_scenario_consistent': dialysis['classification'] == 'consistent',
                           'no_effect_statement_consistent': no_effect_consistent,
                           'rule': plan['decision_rule']['summary']},
              'not_this': copy.deepcopy(plan['not_this']),
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_label_exposure_li_commands(app):
    @app.cli.command('label-exposure-li-check')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(output):
        """Compare the label-based pomalidomide curve with the Li 2017 model (Phase 3.1d). Exploratory; not validation."""
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
