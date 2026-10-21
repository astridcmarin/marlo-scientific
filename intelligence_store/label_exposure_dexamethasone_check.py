"""Phase 3.1g: the label-based dexamethasone curve (HEMADY, 3.1f) against outside exposure data from the NEOFORDEX EPAR.

Primary: study CC-5013-MM-017 (6 Japanese myeloma patients, single 40 mg dose, geometric means). Secondary: the
CPA-402-11 bioequivalence study (24 healthy volunteers, 20 mg, arithmetic means, both arms). Spoorenberg 2014 is
descriptive context only. All rules are fixed in label_exposure_dexamethasone_outside_check_plan_v1.json, locked
after reading only the study designs and before the results tables.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

import click

from . import label_exposure as le
from . import label_exposure_single_dose as sd
from .bortezomib_pk_ogawa_check import T975
from .patient_state import digest

DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'label_exposure_dexamethasone_outside_check_plan_v1.json'
PLAN_SHA256 = '22312b7708384850b8b182cc13c6e86744df6f99d35ae36620484a09374f4ad4'
OBSERVED_PATH = DATA / 'dexamethasone_outside_pk_v1.json'
OBSERVED_SHA256 = 'a3d7de4528207684525885a6524c5b3e552664959b01e13ce6ba186eb163a774'
REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'label_exposure_dexamethasone_outside_check_v1.json'
SCHEMA_VERSION = 'label-exposure-outside-check-report-v1'
METHOD_VERSION = 'label-exposure-dexamethasone-check-v1.0'
T975_FULL = {**T975, 23: 2.0687}


def _load(path, expected, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'{label} is missing or changed; nothing was run.')
    return json.loads(raw)


def load_plan(path=PLAN_PATH):
    return _load(path, PLAN_SHA256, 'Dexamethasone outside-check plan')


def load_observed(path=OBSERVED_PATH):
    return _load(path, OBSERVED_SHA256, 'Dexamethasone outside data')


def ci_arithmetic(mean, sd_, n):
    half = T975_FULL[n - 1] * sd_ / math.sqrt(n)
    return [mean - half, mean + half]


def ci_geometric(gm, cv_percent, n):
    s = math.sqrt(math.log(1 + (cv_percent / 100.0) ** 2))
    half = T975_FULL[n - 1] * s / math.sqrt(n)
    return [gm * math.exp(-half), gm * math.exp(half)]


def _classify(value, interval):
    return ('consistent' if interval[0] <= value <= interval[1]
            else 'model_over_predicts' if value > interval[1] else 'model_under_predicts')


def label_curve():
    label = sd.load_label()
    p = sd.parameter_set(label)
    ka = le.ka_from_tmax(label['values']['tmax_h']['value'], p['cl_f_l_h'] / p['v_f_l'])
    return p, ka


def model_exposure(dose_mg, p, ka, t_end=None):
    """Model Cmax, Tmax and AUC (0-inf, or 0-t_end) for one dose; linear scaling is built into the model."""
    s = sd.single_dose_summary(dose_mg, p['cl_f_l_h'], p['v_f_l'], ka)
    out = {'cmax_ng_ml': s['cmax_ng_ml'], 'tmax_h': s['tmax_h_grid'], 'auc_inf_ng_h_ml': s['auc_inf_ng_h_ml_exact']}
    if t_end is not None:
        n = int(round(t_end / le.GRID_H))
        conc = [le.single_dose_ng_ml(i * le.GRID_H, dose_mg, p['cl_f_l_h'], p['v_f_l'], ka) for i in range(n + 1)]
        out[f'auc_0_{int(t_end)}_ng_h_ml'] = le.GRID_H * (sum(conc) - (conc[0] + conc[-1]) / 2)
    return out


def _row(model, central, interval, statistic, n):
    return {'model': model, 'observed': central, 'statistic': statistic, 'n': n, 'interval_95': interval,
            'ratio_model_to_observed': model / central, 'classification': _classify(model, interval)}


def run_check():
    plan = load_plan()
    obs = load_observed()
    p, ka = label_curve()

    mm = obs['MM_017']['day2_dex_alone']
    m40 = model_exposure(40.0, p, ka)
    primary = _row(m40['auc_inf_ng_h_ml'], mm['auc_inf_ng_h_ml'][0], ci_geometric(*mm['auc_inf_ng_h_ml'], mm['n']), 'geometric mean', mm['n'])
    mm_cmax = _row(m40['cmax_ng_ml'], mm['cmax_ng_ml'][0], ci_geometric(*mm['cmax_ng_ml'], mm['n']), 'geometric mean', mm['n'])

    m20 = model_exposure(20.0, p, ka, t_end=36.0)
    cpa = {}
    for arm in ('test', 'reference'):
        a = obs['CPA_402_11'][arm]
        cpa[arm] = {
            'auc_inf': _row(m20['auc_inf_ng_h_ml'], a['auc_inf_ug_h_l'][0], ci_arithmetic(*a['auc_inf_ug_h_l'], a['n']), 'arithmetic mean', a['n']),
            'auc_0_36': _row(m20['auc_0_36_ng_h_ml'], a['auc_0_36_ug_h_l'][0], ci_arithmetic(*a['auc_0_36_ug_h_l'], a['n']), 'arithmetic mean', a['n']),
            'cmax': _row(m20['cmax_ng_ml'], a['cmax_ug_l'][0], ci_arithmetic(*a['cmax_ug_l'], a['n']), 'arithmetic mean', a['n']),
            'tmax_observed_median_range_h': a['tmax_h_median_range'], 'half_life_observed_h': a['half_life_h']}

    d12 = obs['MM_017']['day12_with_lenalidomide']
    sp = obs['spoorenberg_2014_context']['oral_6mg']
    descriptive = {
        'model_half_life_h': math.log(2) * p['v_f_l'] / p['cl_f_l_h'], 'model_tmax_h': m20['tmax_h'],
        'model_cl_f_l_h': p['cl_f_l_h'],
        'mm017_day2': {'tmax_h_median_range': mm['tmax_h_median_range'], 'half_life_h_gm': mm['half_life_h'][0],
                       'cl_f_l_h_gm': mm['cl_f_ml_min'][0] * 60 / 1000, 'vz_f_l_gm': mm['vz_f_l'][0]},
        'mm017_day12_with_lenalidomide': {'cmax_ng_ml_gm': d12['cmax_ng_ml'][0], 'auc_tau_ng_h_ml_gm': d12['auc_tau_ng_h_ml'][0],
                                          'cl_f_l_h_gm': d12['cl_f_ml_min'][0] * 60 / 1000,
                                          'model_single_dose_auc_inf_40mg': m40['auc_inf_ng_h_ml'], 'classification': None},
        'spoorenberg_2014_scaled_to_20mg': {'auc_inf_ug_l_h_median': sp['auc_inf_ug_l_h'] * 20 / 6, 'cmax_ug_l_median': sp['cmax_ug_l'][0] * 20 / 6,
                                            'clearance_l_h_median': sp['clearance_l_h'][0], 'half_life_h_median': sp['half_life_h'][0],
                                            'population': 'hospitalized with community-acquired pneumonia; context only', 'classification': None}}

    consistent = (primary['classification'] == 'consistent'
                  and all(cpa[arm]['auc_inf']['classification'] == 'consistent' for arm in cpa))
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'observed_sha256': OBSERVED_SHA256, 'label_extract_sha256': sd.LABEL_SHA256,
              'classification': plan['classification'],
              'label_curve_parameters': {'cl_f_l_h': p['cl_f_l_h'], 'v_f_l': p['v_f_l'], 'ka_per_h': ka},
              'primary_mm017_auc_inf_40mg': primary,
              'secondary': {'mm017_cmax_40mg': mm_cmax, 'cpa_402_11_20mg': cpa},
              'descriptive': descriptive,
              'decision': {'curve_consistent_with_outside_data': consistent,
                           'cmax_classifications': {'mm017': mm_cmax['classification'],
                                                    **{f'cpa_{arm}': cpa[arm]['cmax']['classification'] for arm in cpa}},
                           'rule': plan['decision_rule']['summary']},
              'not_this': copy.deepcopy(plan['not_this']), 'known_differences': copy.deepcopy(plan['known_differences']),
              'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_label_exposure_dexamethasone_commands(app):
    @app.cli.command('label-exposure-dexamethasone-outside-check')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(output):
        """Compare the label-based dexamethasone curve with the NEOFORDEX EPAR studies (Phase 3.1g). Not validation."""
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
