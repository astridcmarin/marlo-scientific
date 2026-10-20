"""Phase 3.1e: what the platform may show for a drug at the capability level *Label-based exposure*.

A label-based curve is shown only when (1) the label extract is intact, (2) the committed internal-consistency report
(3.1c) is intact and selected a parameter set, (3) the committed outside check (3.1d) is intact and consistent, and
(4) the parameters recomputed from the label by the plan's rules equal those in the report. If any of these fails,
nothing is shown and the drug stays at its previous level.

Scenarios apply one label fold-change at a time to apparent clearance (CL/F divided by the AUC fold); volume and
absorption are unchanged. The label states only the AUC change, so a scenario's peak and trough are a model
consequence, not label values.
"""
import hashlib
import json
from pathlib import Path

from . import label_exposure as le
from . import label_exposure_li_check as li_check

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = {
    'pomalidomide': {
        'label': 'Pomalidomide',
        'consistency_report': ('docs/verification/label_exposure_pomalidomide_consistency_v1.json',
                               'f5b91ce96404f0fc9f39eb83c531f7fef8e6385e0cdb00211cb7c31de5288711'),
        'outside_report': ('docs/verification/label_exposure_pomalidomide_li_check_v1.json',
                           '3439bf93699061f31fc6a962410126e2d29825149fe0c51b3deb5af58e674129'),
        'outside_source': {'citation': 'Li Y, et al. Clin Pharmacol Adv Appl. 2017;9:133-145.', 'doi': '10.2147/CPAA.S144606'},
        'tmax_for_ka_h': 2.5,
    },
}
SCENARIO_LABELS = {
    'renal_moderate_or_severe_no_dialysis': 'Kidney impairment, moderate or severe, no dialysis',
    'renal_severe_requiring_dialysis': 'Severe kidney impairment requiring dialysis',
    'renal_esrd_non_dialysis_days': 'End-stage kidney disease, non-dialysis days',
    'hepatic_child_pugh_a': 'Mild liver impairment (Child-Pugh A)',
    'hepatic_child_pugh_b': 'Moderate liver impairment (Child-Pugh B)',
    'hepatic_child_pugh_c': 'Severe liver impairment (Child-Pugh C)',
    'fluvoxamine_strong_cyp1a2_inhibitor': 'With fluvoxamine (strong CYP1A2 inhibitor)',
    'fluvoxamine_with_ketoconazole': 'With fluvoxamine and ketoconazole',
    'ketoconazole_strong_cyp3a4_pgp_inhibitor': 'With ketoconazole (strong CYP3A4 and P-gp inhibitor)',
    'carbamazepine_strong_cyp3a4_inducer': 'With carbamazepine (strong CYP3A4 inducer)',
    'smoking_25_per_day': 'Smoking (25 cigarettes a day)',
    'high_fat_meal': 'Taken with a high-fat meal',
}
NOT_SCENARIOS = {'high_fat_meal': 'The label reports a single-dose food effect on Cmax and Tmax as well as AUC; '
                                  'scaling clearance would misrepresent it, so it is shown as text only.'}


def _report(path, sha256):
    raw = (ROOT / path).read_bytes() if (ROOT / path).is_file() else None
    if raw is None or hashlib.sha256(raw).hexdigest() != sha256:
        return None
    return json.loads(raw)


def _verified(drug):
    entry = REGISTRY.get(drug)
    if entry is None:
        return None
    try:
        label = le.load_label(drug)
    except (ValueError, OSError, KeyError):
        return None
    consistency = _report(*entry['consistency_report'])
    outside = _report(*entry['outside_report'])
    if not consistency or not outside:
        return None
    selected = consistency['decision'].get('selected_set')
    if not consistency['decision'].get('eligible') or not selected or not outside['decision'].get('curve_consistent_with_li_2017'):
        return None
    params = le.parameter_sets(label)[selected]
    reported = consistency['parameter_sets'][selected]
    if abs(params['cl_f_l_h'] - reported['cl_f_l_h']) > 1e-12 or abs(params['v_f_l'] - reported['v_f_l']) > 1e-12:
        return None
    return entry, label, consistency, outside, selected, params


def available():
    """Drug ids with a shown label-based curve. Used by the capability levels."""
    return {drug: REGISTRY[drug]['label'] for drug in REGISTRY if _verified(drug)}


