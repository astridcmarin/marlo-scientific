"""Patient Lab 2.0e: between-subject variability band around the typical-value curve.

Virtual patients share the estimated covariates of one saved record and differ only by
random effects drawn from the published OMEGA matrix (Hughes 2019 final control stream):
(eta_CL, eta_V) jointly with their 0.862 correlation, eta_KTR independently. Each virtual
patient's curve uses the exact solution of the transit chain, verified against the
typical-value curve produced by the existing numerical solver.

What the band shows: how far patients with identical covariates are expected to spread
around the typical curve under the source model. What it leaves out: residual
(measurement/model) error, parameter-estimate uncertainty, between-occasion variability,
and any covariate effect the model does not include. Not a prediction for any individual.
"""
import copy
import json
import math
import random
from pathlib import Path

import click
from sqlalchemy.exc import SQLAlchemyError

from .patient_state import digest
from .covariate_estimation import WEIGHT_BASES, load_variability_extract, VARIABILITY_SHA256
from .estimated_pk import calculate_estimated_pk, DISEASE_CODES
from .published_transit_reference import load_structure_contract
from .treatment_requests import _read_json

SCHEMA_VERSION = 'population-educational-pk-v1'
METHOD_VERSION = 'population-educational-pk-v1.0'
DEFAULT_SEED = 20261013
DEFAULT_SUBJECTS = 1000
SUBJECT_LIMITS = (100, 5000)
PERCENTILES = (5, 25, 50, 75, 95)
TYPICAL_CURVE_TOLERANCE_NG_ML = 1e-6


def central_amount_unit_dose(t, ktr, k, stages):
    """Central amount after 1 mg into the first of `stages` equal-rate stages (exact, numerically stable).

    Laplace transform a^n / ((s+a)^n (s+k)) with a = ktr, n = stages, y = (a-k) t. Three algebraically equal forms,
    each used where it has no cancellation:
      y > 50:  (a/(a-k))^n e^(-k t) [1 - e^(-y) sum_{j<n} y^j/j!]
      0<=y<=50: (a t)^n e^(-a t)/n! * sum_m y^m n!/(n+m)!            (positive terms)
      y < 0:   (a t)^n e^(-a t)/n! * sum_m n/(n+m) z^m e^(-z)/m!, z=-y (Kummer transform; positive terms)
    The middle and last forms never divide by (a-k), so a ~ k is handled without a special case.
    """
    if t <= 0:
        return 0.0
    n = stages
    y = (ktr - k) * t
    if y > 50.0:
        term = total = 1.0
        for j in range(1, n):
            term *= y / j
            total += term
        return (ktr / (ktr - k)) ** n * math.exp(-k * t) * (1.0 - math.exp(-y) * total)
    lead = math.exp(n * math.log(ktr * t) - ktr * t - math.lgamma(n + 1))
    if y >= 0.0:
        term = total = 1.0
        m = 0
        while True:
            m += 1
            term *= y / (n + m)
            total += term
            if term <= 1e-17 * total:
                return lead * total
    z = -y
    if z > 700.0:
        raise ValueError('Elimination is too fast relative to transit for this evaluation.')
    u = math.exp(-z)
    total = u
    m = 0
    while True:
        m += 1
        u *= z / m
        piece = n / (n + m) * u
        total += piece
        if m > z and piece <= 1e-17 * total:
            return lead * total


def _percentile(sorted_values, q):
    """Linear interpolation between order statistics (Hyndman-Fan type 7)."""
    pos = (len(sorted_values) - 1) * q / 100.0
    lo = math.floor(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def _summary(values):
    ordered = sorted(values)
    return {f'p{q:02d}': _percentile(ordered, q) for q in PERCENTILES}


def _cholesky_2x2(w11, w12, w22):
    l11 = math.sqrt(w11)
    l21 = w12 / l11
    rest = w22 - l21 ** 2
    if rest <= 0:
        raise ValueError('OMEGA block is not positive definite.')
    return l11, l21, math.sqrt(rest)


def sample_random_effects(n_subjects, seed, omega):
    """Seeded draws: (eta_CL, eta_V) jointly normal, eta_KTR independent."""
    l11, l21, l22 = _cholesky_2x2(omega[0][0], omega[0][1], omega[1][1])
    if omega[0][2] != 0 or omega[1][2] != 0:
        raise ValueError('This implementation expects eta_KTR to be independent of eta_CL and eta_V.')
    sd_ktr = math.sqrt(omega[2][2])
    rng = random.Random(seed)
    draws = []
    for _ in range(n_subjects):
        z1, z2, z3 = rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)
        draws.append((l11 * z1, l21 * z1 + l22 * z2, sd_ktr * z3))
    return draws


