"""Phase 3.1e (pomalidomide) and 3.1h (dexamethasone): what the platform may show for a drug at the capability level *Label-based exposure*.

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
from . import label_exposure_single_dose as sd

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
        'kind': 'steady_state_oral',
    },
    'dexamethasone': {
        'label': 'Dexamethasone',
        'consistency_report': ('docs/verification/label_exposure_dexamethasone_consistency_v1.json',
                               '7fe9506f01e07568ba161ab25a67ef65196c5190e3f7f1f5bb5a2f1b97620a14'),
        'outside_report': ('docs/verification/label_exposure_dexamethasone_outside_check_v1.json',
                           '931d8ee532deda19ee242e9a13658cad156e73aae598a8f32008a81a13e84add'),
        'outside_source': {'citation': 'Neofordex EPAR public assessment report, EMA/CHMP/6613/2016 (studies CC-5013-MM-017 and CPA-402-11).',
                           'url': 'https://www.ema.europa.eu/en/medicines/human/EPAR/neofordex'},
        'tmax_for_ka_h': 1.0,
        'kind': 'single_dose_oral',
        'doses_mg': (20, 40),
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
    'itraconazole_strong_cyp3a4_inhibitor': 'With itraconazole (strong CYP3A4 inhibitor)',
    'aprepitant_moderate_cyp3a4_inhibitor': 'With aprepitant (moderate CYP3A4 inhibitor)',
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
    single = entry['kind'] == 'single_dose_oral'
    try:
        label = sd.load_label() if single else le.load_label(drug)
    except (ValueError, OSError, KeyError):
        return None
    consistency = _report(*entry['consistency_report'])
    outside = _report(*entry['outside_report'])
    if not consistency or not outside:
        return None
    selected = consistency['decision'].get('selected_set')
    outside_ok = outside['decision'].get('curve_consistent_with_outside_data' if single else 'curve_consistent_with_li_2017')
    if not consistency['decision'].get('eligible') or not selected or not outside_ok:
        return None
    if single:
        params = sd.parameter_set(label)
        reported = consistency['parameter_set']
    else:
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
                    'auc_unchanged': s['auc_fold'] == 1.0 and 'cmax_fold' in s,
                    'label_dose_modification': s.get('label_dose_modification'),
                    'selectable': key not in NOT_SCENARIOS, 'why_not_selectable': NOT_SCENARIOS.get(key)})
    return out


def view(drug, scenario=None, dose=None):
    """Everything the page shows. Raises KeyError for an unknown drug, scenario or dose, ValueError if not verifiable."""
    if drug not in REGISTRY:
        raise KeyError(drug)
    verified = _verified(drug)
    if verified is None:
        raise ValueError('Label-based curve withheld: a pinned source or check report is missing or changed.')
    if REGISTRY[drug]['kind'] == 'single_dose_oral':
        return _single_dose_view(drug, verified, scenario, dose)
    if dose is not None:
        raise KeyError(dose)
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


def _single_dose_view(drug, verified, scenario, dose):
    """3.1h: one oral dose (dexamethasone). The label states dose proportionality, so 40 mg is the 20 mg curve doubled."""
    entry, label, consistency, outside, selected, params = verified
    dose = entry['doses_mg'][0] if dose is None else dose
    if dose not in entry['doses_mg']:
        raise KeyError(dose)
    cl, vol = params['cl_f_l_h'], params['v_f_l']
    ka = le.ka_from_tmax(entry['tmax_for_ka_h'], cl / vol)
    options = [dict(o, selectable=o['selectable'] and not o['auc_unchanged'],
                    why_not_selectable=o['why_not_selectable'] or ('Changes the peak but not total exposure; shown as text only.'
                                                                  if o['auc_unchanged'] else None))
               for o in scenarios(label)]
    chosen = None
    if scenario:
        chosen = next((o for o in options if o['id'] == scenario and o['selectable']), None)
        if chosen is None:
            raise KeyError(scenario)
    times = [round(i * 0.05, 2) for i in range(int(24 / 0.05) + 1)]
    base = [le.single_dose_ng_ml(t, dose, cl, vol, ka) for t in times]
    summary = sd.single_dose_summary(dose, cl, vol, ka)
    v = label['values']
    scale = dose / label['regimen']['dose_mg']
    primary = outside['primary_mm017_auc_inf_40mg']
    cpa = outside['secondary']['cpa_402_11_20mg']
    mm_cmax = outside['secondary']['mm017_cmax_40mg']
    observed_points = ([{'source': 'Myeloma patients, MM-017 (6 Japanese patients), geometric mean', 'cmax': mm_cmax['observed'],
                         'auc': primary['observed'], 'tmax': outside['descriptive']['mm017_day2']['tmax_h_median_range'][0]}]
                       if dose == 40 else
                       [{'source': 'Healthy volunteers, NEOFORDEX tablet (CPA-402-11), arithmetic mean', 'cmax': cpa['test']['cmax']['observed'],
                         'auc': cpa['test']['auc_inf']['observed'], 'tmax': cpa['test']['tmax_observed_median_range_h'][0]},
                        {'source': 'Healthy volunteers, reference tablet (CPA-402-11), arithmetic mean', 'cmax': cpa['reference']['cmax']['observed'],
                         'auc': cpa['reference']['auc_inf']['observed'], 'tmax': cpa['reference']['tmax_observed_median_range_h'][0]}])
    result = {
        'kind': 'single_dose_oral', 'drug': drug, 'label': entry['label'], 'selected_set': selected,
        'dose_mg': dose, 'doses_mg': list(entry['doses_mg']), 'regimen': label['regimen'],
        'population_note': consistency['population_note'],
        'parameters': {'cl_f_l_h': cl, 'v_f_l': vol, 'ka_per_h': ka, 'half_life_h': 0.6931471805599453 * vol / cl,
                       'provenance': params['provenance'], 'ka_rule': f"derived from the label's median Tmax ({entry['tmax_for_ka_h']:g} h)"},
        'linearity_quote': label['linearity']['quote'],
        'label_points': {'cmax_ng_ml': v['cmax_single_20mg_ng_ml']['value'] * scale, 'auc_ng_h_ml': v['auc_inf_single_20mg_ng_h_ml']['value'] * scale,
                         'tmax_h': v['tmax_h']['value'], 'tmax_range_h': v['tmax_h']['range'], 'scaled_from_20_mg': dose != 20,
                         'quote': v['cmax_single_20mg_ng_ml']['quote']},
        'observed_points': observed_points,
        'summary': summary,
        'curves': {'times_h': times, 'base': base},
        'remaining_fraction_at_24_h': summary['remaining_fraction_at_24_h'],
        'scenarios': options, 'scenario': chosen,
        'checks': {
            'consistency': {'path': entry['consistency_report'][0], 'sha256': entry['consistency_report'][1],
                            'rows': {c: consistency['parameter_set']['primary']['checks'][c] for c in sd.PASS_FAIL},
                            'tmax_sensitivity': consistency['parameter_set']['tmax_sensitivity'],
                            'informative': consistency['which_checks_are_informative']},
            'outside': {'path': entry['outside_report'][0], 'sha256': entry['outside_report'][1], 'source': entry['outside_source'],
                        'primary': primary, 'mm017_cmax': mm_cmax, 'cpa': cpa,
                        'mm017_cl_f_l_h': outside['descriptive']['mm017_day2']['cl_f_l_h_gm'],
                        'mm017_day12': outside['descriptive']['mm017_day12_with_lenalidomide'],
                        'spoorenberg': outside['descriptive']['spoorenberg_2014_scaled_to_20mg']}},
        'label_source': label['source'],
        'clinical_prediction_validated': False,
    }
    if chosen:
        cl_s = cl / chosen['auc_fold']
        result['curves']['scenario'] = [le.single_dose_ng_ml(t, dose, cl_s, vol, ka) for t in times]
        result['scenario_summary'] = sd.single_dose_summary(dose, cl_s, vol, ka)
    return result
