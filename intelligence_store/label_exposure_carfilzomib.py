"""Carfilzomib (KYPROLIS) label-consistency check: plan label-exposure-consistency-plan-carfilzomib-v1.0.

A one-compartment, constant-rate intravenous curve built from the label by the plan's fixed rules, checked against the
label's own Table 21 exposure. Uses the infusion function of the intravenous engine (label_exposure_iv.py), with dose in
mg (mg/m2 x body surface area), CL in L/h and V in L, so concentrations come out in mg/L (ug/mL).

run_check(plan, label) takes the plan and the extract as objects, so the same code runs on a synthetic extract before
the lock and on the pinned extract after it. Nothing here is a dosing recommendation or an exposure prediction.
"""
import hashlib
import json
import math
from pathlib import Path

from .label_exposure_iv import infusion_ug_ml
from .patient_state import digest

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'label_exposure_consistency_plan_carfilzomib_v1.json'
PLAN_SHA256 = 'ab11dfbd94ce8daef7d8326d454744be8b9f28fcceae282e233ce04b8211c3ad'   # locked 19 November 2026, approved by the owner
LABEL_PATH = DATA / 'label_extract_carfilzomib_v1.json'
LABEL_SHA256 = '199572222b557c6cd6e4b95b5941408ed3568d942c3b15e612fcc73d0e63491f'
REPORT_PATH = ROOT / 'docs' / 'verification' / 'label_exposure_carfilzomib_consistency_v1.json'
SCHEMA_VERSION = 'label-exposure-consistency-report-v1'
METHOD_VERSION = 'label-exposure-carfilzomib-v1.0'
TOLERANCE = (0.67, 1.5)
PASS_FAIL = ('C1_clearance_in_stated_range', 'C2_half_life', 'C3_cmax_primary', 'C4_auc_ss_primary',
             'C5_auc_c1_primary', 'C6_cmax_secondary', 'C7_auc_ss_secondary', 'C8_no_accumulation')
CYCLE_DAYS = 28
REGIMENS = {   # dose per infusion (mg/m2), in order, over the first cycle and at steady state; from section 2.2
    '20/70 once weekly, 30 min': {'cycle_1': [20, 70, 70], 'steady': [70, 70, 70], 'highest': 70, 'infusion_h': 0.5},
    '20/56 twice weekly, 30 min': {'cycle_1': [20, 20, 56, 56, 56, 56], 'steady': [56] * 6, 'highest': 56, 'infusion_h': 0.5},
}
PRIMARY, SECONDARY = '20/70 once weekly, 30 min', '20/56 twice weekly, 30 min'
SHORT = '20/27 twice weekly, 2-10 min'


def _load(path, expected, what):
    raw = Path(path).read_bytes()
    if expected is None:
        raise ValueError(f'{what} is not pinned yet.')
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'{what} is missing or changed.')
    return json.loads(raw)


def load_plan(path=PLAN_PATH):
    return _load(path, PLAN_SHA256, 'Carfilzomib label-consistency plan')


def load_label(path=LABEL_PATH):
    return _load(path, LABEL_SHA256, 'Carfilzomib label extract')


def table_21(label):
    pk = label['pk']
    return {'auc_c1': {k: v[0] for k, v in pk['auc_c1_avg_ng_h_ml']['by_regimen'].items()},
            'auc_ss': {k: v[0] for k, v in pk['auc_ss_ng_h_ml']['by_regimen'].items()},
            'cmax_c1': {k: v[0] for k, v in pk['cmax_c1_ng_ml']['by_regimen'].items()},
            'cl_range_l_h': pk['cl_l_h']['range'], 'vss_l': pk['vss_l']['value'],
            'half_life_bound_h': pk['half_life_h']['upper_bound']}


def implied_cl_l_h(regimen, auc_ss_ng_h_ml, bsa):
    """Steady-state cycle dose / (average daily AUC x 28): mg / (ug.h/L) x 1000 = L/h."""
    dose_mg = sum(REGIMENS[regimen]['steady']) * bsa
    return dose_mg * 1000.0 / (auc_ss_ng_h_ml * CYCLE_DAYS)


