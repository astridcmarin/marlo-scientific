"""Which reading of the Kim 2026 CL/F equation reproduces the paper's own target-attainment results?

The printed equation (p.10) is  CL/F = 8.52*exp[0.0131*(eGFR-46.92)] + 1.1*(BSA-1.64), with the BSA
term outside the exponential. The Discussion (p.17) reports eight probabilities of target attainment
(PTA, total AUC24 within 1615.5-2692.5 ng*h/mL) for BSA and dose combinations. This script rebuilds
that simulation under three readings of the equation and compares.

Approximations (individual covariates are not published): eGFR is drawn from a triangular
distribution matching each group's Table 1 median and range; the reported "BSA < 1.6" PTA range is
assigned to BSA 1.4 and 1.5; omega_CL = 0.189. These limit how closely any form can match, but not
the direction of the dose-escalation results, which is what separates the readings.

Stdlib only; deterministic. Prints JSON.
    python scripts/assess_kim_cl_equation_form.py [--n 20000] [--seed 7]
"""
import argparse
import json
import math
import random

FU = 0.614
OMEGA_CL = 0.189
TARGET = (1615.5, 2692.5)
FORMS = {
    'linear_multiplicative': lambda e, b: 8.52 * math.exp(0.0131 * (e - 46.92)) * (1 + 1.1 * (b - 1.64)),
    'exponential': lambda e, b: 8.52 * math.exp(0.0131 * (e - 46.92) + 1.1 * (b - 1.64)),
    'additive_as_printed': lambda e, b: 8.52 * math.exp(0.0131 * (e - 46.92)) + 1.1 * (b - 1.64),
}
EGFR_TABLE1 = {'severe': (11.1, 25.2, 28.6), 'moderate': (31.3, 52.1, 59.9)}
REPORTED = [  # group, BSA, dose (mg), reported PTA (%), source sentence location
    ('severe', 2.0, 7.5, 42.5), ('severe', 2.0, 10, 70.0), ('severe', 1.4, 5, 58.9), ('severe', 1.5, 5, 69.6),
    ('moderate', 2.0, 10, 30.6), ('moderate', 2.0, 15, 65.9), ('moderate', 1.4, 7.5, 56.0), ('moderate', 1.5, 7.5, 63.8)]
ESCALATIONS = [(('severe', 2.0, 7.5), ('severe', 2.0, 10)), (('moderate', 2.0, 10), ('moderate', 2.0, 15))]


def simulate(form, group, bsa, dose, n, rng):
    lo, med, hi = EGFR_TABLE1[group]
    hits = 0
    for _ in range(n):
        clu = FORMS[form](rng.triangular(lo, hi, med), bsa) * math.exp(rng.gauss(0, OMEGA_CL))
        hits += TARGET[0] <= 1000 * dose / (clu * FU) <= TARGET[1]
    return 100 * hits / n


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--n', type=int, default=20000)
    parser.add_argument('--seed', type=int, default=7)
    args = parser.parse_args()
    report = {'schema_version': 'kim-cl-form-reconstruction-v1', 'n_per_cell': args.n, 'seed': args.seed, 'forms': {}}
    for form in FORMS:
        rng = random.Random(args.seed)
        cells = [{'group': g, 'bsa': b, 'dose_mg': d, 'reported_pta_pct': r, 'simulated_pta_pct': round(simulate(form, g, b, d, args.n, rng), 1)}
                 for g, b, d, r in REPORTED]
        lookup = {(c['group'], c['bsa'], c['dose_mg']): c['simulated_pta_pct'] for c in cells}
        direction = all(lookup[hi] > lookup[lo] for lo, hi in ESCALATIONS)
        report['forms'][form] = {'cells': cells,
                                 'mean_abs_error_pct_points': round(sum(abs(c['reported_pta_pct'] - c['simulated_pta_pct']) for c in cells) / len(cells), 1),
                                 'dose_escalation_raises_pta_as_reported': direction}
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
