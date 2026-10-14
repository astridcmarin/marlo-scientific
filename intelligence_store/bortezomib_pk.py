"""Simulation 3.0b: bortezomib plasma concentrations from the Lignet 2022 adult PK model.

Three-compartment mammillary model, linear, IV bolus into the central compartment. Parameters are per m2
(Table 1, scaled from Hanley 2017); dose is per m2, so body surface area cancels and concentration depends
only on the dose in mg/m2. The exact solution is a sum of three exponentials (roots of the characteristic
cubic); it is checked against an independent RK4 integration. This model has a single clearance; the
bortezomib label reports lower clearance after repeated dosing, which this model cannot show.
"""
import math
from pathlib import Path

from .bortezomib_platelet_evidence import load_model_extract
from .covariate_estimation import _load_pinned

STANDARD_CYCLE_DAYS = (1, 4, 8, 11)
CYCLE_LENGTH_DAYS = 21


def rate_constants(extract=None):
    p = (extract or load_model_extract())['pk_model']['parameters_per_m2']
    v1 = p['central_volume_l_m2']
    return {'k10': p['clearance_l_h_m2'] / v1, 'k12': p['q2_l_h_m2'] / v1, 'k21': p['q2_l_h_m2'] / p['peripheral_volume_2_l_m2'],
            'k13': p['q3_l_h_m2'] / v1, 'k31': p['q3_l_h_m2'] / p['peripheral_volume_3_l_m2'], 'v1_l_m2': v1,
            'cl_l_h_m2': p['clearance_l_h_m2']}


def disposition_rates(k):
    """Roots (alpha > beta > gamma > 0) of l^3 - a2 l^2 + a1 l - a0 for the three-compartment mammillary model."""
    a2 = k['k10'] + k['k12'] + k['k13'] + k['k21'] + k['k31']
    a1 = k['k10'] * k['k21'] + k['k10'] * k['k31'] + k['k21'] * k['k31'] + k['k21'] * k['k13'] + k['k31'] * k['k12']
    a0 = k['k10'] * k['k21'] * k['k31']
    # Trigonometric solution of the depressed cubic; all three roots are real and positive here.
    p = a1 - a2 * a2 / 3.0
    q = -2.0 * a2 ** 3 / 27.0 + a2 * a1 / 3.0 - a0
    r = math.sqrt(-p / 3.0)
    phi = math.acos(max(-1.0, min(1.0, 3.0 * q / (2.0 * p * r))))
    roots = sorted((2.0 * r * math.cos((phi - 2.0 * math.pi * j) / 3.0) + a2 / 3.0 for j in range(3)), reverse=True)
    for root in roots:
        if not abs(((root - a2) * root + a1) * root - a0) <= 1e-9 * max(1.0, a0, a1 * root):
            raise ValueError('Characteristic cubic root check failed.')
    return roots


def unit_bolus_coefficients(k):
    """Coefficients (per L/m2) of C(t) after 1 mg/m2: sum_i c_i exp(-lambda_i t)."""
    lams = disposition_rates(k)
    coeffs = []
    for i, lam in enumerate(lams):
        others = [l for j, l in enumerate(lams) if j != i]
        coeffs.append((k['k21'] - lam) * (k['k31'] - lam) / ((others[0] - lam) * (others[1] - lam)) / k['v1_l_m2'])
    return list(zip(coeffs, lams))


def standard_regimen(dose_mg_m2=1.3, cycles=1):
    """IV bolus times (h) on days 1, 4, 8, 11 of 21-day cycles; day 1 = time 0."""
    return [((cycle * CYCLE_LENGTH_DAYS + day - 1) * 24.0, dose_mg_m2) for cycle in range(cycles) for day in STANDARD_CYCLE_DAYS]


def concentration_ng_ml(t_h, events, terms):
    """Plasma concentration (ng/mL) at time t; a dose at exactly t is counted (post-dose value)."""
    return 1000.0 * math.fsum(dose * c * math.exp(-lam * (t_h - start))
                              for start, dose in events if t_h >= start for c, lam in terms)


def concentration_curve(events, times, extract=None):
    terms = unit_bolus_coefficients(rate_constants(extract))
    return [concentration_ng_ml(t, events, terms) for t in times]


