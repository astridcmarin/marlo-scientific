"""Simulation 3.0c: Lignet 2022 bortezomib platelet model and the locked reading check.

Platelet production: progenitors (Prol) -> three maturation stages (Trans1-3) -> circulating platelets
(Circ), with feedback (Circ0/Circ)^gamma on proliferation. Bortezomib acts through (1 - slope*C), either on
proliferation (myelosuppression variant) or on platelet release (budding variant). Plasma concentration
comes from the exact PK solution in bortezomib_pk. Typical values only; not a toxicity prediction.
"""
import copy
import hashlib
import json
from pathlib import Path

import click

from .patient_state import digest
from .bortezomib_platelet_evidence import EXTRACT_SHA256, OBSERVED_SHA256, load_model_extract
from .bortezomib_pk import LABEL_SHA256, rate_constants, standard_regimen, unit_bolus_coefficients
import math

SCHEMA_VERSION = 'bortezomib-platelet-check-report-v1'
METHOD_VERSION = 'bortezomib-platelets-v1.0'
PLAN_PATH = Path(__file__).parent / 'data' / 'bortezomib_platelet_check_plan_v1.json'
PLAN_SHA256 = '86bb80e1feefc348ce6a569552ae8736c6359ee8e5a775a2d6d4fc52d0641eab'
MOLECULAR_WEIGHT = 384.24
VARIANTS = ('myelosuppression', 'platelet_budding')
UNITS = ('ng_per_ml', 'nM')
BOUNDS = ('unbounded_as_printed', 'bounded_at_zero')
FINE_WINDOW_H = 4.0
FINE_STEP_H = 0.002
COARSE_STEP_H = 0.05


def load_plan(path=PLAN_PATH):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError('Analysis plan is missing or changed; no check was run.')
    return json.loads(raw)


def _segments(events, t_end, extra_cuts=()):
    cuts = {0.0, t_end} | {t for t in extra_cuts if 0.0 < t < t_end}
    for start, _ in events:
        if start < t_end:
            cuts.update({start, min(start + FINE_WINDOW_H, t_end)})
    cuts = sorted(cuts)
    fine_windows = [(s, s + FINE_WINDOW_H) for s, _ in events]
    return [(a, b, FINE_STEP_H if any(lo <= a < hi for lo, hi in fine_windows) else COARSE_STEP_H)
            for a, b in zip(cuts, cuts[1:])]


def simulate(variant, units, bound, events, t_end_h, step_scale=1.0, record_at=(), extract=None):
    """Integrate the platelet model under one reading. Doses at a segment's start are active within it;
    doses at its end are not, so values recorded at a dose time are pre-dose values."""
    if variant not in VARIANTS or units not in UNITS or bound not in BOUNDS:
        raise ValueError('Unknown variant or reading.')
    extract = extract or load_model_extract()
    v = extract['pd_model']['variants'][variant]
    gamma, circ0, slope = v['gamma'], v['circ0_1e9_per_l'], v['slope']
    ktr = 4.0 / v['mtt_h']
    terms = unit_bolus_coefficients(rate_constants(extract))
    factor = 1000.0 / MOLECULAR_WEIGHT if units == 'nM' else 1.0
    state = [circ0] * 5  # Prol, Trans1, Trans2, Trans3, Circ
    record = sorted(set(record_at))
    recorded, t = {}, 0.0
    nadir = (1.0, 0.0)
    negative_h = 0.0

    def effect(c):
        e = 1.0 - slope * c
        return max(0.0, e) if bound == 'bounded_at_zero' else e

    def deriv(s, c):
        prol, t1, t2, t3, circ = s
        e = effect(c)
        feedback = (circ0 / circ) ** gamma
        release = ktr * t3 * (e if variant == 'platelet_budding' else 1.0)
        growth = ktr * prol * (e if variant == 'myelosuppression' else 1.0) * feedback
        return (growth - ktr * prol, ktr * prol - ktr * t1, ktr * t1 - ktr * t2,
                ktr * t2 - release, release - ktr * circ)

    for a, b, step in _segments(events, t_end_h, record):
        active = [(s0, d) for s0, d in events if s0 <= a]
        conc = lambda time: factor * 1000.0 * math.fsum(d * cf * math.exp(-lam * (time - s0)) for s0, d in active for cf, lam in terms)
        n = max(1, math.ceil((b - a) / (step * step_scale) - 1e-9))
        h = (b - a) / n
        for i in range(n):
            t = a + i * h
            if (1.0 - slope * conc(t + h / 2)) < 0:
                negative_h += h
            k1 = deriv(state, conc(t))
            s2 = [x + h / 2 * d for x, d in zip(state, k1)]
            if min(s2) <= 0:
                return {'status': 'invalid_state', 'time_h': t, 'recorded': recorded}
            k2 = deriv(s2, conc(t + h / 2))
            s3 = [x + h / 2 * d for x, d in zip(state, k2)]
            if min(s3) <= 0:
                return {'status': 'invalid_state', 'time_h': t, 'recorded': recorded}
            k3 = deriv(s3, conc(t + h / 2))
            s4 = [x + h * d for x, d in zip(state, k3)]
            if min(s4) <= 0:
                return {'status': 'invalid_state', 'time_h': t, 'recorded': recorded}
            k4 = deriv(s4, conc(t + h))
            state = [x + h / 6 * (d1 + 2 * d2 + 2 * d3 + d4) for x, d1, d2, d3, d4 in zip(state, k1, k2, k3, k4)]
            if min(state) <= 0:
                return {'status': 'invalid_state', 'time_h': t + h, 'recorded': recorded}
            ratio = state[4] / circ0
            if ratio < nadir[0]:
                nadir = (ratio, t + h)
        for r in record:
            if abs(r - b) < 1e-9:
                recorded[r] = state[4] / circ0
    return {'status': 'completed', 'recorded': recorded, 'nadir_ratio': nadir[0], 'nadir_time_h': nadir[1],
            'time_effect_term_negative_h': negative_h, 'final_state': state}


