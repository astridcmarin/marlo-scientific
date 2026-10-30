"""Simulation 3.2a: the Gupta 2017 ixazomib population PK model (Clin Pharmacokinet 2017;56:1355-1368).

Three-compartment disposition (central V2, peripherals V3 and V4, elimination CL from the central compartment)
with first-order oral absorption (Ka) after a lag; absolute bioavailability F. The only covariate is body surface
area on V4. Parameters come from the pinned extract (Table 3); see ixazomib_pk_gupta_2017_extract_v1.json for the
inferred covariate form and the open questions. Concentrations are total plasma ixazomib.

Units: dose in mg, volumes in L, clearances in L/h, time in h; concentrations in ng/mL (= ug/L).

Two solutions are provided. `concentration` is the closed form used for simulation: the unit-impulse response of
the disposition system is a sum of three exponentials whose rates are the roots of the characteristic cubic, and
oral input is that response convolved with first-order absorption. `derivatives` is the differential system, used
only to check the closed form numerically.
"""
import hashlib
import json
import math
from pathlib import Path

EXTRACT_PATH = Path(__file__).parent / 'data' / 'ixazomib_pk_gupta_2017_extract_v1.json'
EXTRACT_SHA256 = 'd4fe97e4a8659b993541c9bd960ff6d6c519b4fe913b3ad27de84ce894b233bf'
MODEL_VERSION = 'ixazomib-pk-gupta-2017-v1.0'
REFERENCE_BSA_M2 = 1.87


def load_extract(path=EXTRACT_PATH):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXTRACT_SHA256:
        raise ValueError('Ixazomib model extract is missing or changed; nothing was computed.')
    return json.loads(raw)


def typical_parameters(extract=None, bsa_m2=REFERENCE_BSA_M2):
    """Typical-value parameters for a patient of the given BSA (V4 = 205 x (BSA / 1.87)^2.06)."""
    fx = (extract or load_extract())['parameters']['fixed_effects']
    v = {k: fx[k]['value'] for k in fx}
    return {'ka': v['ka_per_h'], 'cl': v['cl_l_h'], 'v2': v['v2_l'], 'f': v['f'], 'q3': v['q3_l_h'], 'v3': v['v3_l'],
            'q4': v['q4_l_h'], 'v4': v['v4_l'] * (bsa_m2 / REFERENCE_BSA_M2) ** v['bsa_exponent_on_v4'], 'tlag': v['tlag_h']}


def disposition_rates(p):
    """The three disposition rate constants (1/h), largest first: roots of
    lambda^3 - a2 lambda^2 + a1 lambda - a0 = 0 for the central/peripheral system."""
    k10, k12, k21, k13, k31 = p['cl'] / p['v2'], p['q3'] / p['v2'], p['q3'] / p['v3'], p['q4'] / p['v2'], p['q4'] / p['v4']
    a2 = k10 + k12 + k13 + k21 + k31
    a1 = k10 * k21 + k10 * k31 + k12 * k31 + k13 * k21 + k21 * k31
    a0 = k10 * k21 * k31
    # Depressed cubic by lambda = x + a2/3; three real roots (trigonometric form).
    m = a1 - a2 * a2 / 3.0
    n = -2.0 * a2 ** 3 / 27.0 + a2 * a1 / 3.0 - a0
    r = math.sqrt(-m / 3.0)
    phi = math.acos(max(-1.0, min(1.0, 3.0 * n / (2.0 * m * r))))
    roots = [a2 / 3.0 + 2.0 * r * math.cos(phi / 3.0 - 2.0 * math.pi * j / 3.0) for j in range(3)]
    return sorted(roots, reverse=True)


def impulse_coefficients(p, rates=None):
    """Coefficients a_i (1/L) of the central concentration after a unit amount in the central compartment:
    C(t) = sum a_i exp(-lambda_i t)."""
    rates = rates or disposition_rates(p)
    k21, k31 = p['q3'] / p['v3'], p['q4'] / p['v4']
    out = []
    for i, li in enumerate(rates):
        lj, lk = (rates[j] for j in range(3) if j != i)
        out.append((k21 - li) * (k31 - li) / ((lj - li) * (lk - li)) / p['v2'])
    return out


def concentration(times_h, dose_mg, p):
    """Total plasma concentration (ng/mL) after one oral dose at t = 0 (closed form)."""
    rates = disposition_rates(p)
    coef = impulse_coefficients(p, rates)
    amount = p['f'] * dose_mg * 1000.0          # ug absorbed; ug/L = ng/mL
    ka = p['ka']
    out = []
    for t in times_h:
        tau = t - p['tlag']
        if tau <= 0:
            out.append(0.0)
            continue
        eka = math.exp(-ka * tau)
        c = 0.0
        for a, lam in zip(coef, rates):
            c += a * (math.exp(-lam * tau) - eka) / (ka - lam)
        out.append(amount * ka * c)
    return out


def auc_infinity(dose_mg, p):
    return p['f'] * dose_mg * 1000.0 / p['cl']


def auc_to(t_end_h, dose_mg, p):
    """Exact AUC (h.ng/mL) from the dose to t_end_h after one oral dose (closed-form integral)."""
    tau = t_end_h - p['tlag']
    if tau <= 0:
        return 0.0
    rates = disposition_rates(p)
    coef = impulse_coefficients(p, rates)
    ka = p['ka']
    return p['f'] * dose_mg * 1000.0 * ka * math.fsum(
        a / (ka - lam) * ((1 - math.exp(-lam * tau)) / lam - (1 - math.exp(-ka * tau)) / ka) for a, lam in zip(coef, rates))


def derivatives(a, p):
    """dA/dt for amounts (ug) in depot, central, peripheral 1, peripheral 2; also returns the elimination rate."""
    a1, a2, a3, a4 = a
    c2 = a2 / p['v2']
    elim = p['cl'] * c2
    d1 = -p['ka'] * a1
    d3 = p['q3'] * (c2 - a3 / p['v3'])
    d4 = p['q4'] * (c2 - a4 / p['v4'])
    d2 = p['ka'] * a1 - elim - d3 - d4
    return (d1, d2, d3, d4), elim


def integrate(times_h, dose_mg, p, step_h=0.001):
    """Fourth-order Runge-Kutta solution (for checking only). The absorbed dose F x dose enters the depot at the lag
    time. Returns concentrations at times_h and, at each, the amounts and the cumulative amount eliminated."""
    state = [p['f'] * dose_mg * 1000.0, 0.0, 0.0, 0.0]
    eliminated = 0.0
    t = p['tlag']
    results = []
    for target in times_h:
        if target <= p['tlag']:
            results.append({'t': target, 'conc': 0.0, 'amounts': [0.0] * 4, 'eliminated': 0.0})
            continue
        while t < target - 1e-12:
            h = min(step_h, target - t)
            k1, e1 = derivatives(state, p)
            s2 = [x + h / 2 * d for x, d in zip(state, k1)]
            k2, e2 = derivatives(s2, p)
            s3 = [x + h / 2 * d for x, d in zip(state, k2)]
            k3, e3 = derivatives(s3, p)
            s4 = [x + h * d for x, d in zip(state, k3)]
            k4, e4 = derivatives(s4, p)
            state = [x + h / 6 * (d1 + 2 * d2 + 2 * d3 + d4) for x, d1, d2, d3, d4 in zip(state, k1, k2, k3, k4)]
            eliminated += h / 6 * (e1 + 2 * e2 + 2 * e3 + e4)
            t += h
        results.append({'t': target, 'conc': state[1] / p['v2'], 'amounts': list(state), 'eliminated': eliminated})
    return results
