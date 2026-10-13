"""Reconstruct the Hughes 2019 Table 1 creatinine-clearance distribution under candidate
Cockcroft-Gault weight bases.

Question: Hughes et al. (Br J Clin Pharmacol 2019;85:924-934) cite Cockcroft-Gault but do
not state which body weight was used. Table 1 reports both the inputs (age, sex mix, total
body weight, height, serum creatinine, FFM) and the resulting CrCl distribution. If a
virtual population matching the inputs is pushed through Cockcroft-Gault with each candidate
weight, the basis whose output matches Table 1 is the more plausible one.

This is indirect evidence from summary statistics. It cannot confirm what the authors did.

Stdlib only. Deterministic for a given seed. Prints a JSON report.

    python scripts/reconstruct_hughes_crcl_weight_basis.py [--n 100000] [--seed 20261013]
"""
import argparse
import json
import math
import random
import statistics

TABLE1 = {
    'age_years': {'mean': 58.2, 'sd': 12.8, 'range': [22, 79]},
    'total_body_weight_kg': {'mean': 88.8, 'sd': 22.7, 'range': [48, 152]},
    'height_cm': {'range': [150, 196], 'note': 'Reported SD 22.7 cm is implausible for the reported range; treated as a transcription error.'},
    'fat_free_mass_kg': {'mean': 57.7, 'sd': 12.8, 'median': 58.4, 'range': [32, 84]},
    'serum_creatinine_umol_l': {'mean': 82.8, 'sd': 21.4, 'median': 80.4, 'range': [42, 147]},
    'creatinine_clearance_ml_min': {'mean': 80.1, 'sd': 29.5, 'median': 75.5, 'range': [36, 211]},
    'male_fraction': 76 / 125,
}

SCENARIOS = {
    'base': {'height_weight_corr': 0.5, 'sex_specific_scr': False},
    'strong_height_weight_corr': {'height_weight_corr': 0.7, 'sex_specific_scr': False},
    'sex_specific_creatinine': {'height_weight_corr': 0.5, 'sex_specific_scr': True},
}

BASES = ('total_body_weight', 'ideal_body_weight_devine', 'adjusted_body_weight_0_4', 'fat_free_mass')


def lognormal_params(mean, sd):
    sigma = math.sqrt(math.log(1 + (sd / mean) ** 2))
    return math.log(mean) - sigma ** 2 / 2, sigma


def truncated(draw, lo, hi):
    while True:
        value = draw()
        if lo <= value <= hi:
            return value


def simulate(n, seed, height_weight_corr, sex_specific_scr):
    rng = random.Random(seed)
    w_mu, w_sigma = lognormal_params(TABLE1['total_body_weight_kg']['mean'], TABLE1['total_body_weight_kg']['sd'])
    s_mu, s_sigma = lognormal_params(TABLE1['serum_creatinine_umol_l']['mean'], TABLE1['serum_creatinine_umol_l']['sd'])
    rows = []
    for _ in range(n):
        male = rng.random() < TABLE1['male_fraction']
        age = truncated(lambda: rng.gauss(58.2, 12.8), 22, 79)
        # Height and weight share a latent normal factor (Gaussian copula).
        while True:
            z_h = rng.gauss(0, 1)
            z_w = height_weight_corr * z_h + math.sqrt(1 - height_weight_corr ** 2) * rng.gauss(0, 1)
            height = (177.0 if male else 163.0) + 7.0 * z_h
            weight = math.exp(w_mu + w_sigma * z_w)
            if 150 <= height <= 196 and 48 <= weight <= 152:
                break
        if sex_specific_scr:
            mu = s_mu + (0.06 if male else -0.10)
            scr = truncated(lambda: math.exp(rng.gauss(mu, s_sigma)), 42, 147)
        else:
            scr = truncated(lambda: math.exp(rng.gauss(s_mu, s_sigma)), 42, 147)
        bmi = weight / (height / 100) ** 2
        ffm = 9270 * weight / ((6680 + 216 * bmi) if male else (8780 + 244 * bmi))
        ibw = (50.0 if male else 45.5) + 2.3 * (height / 2.54 - 60)
        abw = ibw + 0.4 * (weight - ibw)
        sex_factor = 1.0 if male else 0.85
        scr_mg_dl = scr / 88.4
        dosing = {'total_body_weight': weight, 'ideal_body_weight_devine': ibw,
                  'adjusted_body_weight_0_4': abw, 'fat_free_mass': ffm}
        crcl = {basis: (140 - age) * w / (72 * scr_mg_dl) * sex_factor for basis, w in dosing.items()}
        rows.append({'ffm': ffm, 'crcl': crcl})
    return rows


def summarize(values):
    ordered = sorted(values)
    return {'mean': round(statistics.fmean(ordered), 1), 'median': round(statistics.median(ordered), 1),
            'sd': round(statistics.pstdev(ordered), 1)}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--n', type=int, default=100000)
    parser.add_argument('--seed', type=int, default=20261013)
    args = parser.parse_args()
    target = TABLE1['creatinine_clearance_ml_min']
    report = {'schema_version': 'hughes-crcl-weight-basis-reconstruction-v1', 'n_per_scenario': args.n,
              'seed': args.seed, 'table1_target': target, 'scenarios': {}}
    for index, (name, spec) in enumerate(SCENARIOS.items()):
        rows = simulate(args.n, args.seed + index, **spec)
        ffm = summarize([r['ffm'] for r in rows])
        bases = {}
        for basis in BASES:
            s = summarize([r['crcl'][basis] for r in rows])
            s['mean_error_vs_table1'] = round(s['mean'] - target['mean'], 1)
            s['median_error_vs_table1'] = round(s['median'] - target['median'], 1)
            bases[basis] = s
        best = min(bases, key=lambda b: abs(bases[b]['mean_error_vs_table1']) + abs(bases[b]['median_error_vs_table1']))
        report['scenarios'][name] = {'assumptions': spec,
                                     'fat_free_mass_calibration': {'simulated': ffm, 'table1': TABLE1['fat_free_mass_kg']},
                                     'crcl_by_weight_basis': bases, 'closest_basis': best}
    report['interpretation_limit'] = ('Reconstruction from marginal summary statistics with assumed joint structure. '
                                      'Indirect evidence only; it does not establish the authors\' method.')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