def parameter_sets(label, bsa):
    t = table_21(label)
    lo, hi = t['cl_range_l_h']
    return {
        'A_exposure_derived': {'cl_l_h': implied_cl_l_h(PRIMARY, t['auc_ss'][PRIMARY], bsa), 'v_l': t['vss_l'],
                               'provenance': {'cl': f'210 mg/m2 x {bsa} m2 / (Table 21 AUCss for 20/70 x 28 days)',
                                              'v': 'Vss, 28 L (label, 20 mg/m2)'}},
        'B_stated_clearance': {'cl_l_h': math.sqrt(lo * hi), 'v_l': t['vss_l'],
                               'provenance': {'cl': 'geometric midpoint of 151-263 L/h', 'v': 'Vss, 28 L (label, 20 mg/m2)'}},
    }


def cmax_ng_ml(dose_mg_m2, bsa, infusion_h, cl, v):
    return 1000.0 * infusion_ug_ml(infusion_h, dose_mg_m2 * bsa, infusion_h, cl, v)


def avg_daily_auc_ng_h_ml(doses_mg_m2, bsa, cl):
    """Sum of Dose / CL over the cycle's doses, divided by 28 days (no accumulation; C8 tests that)."""
    return sum(d * bsa * 1000.0 / cl for d in doses_mg_m2) / CYCLE_DAYS


def _ratio(model, label_value, judged=True):
    r = model / label_value
    return {'model': model, 'label': label_value, 'ratio': r,
            'result': ('pass' if TOLERANCE[0] <= r <= TOLERANCE[1] else 'fail') if judged else None}


def check_set(pset, label, bsa):
    t = table_21(label)
    cl, v = pset['cl_l_h'], pset['v_l']
    lo, hi = t['cl_range_l_h']
    half_life = math.log(2) * v / cl
    remaining = math.exp(-cl / v * 24.0)
    checks = {
        'C1_clearance_in_stated_range': {'model': cl, 'label_range': [lo, hi], 'result': 'pass' if lo <= cl <= hi else 'fail'},
        'C2_half_life': {'model': half_life, 'label_bound': t['half_life_bound_h'],
                         'result': 'pass' if half_life <= t['half_life_bound_h'] else 'fail'},
        'C3_cmax_primary': _ratio(cmax_ng_ml(REGIMENS[PRIMARY]['highest'], bsa, 0.5, cl, v), t['cmax_c1'][PRIMARY]),
        'C4_auc_ss_primary': _ratio(avg_daily_auc_ng_h_ml(REGIMENS[PRIMARY]['steady'], bsa, cl), t['auc_ss'][PRIMARY]),
        'C5_auc_c1_primary': _ratio(avg_daily_auc_ng_h_ml(REGIMENS[PRIMARY]['cycle_1'], bsa, cl), t['auc_c1'][PRIMARY]),
        'C6_cmax_secondary': _ratio(cmax_ng_ml(REGIMENS[SECONDARY]['highest'], bsa, 0.5, cl, v), t['cmax_c1'][SECONDARY]),
        'C7_auc_ss_secondary': _ratio(avg_daily_auc_ng_h_ml(REGIMENS[SECONDARY]['steady'], bsa, cl), t['auc_ss'][SECONDARY]),
        'C8_no_accumulation': {'model': remaining, 'bound': 0.001, 'result': 'pass' if remaining < 0.001 else 'fail'},
        'D1_auc_c1_secondary': _ratio(avg_daily_auc_ng_h_ml(REGIMENS[SECONDARY]['cycle_1'], bsa, cl), t['auc_c1'][SECONDARY], judged=False),
        'D2_short_infusion': {
            'cmax_27_mg_m2_by_minutes': {m: _ratio(cmax_ng_ml(27, bsa, m / 60.0, cl, v), t['cmax_c1'][SHORT], judged=False)
                                         for m in (2, 6, 10)},
            'cmax_ratio_short_to_30_min_same_dose': {m: cmax_ng_ml(27, bsa, m / 60.0, cl, v) / cmax_ng_ml(27, bsa, 0.5, cl, v)
                                                     for m in (2, 10)},
            'label': '2- to 3-fold', 'result': None},
    }
    return {'bsa_m2': bsa, 'cl_l_h': cl, 'v_l': v, 'checks': checks,
            'passes_all': all(checks[c]['result'] == 'pass' for c in PASS_FAIL)}