def _curve(times, dose, tau, cl, v, ka, steady):
    if steady:
        return [le.steady_state_ng_ml(t, dose, tau, cl, v, ka) for t in times]
    return [sum(le.single_dose_ng_ml(t - n * tau, dose, cl, v, ka) for n in range(int(t // tau) + 1)) for t in times]


def scenarios(label):
    out = []
    for key, s in label['scenarios'].items():
        out.append({'id': key, 'label': SCENARIO_LABELS.get(key, key.replace('_', ' ')), 'auc_fold': s['auc_fold'],
                    'quote': s['quote'] if not s['quote'].startswith('same sentence') else
                    label['scenarios'][s['quote'].split('same sentence as ')[1]]['quote'],
                    'location': s['location'], 'study_population': s['study_population'],
                    'not_myeloma_patients': not s['study_population'].startswith('patients'),
                    'label_dose_modification': s.get('label_dose_modification'),
                    'selectable': key not in NOT_SCENARIOS, 'why_not_selectable': NOT_SCENARIOS.get(key)})
    return out


def view(drug, scenario=None):
    """Everything the page shows. Raises KeyError for an unknown drug or scenario, ValueError if not verifiable."""
    if drug not in REGISTRY:
        raise KeyError(drug)
    verified = _verified(drug)
    if verified is None:
        raise ValueError('Label-based curve withheld: a pinned source or check report is missing or changed.')
    entry, label, consistency, outside, selected, params = verified
    dose, tau = label['regimen']['dose_mg'], label['regimen']['interval_h']
    cl, vol = params['cl_f_l_h'], params['v_f_l']
    ka = le.ka_from_tmax(entry['tmax_for_ka_h'], cl / vol)
    options = scenarios(label)
    chosen = None
    if scenario:
        chosen = next((s for s in options if s['id'] == scenario and s['selectable']), None)
        if chosen is None:
            raise KeyError(scenario)
    cl_s = cl / chosen['auc_fold'] if chosen else None

    week = [round(i * 0.25, 2) for i in range(int(72 / 0.25) + 1)]
    day = [round(i * 0.1, 2) for i in range(241)]
    li_p = li_check.li_typical(li_check.load_li())
    base_ss = le.steady_state_summary(dose, tau, cl, vol, ka)
    result = {
        'drug': drug, 'label': entry['label'], 'selected_set': selected,
        'regimen': label['regimen'],
        'parameters': {'cl_f_l_h': cl, 'v_f_l': vol, 'ka_per_h': ka, 'half_life_h': 0.6931471805599453 * vol / cl,
                       'provenance': params['provenance'], 'ka_rule': f"derived from the label's Tmax ({entry['tmax_for_ka_h']:g} h, middle of 2–3 h)"},
        'label_points': {'cmax_ng_ml': label['values']['cmax_ss_mm_4mg_ng_ml']['value'],
                         'auc_ng_h_ml': label['values']['auc_tau_ss_mm_4mg_ng_h_ml']['value'],
                         'tmax_range_h': label['values']['tmax_h']['range'],
                         'quote': label['values']['auc_tau_ss_mm_4mg_ng_h_ml']['quote']},
        'steady_state': base_ss,
        'curves': {'first_72_h': {'times_h': week, 'base': _curve(week, dose, tau, cl, vol, ka, False)},
                   'steady_state_day': {'times_h': day, 'base': _curve(day, dose, tau, cl, vol, ka, True),
                                        'li_2017_typical': [li_check.li_steady_state_ng_ml(t, li_p) for t in day]}},
        'scenarios': options, 'scenario': chosen,
        'checks': {
            'consistency': {'path': entry['consistency_report'][0], 'sha256': entry['consistency_report'][1],
                            'report_sha256': consistency['report_sha256'],
                            'rows': {c: consistency['parameter_sets'][selected]['primary']['checks'][c] for c in le.PASS_FAIL},
                            'rejected_set': {n: {'passes': s['primary']['passes_c1_to_c4'],
                                                 'auc': s['primary']['checks']['C4_steady_state_auc']['model'],
                                                 'cmax': s['primary']['checks']['C3_steady_state_cmax']['model']}
                                             for n, s in consistency['parameter_sets'].items() if n != selected},
                            'informative': consistency['which_checks_are_informative']},
            'outside': {'path': entry['outside_report'][0], 'sha256': entry['outside_report'][1],
                        'report_sha256': outside['report_sha256'], 'source': entry['outside_source'],
                        'primary': outside['primary'], 'ratios': outside['typical_curve_ratios'],
                        'dialysis': outside['dialysis_scenario'], 'classification': outside['classification'],
                        'ka_sensitivity': outside['descriptive']['ka_sensitivity']}},
        'label_source': label['source'],
        'clinical_prediction_validated': False,
    }
    if chosen:
        result['scenario_steady_state'] = le.steady_state_summary(dose, tau, cl_s, vol, ka)
        result['curves']['first_72_h']['scenario'] = _curve(week, dose, tau, cl_s, vol, ka, False)
        result['curves']['steady_state_day']['scenario'] = _curve(day, dose, tau, cl_s, vol, ka, True)
    return result
