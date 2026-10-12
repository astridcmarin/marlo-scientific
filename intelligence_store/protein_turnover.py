"""Generic normalized turnover mathematics; no drug or patient calibration."""
import hashlib
import json
import math


def _number(value, name, low, high):
    if type(value) not in (int, float):
        raise ValueError(name + ' must be a finite number, not a boolean or string.')
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be between {low} and {high}.')
    return value


def _digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def calculate_turnover(*, loss_rate_h_inv, phases, times_h, initial_relative_amount=1):
    """dR/dt=kout*(1-m*R); synthesis stays at normalized baseline kout."""
    kout = _number(loss_rate_h_inv, 'loss_rate_h_inv', 1e-6, 1e3)
    initial = _number(initial_relative_amount, 'initial_relative_amount', 0, 1e6)
    if not isinstance(times_h, list) or not 2 <= len(times_h) <= 1001:
        raise ValueError('Provide 2 to 1001 sample times.')
    times = [_number(t, 'time_h', 0, 72) for t in times_h]
    if times[0] != 0 or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('Sample times must start at zero and strictly increase.')
    if not isinstance(phases, list) or not 1 <= len(phases) <= 8:
        raise ValueError('Provide 1 to 8 explicit loss-multiplier phases.')
    normalized = []
    for phase in phases:
        if not isinstance(phase, dict) or set(phase) != {'start_time_h', 'loss_multiplier'}:
            raise ValueError('Each phase needs only start_time_h and loss_multiplier.')
        normalized.append({'start_time_h': _number(phase['start_time_h'], 'start_time_h', 0, 72),
            'loss_multiplier': _number(phase['loss_multiplier'], 'loss_multiplier', 0, 1000)})
    if any(0 < p['loss_multiplier'] < 1e-6 for p in normalized):
        raise ValueError('A nonzero loss_multiplier must be at least 1e-6.')
    starts = [p['start_time_h'] for p in normalized]
    if starts[0] != 0 or any(b <= a for a, b in zip(starts, starts[1:])) or starts[-1] >= times[-1]:
        raise ValueError('Phases must start at zero, strictly increase and start before the horizon.')
    def evolve(amount, duration, multiplier):
        if multiplier == 0:
            return amount + kout * duration
        rate = kout * multiplier
        # Convex form avoids cancellation at large times; expm1 preserves small changes.
        decay = math.exp(-rate * duration)
        return amount * decay + (-math.expm1(-rate * duration)) / multiplier
    points, boundaries, segments = [], [], []
    amount = initial
    for index, phase in enumerate(normalized):
        start = phase['start_time_h']
        end = starts[index+1] if index+1 < len(starts) else times[-1]
        multiplier = phase['loss_multiplier']
        boundaries.append({'time_h': start, 'relative_amount': amount,
            'before_loss_multiplier': None if index == 0 else normalized[index-1]['loss_multiplier'],
            'after_loss_multiplier': multiplier})
        final = evolve(amount, end-start, multiplier)
        segments.append({'start_time_h': start, 'end_time_h': end, 'loss_multiplier': multiplier,
            'initial_relative_amount': amount, 'final_relative_amount': final,
            'equilibrium_relative_amount': None if multiplier == 0 else 1/multiplier})
        for t in times:
            if start <= t < end or (index == len(normalized)-1 and t == end):
                points.append({'time_h': t, 'phase_index': index, 'loss_multiplier': multiplier,
                    'relative_amount': evolve(amount, t-start, multiplier)})
        amount = final
    report = {'schema_version': 'generic-normalized-turnover-v1',
        'method_version': 'analytic-piecewise-turnover-v1.0', 'purpose': 'synthetic_educational',
        'inputs': {'loss_rate_h_inv': kout, 'initial_relative_amount': initial,
            'phases': normalized, 'sample_times_h': times, 'origin': 'invented_educational_inputs'},
        'units': {'time': 'h', 'loss_rate': 'h^-1', 'relative_amount': 'dimensionless',
            'loss_multiplier': 'dimensionless'},
        'equation': 'dR/dt = kout * (1 - loss_multiplier * R)',
        'normalization': 'R is amount divided by an unspecified baseline amount. Baseline synthesis is kout in relative-amount units per hour; baseline loss multiplier is 1.',
        'baseline_half_life_h': math.log(2)/kout,
        'numerical_method': 'Exact constant-phase solution with expm1 and continuous amount carry-forward; zero-loss phase uses linear synthesis.',
        'boundary_convention': 'At a switch, the multiplier is the new phase and relative amount is continuous. Pre-zero history is unknown.',
        'points': points, 'boundaries': boundaries, 'segments': segments,
        'concept_reference': {'doi': '10.1007/BF01061691',
            'url': 'https://pubmed.ncbi.nlm.nih.gov/8133465/',
            'role': 'Indirect-response turnover concept only; no extracted protein-specific parameters or calibration.',
            'checked_on': '2026-10-09'},
        'assumptions': ['Constant synthesis, first-order loss, one homogeneous mathematical quantity.',
            'Loss multipliers are externally imposed steps, not concentrations, doses or binding fractions.',
            'No drug, protein identity, cell type, organ, feedback, stochastic variability or assay calibration.'],
        'drug': None, 'protein': None, 'patient_revision_id': None, 'pk_run_id': None,
        'clinical_prediction_validated': False, 'ready_for_patient_simulation': False,
        'limitation': 'Invented normalized turnover example only. It does not calculate lenalidomide-induced IKZF degradation, measured biomarkers, efficacy, toxicity or a patient response.'}
    report['report_sha256'] = _digest(report)
    return report


def turnover_example(times_h=None):
    times = times_h if times_h is not None else [0, 1, 2, 4, 8, 12, 24]
    phases = [{'start_time_h': 0, 'loss_multiplier': 4}, {'start_time_h': 4, 'loss_multiplier': 1}]
    return {name: calculate_turnover(loss_rate_h_inv=rate, phases=phases, times_h=times)
        for name, rate in [('faster_turnover', .2), ('slower_turnover', .05)]}
