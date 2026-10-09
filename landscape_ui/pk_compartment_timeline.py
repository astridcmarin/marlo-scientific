"""Bounded presentation of retained amounts; no model, catalog or solver calls."""
import math

ORDER = ['ABS'] + [f'TRANS{i}' for i in range(1, 8)]
LABELS = ['ABS · stage 1'] + [f'TRANS{i} · stage {i+1}' for i in range(1, 8)] + ['Central compartment', 'Eliminated amount']


def _number(value):
    if type(value) not in (int, float):
        raise ValueError('Unsupported numeric value')
    try:
        value = float(value)
    except (ValueError, OverflowError):
        raise ValueError('Unsupported numeric value') from None
    if not math.isfinite(value) or value < 0:
        raise ValueError('Unsupported numeric value')
    return value



def _boundary_point(point, time):
    if _number(point['time_h']) != time:
        raise ValueError('Inconsistent boundary time')
    stages = point['precentral_amounts_mg']
    if not isinstance(stages, list) or len(stages) != 8:
        raise ValueError('Incomplete boundary amounts')
    amounts = [_number(v) for v in stages] + [_number(point['central_amount_mg']), _number(point['eliminated_amount_mg'])]
    requested = _number(point['cumulative_requested_amount_mg'])
    accounted = math.fsum(amounts)
    if abs(accounted - requested) > 1e-9 * max(1, requested):
        raise ValueError('Inconsistent boundary balance')
    return {'time_h': time, 'amounts_mg': amounts,
            'concentration_ng_ml': _number(point['concentration_ng_ml']),
            'auc_ng_h_ml': _number(point['auc_0_t_ng_h_ml']),
            'requested_mg': requested, 'accounted_mg': accounted}


def _events(report, points):
    try:
        boundaries = report['event_boundaries']
        if not isinstance(boundaries, list) or not 1 <= len(boundaries) <= 4:
            raise ValueError('Missing bounded event snapshots')
        requests = report['preflight_review']['treatment_request_preview']['request']['events']
        if not isinstance(requests, list) or len(requests) != len(boundaries):
            raise ValueError('Incomplete request boundary set')
        expected_events = [(_number(e['time']['value']), _number(e['amount']['value'])) for e in requests]
        if [(_number(e['time_h']), _number(e['amount_mg'])) for e in boundaries] != expected_events:
            raise ValueError('Boundary times/amounts differ from the retained request')
        indices = {p['time_h']: i for i, p in enumerate(points)}
        events = []
        previous = -1
        for boundary in boundaries:
            time = _number(boundary['time_h'])
            amount = _number(boundary['amount_mg'])
            if amount <= 0 or time <= previous or time not in indices:
                raise ValueError('Unsupported event time or amount')
            before = _boundary_point(boundary['before'], time)
            after = _boundary_point(boundary['after'], time)
            if after != points[indices[time]]:
                raise ValueError('After-event values do not match the archived sampled point')
            tolerance = 1e-9 * max(1, after['requested_mg'])
            if (abs(after['requested_mg'] - before['requested_mg'] - amount) > tolerance
                    or abs(after['amounts_mg'][0] - before['amounts_mg'][0] - amount) > tolerance
                    or any(abs(a-b) > tolerance for a,b in zip(after['amounts_mg'][1:], before['amounts_mg'][1:]))
                    or abs(after['concentration_ng_ml'] - before['concentration_ng_ml']) > 5e-7
                    or abs(after['auc_ng_h_ml'] - before['auc_ng_h_ml']) > 5e-5):
                raise ValueError('Inconsistent request-time transition')
            events.append({'index': indices[time], 'time_h': time, 'amount_mg': amount,
                           'before': before, 'after': after})
            previous = time
        return {'available': True, 'items': events}
    except (KeyError, TypeError, ValueError, OverflowError):
        return {'available': False, 'items': [],
                'reason': 'Dose-event snapshots are missing or inconsistent; request-time controls are withheld.'}


def build_compartment_timeline(report):
    """Project archived values for display; integrity is checked by read_pk_run upstream."""
    try:
        if (report['method_version'] != 'hughes-educational-pk-v1.0'
                or report['status'] != 'completed_educational_calculation'
                or report['point_amount_order'] != ORDER):
            return {'available': False, 'reason': 'This archived model structure is not supported by the timeline.'}
        points = report['points']
        if not isinstance(points, list) or not 1 <= len(points) <= 721:
            raise ValueError('Unsupported point count')
        projected = []
        last_time = -1
        last_requested = -1
        for point in points:
            time = _number(point['time_h'])
            if time <= last_time or time > 72 or (not projected and time != 0):
                raise ValueError('Unsupported times')
            stages = point['precentral_amounts_mg']
            if not isinstance(stages, list) or len(stages) != 8:
                raise ValueError('Unsupported amount structure')
            amounts = [_number(v) for v in stages] + [_number(point['central_amount_mg']), _number(point['eliminated_amount_mg'])]
            requested = _number(point['cumulative_requested_amount_mg'])
            if requested < last_requested:
                raise ValueError('Unsupported request history')
            accounted = math.fsum(amounts)
            if abs(accounted - requested) > 1e-9 * max(1, requested):
                raise ValueError('Inconsistent amount balance')
            projected.append({'time_h': time, 'amounts_mg': amounts,
                              'concentration_ng_ml': _number(point['concentration_ng_ml']),
                              'auc_ng_h_ml': _number(point['auc_0_t_ng_h_ml']),
                              'requested_mg': requested, 'accounted_mg': accounted})
            last_time, last_requested = time, requested
        return {'available': True, 'labels': LABELS[:], 'points': projected, 'first': projected[0],
                'max_index': len(projected) - 1, 'events': _events(report, projected)}
    except (KeyError, TypeError, ValueError, OverflowError):
        return {'available': False, 'reason': 'Archived compartment values are incomplete or inconsistent; the timeline is withheld.'}
