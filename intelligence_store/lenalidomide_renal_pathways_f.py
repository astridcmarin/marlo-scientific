"""Simulation 2.0e: the 2.0a kidney-pathway comparison re-run across bioavailability F (plan v3, locked 4 November 2026).

Renal clearance (amount in urine / AUC) does not depend on F; the non-renal clearance derived from CL/F does. At F = 1
this is exactly the 2.0a reading A model. The plan fixes the scenarios (F = 1.0, 0.95, 0.90 decide; 0.85 reported) and,
before computation, what the body map says for each outcome. Not blind: every value used had been seen.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

from scipy.stats import t as student_t

from .patient_state import digest

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'lenalidomide_renal_pathways_plan_v3.json'
PLAN_SHA256 = 'ccbd8fcbf2674e8e167fdc7acfbf5916fe6ebe15eab938ccc4bbc2c5c9f47bc9'
REPORT_PATH = ROOT / 'docs' / 'verification' / 'lenalidomide_renal_pathways_check_v3.json'
SCHEMA_VERSION = 'lenalidomide-renal-pathways-check-report-v3'
METHOD_VERSION = 'lenalidomide-renal-pathways-f-v1.0'
FU, CRCL_REF = 0.77, 110.0
PRIMARY = {'normal': 110.0, 'mild': 65.0, 'moderate': 40.0, 'severe_without_dialysis': 20.0}
CHEN_NAMES = {'normal': 'normal', 'mild': 'mild', 'moderate': 'moderate', 'severe_without_dialysis': 'severe'}
IMPAIRED = ('mild', 'moderate', 'severe_without_dialysis')
BANDS = {'moderate': 'moderate', 'severe': 'severe_without_dialysis'}


class RenalPathwaysFError(ValueError):
    pass


def _pinned(path, sha, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        raise RenalPathwaysFError(f'{label} is missing or changed; nothing was computed.')
    return json.loads(raw)


def load_plan():
    plan = _pinned(PLAN_PATH, PLAN_SHA256, 'Renal pathways plan v3')
    if plan['status'] != 'locked_before_computation':
        raise RenalPathwaysFError('Plan v3 is not locked.')
    return plan


def calibrate_f(evidence, F, crcl_normal=CRCL_REF):
    dose = evidence['study']['dose_mg']
    normal = next(g for g in evidence['groups'] if g['group'] == 'normal')
    cl_app = dose * 1e6 / normal['auc_ng_h_ml'][0] / 60.0          # apparent CL/F, mL/min
    renal = normal['fe_percent'] / 100.0 * cl_app                   # Ae / AUC: independent of F
    filtration = FU * crcl_normal
    return {'F': F, 'crcl_ml_min': crcl_normal, 'renal_ml_min': renal, 'non_renal_ml_min': F * cl_app - renal,
            'filtration_ml_min': filtration, 'secretion_ml_min': renal - filtration, 'cl_apparent_ml_min': cl_app}


def predict(cal, crcl):
    renal = FU * crcl + cal['secretion_ml_min'] * crcl / cal['crcl_ml_min']
    total = renal + cal['non_renal_ml_min']
    return {'renal_ml_min': renal, 'total_true_ml_min': total, 'cl_f_ml_min': total / cal['F'], 'fe': renal / total * cal['F']}


def _classify(v, ci):
    return 'model_under_predicts' if v < ci[0] else 'model_over_predicts' if v > ci[1] else 'consistent'


def _cc5013(evidence, cal, crcls):
    dose = evidence['study']['dose_mg']
    groups = {g['group']: g for g in evidence['groups']}
    out = {}
    for g in IMPAIRED:
        o = groups[g]
        mean, sd, n = o['auc_ng_h_ml'][0], o['auc_ng_h_ml'][1], o['n']
        half = float(student_t.ppf(0.975, n - 1)) * sd / math.sqrt(n)
        ci = [mean - half, mean + half]
        p = predict(cal, crcls[g])
        auc = 1e6 * dose / (p['cl_f_ml_min'] * 60.0)
        out[g] = {'crcl_ml_min': crcls[g], 'model_auc': auc, 'observed_mean': mean, 'ci95': ci, 'classification': _classify(auc, ci),
                  'model_fe': p['fe'], 'observed_fe': o['fe_percent'] / 100.0}
    return out


def _myeloma(cal, inputs):
    bd, bo, kim = inputs['bridoux_design'], inputs['bridoux_observed'], inputs['kim_extract']['author_reported_groups']
    out = {'bridoux': {}, 'kim': {}}
    for g in ('normal', 'mild', 'moderate', 'severe'):
        o = bo['groups'][g]
        s = math.sqrt(math.log(1 + (o['auc24_gcv_pct'] / 100) ** 2))
        half = float(student_t.ppf(0.95, o['n'] - 1)) * s / math.sqrt(o['n'])
        ci = [o['auc24_gm'] * math.exp(-half), o['auc24_gm'] * math.exp(half)]
        crcl = bd['design']['per_group']['crcl_mean_sd_ml_min'][g][0]
        auc = 1e6 * o['dose_mg_per_24h'] / (predict(cal, crcl)['cl_f_ml_min'] * 60.0)
        out['bridoux'][g] = {'crcl_ml_min': crcl, 'model': auc, 'observed_gm': o['auc24_gm'], 'ci90': ci, 'classification': _classify(auc, ci)}
    for g in ('control', 'moderate', 'severe'):
        med, obs = kim['table1_medians'][g], kim['table2_total_cl_f_l_h'][g]
        half = float(student_t.ppf(0.95, med['n'] - 1)) * obs['sd'] / math.sqrt(med['n'])
        ci = [obs['mean'] - half, obs['mean'] + half]
        crcl = med['egfr'] * med['bsa'] / 1.73
        cl = predict(cal, crcl)['cl_f_ml_min'] * 0.06
        out['kim'][g] = {'input_ml_min': crcl, 'model': cl, 'observed_mean': obs['mean'], 'ci90': ci, 'classification': _classify(cl, ci)}
    return out


def _esrd(evidence, cal):
    dose = evidence['study']['dose_mg']
    out = {}
    for c in (0, 5, 10):
        total = cal['non_renal_ml_min'] + (predict(cal, c)['renal_ml_min'] if c else 0.0)
        out[str(c)] = 1e6 * dose / (total / cal['F'] * 60.0) if total > 1e-9 else None   # no elimination left: not computable
    return out


def run_check():
    plan = load_plan()
    inputs = {n: _pinned(ROOT / r['file'], r['sha256'], n) for n, r in plan['pinned_inputs'].items()}
    ev = inputs['pathway_evidence']
    chen = inputs['chen_2007_demographics']['sources']['chen_2007']['table_I_demographics']
    secondary_crcl = {g: chen[CHEN_NAMES[g]]['crcl_ml_min_mean'] for g in PRIMARY}
    f_all = plan['scenarios']['F_best_supported'] + [plan['scenarios']['F_lower_bound']]
    scen = {}
    for F in f_all:
        cal = calibrate_f(ev, F)
        cal_sec = calibrate_f(ev, F, secondary_crcl['normal'])
        scen[f'{F:.2f}'] = {'calibration': cal, 'possible': cal['non_renal_ml_min'] >= -1e-9,
                            'cc5013_primary': _cc5013(ev, cal, PRIMARY), 'cc5013_secondary': _cc5013(ev, cal_sec, secondary_crcl),
                            'myeloma': _myeloma(cal, inputs), 'esrd_auc_by_residual_crcl': _esrd(ev, cal)}
    # numerical check: F = 1 reproduces 2.0a reading A
    from .lenalidomide_renal_pathways import calibrate, pathways
    a = calibrate(ev, CRCL_REF, FU)
    worst = max(abs(pathways(a, c, 'A_intact_nephron')['total_ml_min'] - predict(calibrate_f(ev, 1.0), c)['total_true_ml_min'])
                / pathways(a, c, 'A_intact_nephron')['total_ml_min'] for c in (10.0, 20.0, 40.0, 65.0, 110.0))
    if worst > 1e-12:
        raise RenalPathwaysFError('F = 1 does not reproduce 2.0a.')
    best = [f'{F:.2f}' for F in plan['scenarios']['F_best_supported']]
    low = f"{plan['scenarios']['F_lower_bound']:.2f}"
    d1 = {}
    for band, g in BANDS.items():
        by_f = {F: scen[F]['cc5013_primary'][g]['classification'] for F in best}
        d1[band] = {'by_F': by_f, 'at_lower_bound': scen[low]['cc5013_primary'][g]['classification'],
                    'status': 'unchanged_holds_for_F_0_90_to_1' if len(set(by_f.values())) == 1 else 'depends_on_bioavailability'}
    moderate_consistent_somewhere = any(scen[F]['cc5013_primary']['moderate']['classification'] == 'consistent' for F in best)
    nr = [scen[F]['calibration']['non_renal_ml_min'] for F in best]
    d3 = {'range_ml_min': [min(nr), max(nr)], 'at_F_1': scen['1.00']['calibration']['non_renal_ml_min'],
          'status': 'depends_on_bioavailability' if max(nr) > 1.5 * min(nr) else 'calibrated'}
    d4 = {}
    for band, groups in {'moderate': ('moderate', 'moderate'), 'severe': ('severe', 'severe')}.items():
        by_f = {F: {'bridoux': scen[F]['myeloma']['bridoux'][groups[0]]['classification'],
                    'kim': scen[F]['myeloma']['kim'][groups[1]]['classification']} for F in best}
        d4[band] = {'by_F': by_f, 'holds_at_every_F': all(set(v.values()) == {'consistent'} for v in by_f.values()),
                    'not_at': [F for F, v in by_f.items() if set(v.values()) != {'consistent'}]}
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'input_sha256': {n: r['sha256'] for n, r in plan['pinned_inputs'].items()},
              'classification': 'checks_on_seen_data_not_blind', 'what_is_known_before_computation': plan['what_is_known_before_computation'],
              'numerical_checks': {'F1_reproduces_2_0a_max_relative_difference': worst, 'pass': True}, 'scenarios': scen,
              'decision': {'D1_band_status': d1,
                           'D2_faster_than_proportional': 'not_established' if moderate_consistent_somewhere else 'holds_for_F_0_90_to_1',
                           'D3_non_renal': d3, 'D4_myeloma_note': d4, 'rules': copy.deepcopy(plan['decision_rule'])},
              'known_limitations': copy.deepcopy(plan['known_limitations']),
              'clinical_prediction_validated': False, 'ready_for_patient_simulation': False}
    report['report_sha256'] = digest(report)
    return report


def write_report(path=REPORT_PATH):
    r = run_check()
    Path(path).write_text(json.dumps(r, indent=1, ensure_ascii=False, allow_nan=False) + '\n')
    return r
