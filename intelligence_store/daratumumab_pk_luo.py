"""Simulation 3.2b: the Luo 2021 daratumumab population PK model (J Clin Pharmacol 2021;61:614-627), intravenous part.

Two compartments (central V1, peripheral V2, exchange Q). Drug leaves the central compartment by two parallel routes:
- a linear clearance CL, the non-specific IgG catabolism every antibody undergoes;
- a saturable Michaelis-Menten route, Vmax C / (Km + C), which represents binding to CD38 on myeloma and other cells
  followed by internalisation (target-mediated drug disposition). At low concentrations it acts like an extra
  clearance Vmax / Km; once the targets are saturated (C >> Km = 2.56 ug/mL) it removes at most Vmax per hour.
Vmax declines over time (KDES), read as Vmax exp(-KDES t): as treatment kills CD38-positive cells, there is less
target to clear the drug. See daratumumab_pk_luo_2021_extract_v1.json for the open readings.

Units: mg, L, h; concentration mg/L = ug/mL.
"""
import hashlib
import json
import math
from pathlib import Path

EXTRACT_PATH = Path(__file__).parent / 'data' / 'daratumumab_pk_luo_2021_extract_v1.json'
EXTRACT_SHA256 = '8c68ddb7a849ce00a6340e0a7b4ec58ecf9e720491be8b55f1a47c774293d4f6'
MODEL_VERSION = 'daratumumab-pk-luo-2021-v1.0'
REFERENCE_WEIGHT_KG = 78.6
REFERENCE_ALBUMIN_G_L = 37.0


def load_extract(path=EXTRACT_PATH):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXTRACT_SHA256:
        raise ValueError('Daratumumab model extract is missing or changed; nothing was computed.')
    return json.loads(raw)


def typical_parameters(extract=None, weight_kg=REFERENCE_WEIGHT_KG, albumin_g_l=REFERENCE_ALBUMIN_G_L, igg=False, male=False,
                       sex_factor_on='male'):
    """Typical values for a patient with these covariates (extract covariate_equations_read)."""
    fx = (extract or load_extract())['parameters']['fixed_effects']
    v = {k: fx[k]['value'] for k in fx}
    cl = (v['cl_l_h'] * (weight_kg / REFERENCE_WEIGHT_KG) ** v['wt_exponent_on_cl']
          * (albumin_g_l / REFERENCE_ALBUMIN_G_L) ** v['alb_exponent_on_cl'] * ((1 + v['igg_shift_on_cl']) if igg else 1.0))
    sex_applies = male if sex_factor_on == 'male' else not male
    v1 = v['v1_l'] * (weight_kg / REFERENCE_WEIGHT_KG) ** v['wt_exponent_on_v1'] * ((1 + v['sex_shift_on_v1']) if sex_applies else 1.0)
    return {'cl': cl, 'v1': v1, 'v2': v['v2_l'], 'q': v['q_l_h'], 'vmax': v['vmax_mg_h'], 'km': v['km_ug_ml'], 'kdes': v['kdes_per_h']}


def _rhs(p):
    cl, v1, v2, q, vmax, km, kdes = p['cl'], p['v1'], p['v2'], p['q'], p['vmax'], p['km'], p['kdes']

    def f(t, a1, a2, rate):
        c = a1 / v1
        lin = cl * c
        sat = vmax * math.exp(-kdes * t) * c / (km + c)
        dist = q * (c - a2 / v2)
        return rate - lin - sat - dist, dist, c, lin, sat
    return f


def simulate(p, infusions, output_times, fine_step_h=0.05, coarse_step_h=1.0, fine_after_end_h=24.0, until_fraction_of_max=None):
    """Integrate with fixed-step RK4. infusions: list of (start_h, amount_mg, duration_h). Returns concentrations at
    output_times, the AUC (ug.h/mL) at each output time, and the amounts removed by each route.

    If until_fraction_of_max is set, integration continues past the last output time, in 24 h blocks, until the
    concentration is below that fraction of its maximum; the result then includes auc_infinity (with a log-linear
    tail C / k over the last 24 h)."""
    f = _rhs(p)
    fine = [(s, s + d + fine_after_end_h) for s, _, d in infusions]
    bps = sorted({0.0, *output_times, *(s for s, _, _ in infusions), *(s + d for s, _, d in infusions),
                  *(s + d + fine_after_end_h for s, _, d in infusions)})
    state = [0.0, 0.0, 0.0, 0.0, 0.0]          # A1, A2, AUC, removed linear, removed saturable
    cmax = 0.0
    out = {}

    def rate_at(t):
        return sum(a / d for s, a, d in infusions if s <= t < s + d)

    def advance(t0, t1):
        nonlocal state, cmax
        span = t1 - t0
        if span <= 0:
            return
        is_fine = any(a <= t0 and t1 <= b + 1e-9 for a, b in fine)
        n = max(1, math.ceil(span / (fine_step_h if is_fine else coarse_step_h) - 1e-9))
        h = span / n
        rate = rate_at(t0 + span / 2)
        t = t0
        a1, a2, auc, rl, rs = state
        for _ in range(n):
            k1 = f(t, a1, a2, rate)
            k2 = f(t + h / 2, a1 + h / 2 * k1[0], a2 + h / 2 * k1[1], rate)
            k3 = f(t + h / 2, a1 + h / 2 * k2[0], a2 + h / 2 * k2[1], rate)
            k4 = f(t + h, a1 + h * k3[0], a2 + h * k3[1], rate)
            a1 += h / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
            a2 += h / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
            auc += h / 6 * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2])
            rl += h / 6 * (k1[3] + 2 * k2[3] + 2 * k3[3] + k4[3])
            rs += h / 6 * (k1[4] + 2 * k2[4] + 2 * k3[4] + k4[4])
            t += h
            cmax = max(cmax, a1 / p['v1'])
        state = [a1, a2, auc, rl, rs]

    t = 0.0
    last_output = max(output_times)
    for b in bps:
        if b > last_output:
            break
        advance(t, b)
        t = b
        if b in output_times:
            out[b] = {'conc': state[0] / p['v1'], 'auc': state[2]}
    result = {'at': out, 'removed_linear_mg': state[3], 'removed_saturable_mg': state[4],
              'amount_central_mg': state[0], 'amount_peripheral_mg': state[1], 'time_h': t}
    if until_fraction_of_max:
        end_inf = max(s + d + fine_after_end_h for s, _, d in infusions)
        if t < end_inf:
            advance(t, end_inf)
            t = end_inf
        while True:
            c_before = state[0] / p['v1']
            advance(t, t + 24.0)
            t += 24.0
            c = state[0] / p['v1']
            if c < until_fraction_of_max * cmax or t > 20000:
                break
        k = math.log(c_before / c) / 24.0
        result.update(auc_infinity=state[2] + c / k, tail_fraction=(c / k) / (state[2] + c / k), integrated_to_h=t,
                      removed_linear_mg=state[3], removed_saturable_mg=state[4],
                      amount_central_mg=state[0], amount_peripheral_mg=state[1])
    result['cmax_during'] = cmax
    return result