def _run_reading(variant, units, bound, events, end_h, primary_t, recovery_t, step_scale):
    return simulate(variant, units, bound, events, end_h, step_scale, record_at=(primary_t, recovery_t))


def run_check():
    plan = load_plan()
    events = standard_regimen(1.3, cycles=1)
    end_h, primary_t, recovery_t = 504.0, 240.0, 504.0
    lo, hi = plan['endpoints']['primary']['interval']
    rows = []
    for variant in VARIANTS:
        for units in UNITS:
            for bound in BOUNDS:
                base = _run_reading(variant, units, bound, events, end_h, primary_t, recovery_t, 1.0)
                row = {'variant': variant, 'units': units, 'effect_bound': bound, 'status': base['status']}
                if base['status'] != 'completed':
                    row.update(classification='invalid_state', invalid_at_h=base['time_h'])
                    rows.append(row)
                    continue
                half = _run_reading(variant, units, bound, events, end_h, primary_t, recovery_t, 0.5)
                primary, recovery = base['recorded'][primary_t], base['recorded'][recovery_t]
                resolved = (half['status'] == 'completed'
                            and abs(half['recorded'][primary_t] - primary) <= 1e-4 * primary
                            and abs(half['recorded'][recovery_t] - recovery) <= 1e-4 * recovery)
                row.update(cycle1_day11_ratio=primary, cycle2_day1_ratio=recovery,
                           recovery_label='recovers' if recovery >= 0.90 else 'does_not_recover',
                           nadir_ratio=base['nadir_ratio'], nadir_time_h=base['nadir_time_h'],
                           time_effect_term_negative_h=base['time_effect_term_negative_h'],
                           step_halving_primary_change=abs(half['recorded'][primary_t] - primary) if half['status'] == 'completed' else None,
                           numerically_resolved=resolved)
                if not resolved:
                    row['classification'] = 'numerically_unresolved'
                else:
                    row['classification'] = 'consistent' if lo <= primary <= hi else 'inconsistent'
                rows.append(row)
    adopted = {}
    for variant in VARIANTS:
        ok = [(r['units'], r['effect_bound']) for r in rows if r['variant'] == variant and r['classification'] == 'consistent']
        adopted[variant] = ok
    both = [rb for rb in adopted['myelosuppression'] if rb in adopted['platelet_budding']]
    def pick(options):
        options = sorted(options, key=lambda ub: (ub[0] != 'ng_per_ml', ub[1] != 'bounded_at_zero'))
        return {'units': options[0][0], 'effect_bound': options[0][1]} if options else None
    decision = {'consistent_by_variant': {k: [{'units': u, 'effect_bound': b} for u, b in v] for k, v in adopted.items()},
                'consistent_for_both_variants': [{'units': u, 'effect_bound': b} for u, b in both],
                'adopted_primary_reading': pick(both),
                'per_variant_if_none_shared': None if both else {k: pick(v) for k, v in adopted.items()}}
    report = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'plan_version': plan['plan_version'],
              'plan_sha256': PLAN_SHA256, 'model_extract_sha256': EXTRACT_SHA256, 'observed_sha256': OBSERVED_SHA256,
              'label_reference_sha256': LABEL_SHA256, 'classification': plan['classification'],
              'observed_primary': plan['endpoints']['primary']['observed'], 'interval': [lo, hi],
              'rows': rows, 'decision': decision, 'not_this': copy.deepcopy(plan['not_this']),
              'known_differences': copy.deepcopy(plan['known_differences']), 'clinical_prediction_validated': False}
    report['report_sha256'] = digest(report)
    return report


def register_bortezomib_platelet_commands(app):
    @app.cli.command('bortezomib-platelet-check')
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(output):
        """Run the locked bortezomib platelet reading check. Internal consistency only; not validation."""
        try:
            report = run_check()
        except (ValueError, OSError, KeyError) as exc:
            raise click.ClickException(str(exc)) from exc
        payload = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
        if output:
            with output.open('x', encoding='utf-8') as handle:
                handle.write(payload)
            click.echo(f'Saved report: {output}\nReport SHA256: {report["report_sha256"]}')
        else:
            click.echo(payload, nl=False)