def _diagnostics(draws, omega):
    n = len(draws)
    cols = list(zip(*draws))
    means = [math.fsum(c) / n for c in cols]
    var = [math.fsum((x - m) ** 2 for x in c) / (n - 1) for c, m in zip(cols, means)]
    cov = math.fsum((a - means[0]) * (b - means[1]) for a, b in zip(cols[0], cols[1])) / (n - 1)
    return {'specified': {'omega_cl': omega[0][0], 'omega_v': omega[1][1], 'omega_ktr': omega[2][2],
                          'corr_cl_v': omega[0][1] / math.sqrt(omega[0][0] * omega[1][1])},
            'sampled': {'omega_cl': var[0], 'omega_v': var[1], 'omega_ktr': var[2],
                        'corr_cl_v': cov / math.sqrt(var[0] * var[1]),
                        'mean_eta': means},
            'note': 'Sampling check only. Agreement within sampling error confirms the draws, not the model.'}


def calculate_population_pk(revision_id, weight_basis, request, disease_code='UNKNOWN', *,
                            n_subjects=DEFAULT_SUBJECTS, seed=DEFAULT_SEED):
    """Typical-value calculation from the saved record, plus a between-subject variability band."""
    if type(n_subjects) is not int or not SUBJECT_LIMITS[0] <= n_subjects <= SUBJECT_LIMITS[1]:
        raise ValueError(f'n_subjects must be an integer from {SUBJECT_LIMITS[0]} to {SUBJECT_LIMITS[1]}.')
    if type(seed) is not int or not 0 <= seed < 2 ** 63:
        raise ValueError('seed must be a non-negative integer.')
    typical = calculate_estimated_pk(revision_id, weight_basis, request, disease_code)
    variability = load_variability_extract()
    omega = variability['random_effects']['omega_matrix']
    report = {
        'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION,
        'revision_id': revision_id, 'weight_basis': weight_basis,
        'typical_report_sha256': typical['report_sha256'],
        'covariate_estimate': typical['covariate_estimate'],
        'variability_extract_version': variability['extract_version'], 'variability_extract_sha256': VARIABILITY_SHA256,
        'omega_matrix': copy.deepcopy(omega), 'n_subjects': n_subjects, 'seed': seed,
        'prediction_type': 'between_subject_variability_for_declared_covariates',
        'band_meaning': ('Spread of concentration among virtual patients with identical covariates, from the source '
                         'model\'s between-subject variability. Percentiles are of the virtual population at each time.'),
        'excluded': ['residual (measurement and model) error', 'uncertainty in the published parameter estimates',
                     'between-occasion variability (tested and not retained by the source authors)',
                     'covariate effects not in the model (for example food, adherence, interactions)'],
        'clinical_prediction_validated': False, 'ready_for_patient_simulation': False,
        'typical_parameters': None, 'times_h': None, 'typical_concentration_ng_ml': None,
        'band': None, 'exposure': None, 'sampling_diagnostics': None, 'verification': None,
    }
    calc = typical['calculation']
    if calc is None or not calc['points']:
        report['status'] = typical['status']
        report['simulation_status'] = 'not_run'
        report['typical_status_detail'] = ([b['code'] for b in calc['execution_blockers']] if calc else
                                           ['missing_estimator_inputs'])
        report['report_sha256'] = digest(report)
        return report

    stages = load_structure_contract()['structure']['precentral_stage_count']
    params = calc['parameters']
    cl0, v0, ktr0 = params['apparent_clearance_l_h'], params['apparent_volume_l'], params['transit_rate_h']
    times = [p['time_h'] for p in calc['points']]
    step = round(times[1] - times[0], 10)
    events = [(round(e['time']['value'] / step), e['amount']['value'])
              for e in calc['preflight_review']['treatment_request_preview']['request']['events']]

    def curve(cl, v, ktr):
        k = cl / v
        unit = [central_amount_unit_dose(t, ktr, k, stages) / v * 1000.0 for t in times]
        return [math.fsum(amount * unit[i - start] for start, amount in events if i >= start)
                for i in range(len(times))]

    typical_curve = [p['concentration_ng_ml'] for p in calc['points']]
    exact_typical = curve(cl0, v0, ktr0)
    max_diff = max(abs(a - b) for a, b in zip(exact_typical, typical_curve))
    if max_diff > TYPICAL_CURVE_TOLERANCE_NG_ML:
        raise ValueError('Exact transit solution disagrees with the numerical typical curve; no band was generated.')

    draws = sample_random_effects(n_subjects, seed, omega)
    total_dose = math.fsum(a for _, a in events)
    columns = [[] for _ in times]
    aucs, cmaxes, auc_inf = [], [], []
    for eta_cl, eta_v, eta_ktr in draws:
        cl, v, ktr = cl0 * math.exp(eta_cl), v0 * math.exp(eta_v), ktr0 * math.exp(eta_ktr)
        values = curve(cl, v, ktr)
        for column, value in zip(columns, values):
            column.append(value)
        aucs.append(math.fsum((values[i] + values[i + 1]) / 2 * step for i in range(len(values) - 1)))
        cmaxes.append(max(values))
        auc_inf.append(1000.0 * total_dose / cl)

    band = [{'time_h': t, **_summary(column)} for t, column in zip(times, columns)]
    report.update(
        status='completed_population_calculation', simulation_status='completed_population_calculation',
        typical_parameters={'apparent_clearance_l_h': cl0, 'apparent_volume_l': v0, 'transit_rate_h': ktr0,
                            'precentral_stages': stages},
        times_h=times, typical_concentration_ng_ml=typical_curve, band=band,
        exposure={'auc_0_horizon_ng_h_ml': _summary(aucs), 'auc_0_infinity_ng_h_ml': _summary(auc_inf),
                  'peak_concentration_ng_ml': _summary(cmaxes),
                  'typical_auc_0_horizon_ng_h_ml': calc['auc_0_horizon_ng_h_ml'],
                  'note': 'AUC over the horizon uses the trapezoid rule on the 0.1 h grid; AUC to infinity is dose/CL exactly.'},
        sampling_diagnostics=_diagnostics(draws, omega),
        verification={'exact_vs_numerical_typical_max_abs_ng_ml': max_diff,
                      'tolerance_ng_ml': TYPICAL_CURVE_TOLERANCE_NG_ML,
                      'method': 'Exact transit-chain solution evaluated at the typical parameters and compared with '
                                'the existing numerical educational calculation.'},
        median_note=('The population median is close to, but not identical with, the typical curve: medians of '
                     'log-normal parameters equal their typical values, but concentration is a nonlinear function of '
                     'several parameters.'))
    report['report_sha256'] = digest(report)
    return report