def rk4_concentration(events, times, step_h=0.001, extract=None):
    """Independent check: integrate the amounts (mg/m2) with fixed-step RK4, applying boluses at their times."""
    k = rate_constants(extract)
    def deriv(a):
        a1, a2, a3 = a
        return (-(k['k10'] + k['k12'] + k['k13']) * a1 + k['k21'] * a2 + k['k31'] * a3,
                k['k12'] * a1 - k['k21'] * a2, k['k13'] * a1 - k['k31'] * a3)
    amounts, t, out = [0.0, 0.0, 0.0], 0.0, []
    pending = sorted(events)
    for target in times:
        while True:
            while pending and pending[0][0] <= t + 1e-12:
                amounts[0] += pending.pop(0)[1]
            stop = min([target] + [e[0] for e in pending])
            if t >= stop - 1e-12:
                break
            h = min(step_h, stop - t)
            s1 = deriv(amounts)
            s2 = deriv([a + h / 2 * d for a, d in zip(amounts, s1)])
            s3 = deriv([a + h / 2 * d for a, d in zip(amounts, s2)])
            s4 = deriv([a + h * d for a, d in zip(amounts, s3)])
            amounts = [a + h / 6 * (d1 + 2 * d2 + 2 * d3 + d4) for a, d1, d2, d3, d4 in zip(amounts, s1, s2, s3, s4)]
            t += h
        while pending and pending[0][0] <= target + 1e-12:
            amounts[0] += pending.pop(0)[1]
        out.append(1000.0 * amounts[0] / k['v1_l_m2'])
    return out


def single_dose_summary(dose_mg_m2=1.3, extract=None):
    k = rate_constants(extract)
    terms = unit_bolus_coefficients(k)
    return {'dose_mg_m2': dose_mg_m2,
            'c0_ng_ml': 1000.0 * dose_mg_m2 / k['v1_l_m2'],
            'c_5min_ng_ml': concentration_ng_ml(5 / 60, [(0.0, dose_mg_m2)], terms),
            'auc_0_inf_ng_h_ml': 1000.0 * dose_mg_m2 * math.fsum(c / lam for c, lam in terms),
            'auc_from_clearance_ng_h_ml': 1000.0 * dose_mg_m2 / k['cl_l_h_m2'],
            'half_lives_h': [math.log(2) / lam for _, lam in terms],
            'clearance_for_1_62_m2_l_h': k['cl_l_h_m2'] * 1.62}


LABEL_PATH = Path(__file__).parent / 'data' / 'bortezomib_label_pk_v1.json'
LABEL_SHA256 = 'c82d910e29a9ac0e6b60a33e47608c39f014bb0ca0589152ddf014d261d0938a'
ADULT_BSA_M2 = 1.62


def load_label_reference(path=LABEL_PATH):
    return _load_pinned(path, LABEL_SHA256, 'label-pk-reference-v1', 'Bortezomib label PK reference')


def compare_with_label(extract=None):
    """Model quantities beside the label ranges; descriptive placement only, no acceptance limits."""
    label = load_label_reference()['values']
    k = rate_constants(extract)
    p = (extract or load_model_extract())['pk_model']['parameters_per_m2']
    terms = unit_bolus_coefficients(k)
    clearance = k['cl_l_h_m2'] * ADULT_BSA_M2
    vss = p['central_volume_l_m2'] + p['peripheral_volume_2_l_m2'] + p['peripheral_volume_3_l_m2']
    terminal = math.log(2) / min(lam for _, lam in terms)
    def place(value, bounds):
        lo, hi = bounds
        return 'below' if value < lo else 'above' if value > hi else 'inside'
    rows = [
        {'quantity': 'terminal_half_life_h', 'model': terminal,
         'label': label['terminal_half_life_multiple_dosing_1_3_h']['range'],
         'placement': place(terminal, label['terminal_half_life_multiple_dosing_1_3_h']['range'])},
        {'quantity': 'volume_of_distribution_l_m2', 'model': vss, 'label': label['volume_of_distribution_l_m2']['range'],
         'placement': place(vss, label['volume_of_distribution_l_m2']['range'])},
        {'quantity': 'clearance_repeat_dose_l_h', 'model': clearance, 'label': label['clearance_subsequent_doses_l_h']['range'],
         'placement': place(clearance, label['clearance_subsequent_doses_l_h']['range'])},
        {'quantity': 'clearance_first_dose_l_h', 'model': clearance, 'label': label['clearance_first_dose_l_h']['range'],
         'placement': place(clearance, label['clearance_first_dose_l_h']['range']),
         'fold_difference': label['clearance_first_dose_l_h']['range'][0] / clearance}]
    c0 = concentration_ng_ml(0.0, [(0.0, 1.3)], terms)
    c5 = concentration_ng_ml(5 / 60, [(0.0, 1.3)], terms)
    rows.append({'quantity': 'early_concentration_1_3_mg_m2_ng_ml', 'model': {'at_0_min': c0, 'at_5_min': c5},
                 'label': {'first_dose_cmax': label['cmax_first_dose_1_3_ng_ml']['value'],
                           'subsequent_cmax': label['cmax_subsequent_doses_1_3_ng_ml']['range']},
                 'placement': 'not_comparable_sampling_time_unstated'})
    return {'clearance_assumes_bsa_m2': ADULT_BSA_M2, 'rows': rows,
            'reading': ('The model matches repeat-dose disposition (terminal half-life, distribution volume, clearance at the '
                        'lower edge) but has one clearance, about 7-fold lower than the label first-dose clearance; first-dose '
                        'exposure in cycle 1 is therefore overstated.')}