ADOPTED_READING = {'units': 'ng_per_ml', 'effect_bound': 'unbounded_as_printed'}
REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'bortezomib_platelet_check_v1.json'
TIMECOURSE_SCHEMA = 'bortezomib-platelet-timecourse-v1'
MAX_CYCLES = 4


def platelet_timecourse(cycles=1):
    """Typical platelet curves (fraction of each variant's baseline) for 1.3 mg/m2 on days 1, 4, 8, 11 of
    21-day cycles, under the reading adopted by the locked check, plus the driving PK curve."""
    from .bortezomib_pk import concentration_curve
    if isinstance(cycles, bool) or not isinstance(cycles, int) or not 1 <= cycles <= MAX_CYCLES:
        raise ValueError(f'Cycles must be a whole number from 1 to {MAX_CYCLES}.')
    extract = load_model_extract()
    end = 504.0 * cycles
    events = standard_regimen(1.3, cycles=cycles)
    times = [float(h) for h in range(1, int(end) + 1)]
    variants = {}
    for variant in VARIANTS:
        v = extract['pd_model']['variants'][variant]
        result = simulate(variant, ADOPTED_READING['units'], ADOPTED_READING['effect_bound'], events, end,
                          record_at=times, extract=extract)
        if result['status'] != 'completed':
            raise ValueError('Platelet simulation did not complete.')
        fractions = [1.0] + [result['recorded'][t] for t in times]
        day11 = [{'cycle': c + 1, 'time_h': 504.0 * c + 240.0, 'fraction_of_baseline': fractions[int(504 * c + 240)]}
                 for c in range(cycles)]
        variants[variant] = {
            'parameters': {k: v[k] for k in ('gamma', 'mtt_h', 'circ0_1e9_per_l', 'slope')},
            'description': v['description'], 'fraction_of_baseline': fractions,
            'platelets_1e9_per_l_from_fitted_baseline': [f * v['circ0_1e9_per_l'] for f in fractions],
            'nadir_fraction': result['nadir_ratio'], 'nadir_time_h': result['nadir_time_h'],
            'pre_dose_day11_by_cycle': day11,
            'next_cycle_day1_fraction': fractions[-1],
            'hours_effect_term_negative': result['time_effect_term_negative_h'],
            'effect_term_zero_at_ng_ml': 1.0 / v['slope']}
    pk_times = sorted({h / 20.0 for h in range(0, 20 * 6)} | {float(h) for h in range(0, int(end) + 1)})
    report_raw = REPORT_PATH.read_bytes()
    report = json.loads(report_raw)
    if report['decision']['adopted_primary_reading'] != ADOPTED_READING:
        raise ValueError('Adopted reading does not match the committed check report.')
    observed = load_plan()['endpoints']['primary']
    out = {'schema_version': TIMECOURSE_SCHEMA, 'method_version': METHOD_VERSION, 'cycles': cycles,
           'regimen': {'dose_mg_m2': 1.3, 'route': 'IV bolus', 'days': [1, 4, 8, 11], 'cycle_length_days': 21,
                       'dose_times_h': [t for t, _ in events]},
           'times_h': [0.0] + times, 'variants': variants,
           'pk': {'times_h': pk_times, 'concentration_ng_ml': concentration_curve(events, pk_times, extract)},
           'observed_reference': {'cycle1_day11_ratio': observed['observed'], 'interval': observed['interval'],
                                  'source': observed['observed_source']},
           'reading': dict(ADOPTED_READING, check_report_sha256=report['report_sha256'],
                           check_report_file_sha256=hashlib.sha256(report_raw).hexdigest()),
           'sources': {'model_extract_sha256': EXTRACT_SHA256, 'observed_sha256': OBSERVED_SHA256,
                       'label_reference_sha256': LABEL_SHA256, 'plan_sha256': PLAN_SHA256},
           'prediction_type': 'typical_value_from_mean_data',
           'limitations': [
               'Typical curve fitted to mean platelet counts; patients vary widely around it and no between-patient spread is available.',
               'The effect term (1 - slope x C) is used as printed: it goes negative for a few hours after each dose, so it describes the net effect on mean counts, not a literal mechanism.',
               'The PK model has one clearance and overstates first-dose exposure about 7-fold; early cycle 1 is affected most.',
               'Only the studied regimen (1.3 mg/m2, days 1, 4, 8, 11 of 21-day cycles) is run; no dose holds, reductions or other schedules.',
               'Later-cycle mean counts in the source may rise partly because patients with low counts stopped treatment.',
               'Myeloma-related low platelets before treatment are not modelled.',
               'Not a toxicity prediction, dosing advice or a basis for treatment decisions.'],
           'clinical_prediction_validated': False, 'ready_for_patient_simulation': False}
    out['report_sha256'] = digest(out)
    return out