def register_population_pk_commands(app):
    @app.cli.command('patient-pk-population')
    @click.option('--revision-id', type=click.IntRange(min=1), required=True)
    @click.option('--weight-basis', type=click.Choice(WEIGHT_BASES), required=True)
    @click.option('--treatment-file', type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True)
    @click.option('--disease-code', type=click.Choice(DISEASE_CODES), default='UNKNOWN')
    @click.option('--subjects', type=click.IntRange(*SUBJECT_LIMITS), default=DEFAULT_SUBJECTS, show_default=True)
    @click.option('--seed', type=click.IntRange(min=0), default=DEFAULT_SEED, show_default=True)
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(revision_id, weight_basis, treatment_file, disease_code, subjects, seed, output):
        """Between-subject variability band around the typical curve. Never a clinical prediction."""
        try:
            report = calculate_population_pk(revision_id, weight_basis, _read_json(treatment_file), disease_code,
                                             n_subjects=subjects, seed=seed)
            payload = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
            if output:
                with output.open('x', encoding='utf-8') as handle:
                    handle.write(payload)
                click.echo(f'Saved report: {output}\nReport SHA256: {report["report_sha256"]}')
            else:
                click.echo(payload, nl=False)
        except (ValueError, OSError, UnicodeError, SQLAlchemyError) as exc:
            raise click.ClickException(str(exc)) from exc