def numerical_checks(sets, bsa):
    """The engine's infusion function against closed forms: AUC by quadrature equals Dose / CL; continuity at T."""
    worst_auc, worst_cont = 0.0, 0.0
    for p in sets.values():
        cl, v, dose = p['cl_l_h'], p['v_l'], 70 * bsa
        step, horizon = 0.0005, 24.0
        n = int(round(horizon / step))
        conc = [infusion_ug_ml(i * step, dose, 0.5, cl, v) for i in range(n + 1)]
        auc = step * (sum(conc) - (conc[0] + conc[-1]) / 2) + conc[-1] / (cl / v)
        worst_auc = max(worst_auc, abs(auc - dose / cl) / (dose / cl))
        a, b = infusion_ug_ml(0.5 - 1e-9, dose, 0.5, cl, v), infusion_ug_ml(0.5 + 1e-9, dose, 0.5, cl, v)
        worst_cont = max(worst_cont, abs(a - b) / a)
    return {'auc_numerical_vs_exact_max_relative_difference': worst_auc, 'auc_passed': worst_auc < 1e-4,
            'end_of_infusion_continuity_max_relative_difference': worst_cont, 'continuity_passed': worst_cont < 1e-6}


def run_check(plan, label):
    if plan['plan_version'] != 'label-exposure-consistency-plan-carfilzomib-v1.0':
        raise ValueError('wrong plan')
    bsa = plan['inputs']['body_surface_area_m2']['value']
    t = table_21(label)
    by_bsa = {}
    for b in [bsa] + plan['inputs']['body_surface_area_m2']['sensitivity']:
        sets = parameter_sets(label, b)
        by_bsa[str(b)] = {name: dict(check_set(p, label, b), provenance=p['provenance']) for name, p in sets.items()}
    primary = by_bsa[str(bsa)]
    selected = next((n for n in plan['parameter_sets']['order_of_preference'] if primary[n]['passes_all']), None)
    implied = {r: implied_cl_l_h(r, t['auc_ss'][r], bsa) for r in REGIMENS}
    report = {
        'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'drug': 'carfilzomib',
        'plan': {'file': str(PLAN_PATH.relative_to(ROOT)), 'plan_version': plan['plan_version'],
                 'sha256': hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest() if PLAN_SHA256 else None},
        'label_extract': {'file': str(LABEL_PATH.relative_to(ROOT)), 'sha256': LABEL_SHA256},
        'body_surface_area_m2': bsa, 'tolerance': list(TOLERANCE),
        'sets_by_bsa': by_bsa,
        'D3_implied_clearance_by_regimen': {'cl_l_h': implied, 'ratio_secondary_to_primary': implied[SECONDARY] / implied[PRIMARY]},
        'numerical_checks': numerical_checks(parameter_sets(label, bsa), bsa),
        'selected_set': selected,
        'outcome': 'eligible' if selected else 'not_eligible',
        'scenarios': ({'hepatic_mild_moderate': {'cl_factor': 1 / 1.5, 'quote': label['special_populations']['hepatic_mild_moderate_auc_fold']['quote']},
                       'esrd_haemodialysis': {'cl_factor': 1 / 1.33, 'quote': label['special_populations']['esrd_hemodialysis_auc_fold']['quote']},
                       'renal_15_89_age_sex_race': {'cl_factor': 1.0, 'quote': label['special_populations']['covariates_no_effect']['quote']}}
                      if selected else None),
        'assumptions': ['Body surface area 1.8 m2 (label does not state it); 1.6 and 2.0 m2 reported beside it.',
                        'Average daily AUC read as total AUC over a 28-day cycle divided by 28.',
                        'One compartment with Vss as its volume; the label gives no central volume.'],
        'clinical_prediction_validated': False,
    }
    report['report_sha256'] = digest(report)
    return report
