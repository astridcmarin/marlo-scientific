"""Phase 4.1f: protocol benchmarking pages (eligibility thresholds across the myeloma corpus).

Only criterion types that passed the locked v2 accuracy check are shown; see intelligence_store.eligibility_benchmark.
"""
from flask import abort, current_app, request

from intelligence_store import eligibility_benchmark as eb
from intelligence_store.eligibility_annotations_v2 import TYPES as ANNOTATION_TYPES
from .workspace_pages import _response

STATUSES = ('COMPLETED', 'RECRUITING', 'ACTIVE_NOT_RECRUITING', 'NOT_YET_RECRUITING', 'TERMINATED', 'WITHDRAWN',
            'SUSPENDED', 'UNKNOWN', 'ENROLLING_BY_INVITATION')


def _filters():
    def year(name):
        value = (request.args.get(name) or '').strip()
        return int(value) if value.isdigit() and len(value) == 4 else None
    phase = request.args.get('phase') or None
    status = request.args.get('status') or None
    return {'phase': phase if phase in eb.PHASE_LABELS else None, 'status': status if status in STATUSES else None,
            'start_from': year('start_from'), 'start_to': year('start_to')}


def _visible(status):
    preview = bool(current_app.config.get('ELIGIBILITY_BENCHMARK_PREVIEW'))
    types = list(eb.LABELS) if preview else [t for t in eb.LABELS if t in status['passing_types']]
    return types, preview


def register_eligibility_benchmark_pages(bp):
    @bp.get('/benchmarking')
    def eligibility_benchmark():
        status = eb.validation_status()
        types, preview = _visible(status)
        filters = _filters()
        data = eb.extracted_corpus() if types else None
        rows = eb.filter_trials(data['trials'], **filters) if data else []
        summaries = [eb.distribution(rows, t) for t in types]
        return _response('landscape_eligibility_benchmark.html', status=status, preview=preview, summaries=summaries,
                         filters=filters, phase_labels=eb.PHASE_LABELS, statuses=STATUSES, labels=eb.LABELS,
                         data=data, selection=len(rows))

    @bp.get('/benchmarking/criteria/<ctype>')
    def eligibility_benchmark_type(ctype):
        if ctype not in eb.LABELS:
            abort(404)
        status = eb.validation_status()
        types, preview = _visible(status)
        if ctype not in types:
            abort(404)
        filters = _filters()
        data = eb.extracted_corpus()
        rows = eb.filter_trials(data['trials'], **filters)
        dist = eb.distribution(rows, ctype)
        draft, draft_error = None, None
        units = ANNOTATION_TYPES[ctype]['units']
        if request.args.get('draft_value'):
            comparator = request.args.get('draft_comparator')
            unit = request.args.get('draft_unit')
            try:
                value = float(request.args['draft_value'].replace(',', ''))
                if comparator not in eb.SYMBOL or unit not in units or value < 0:
                    raise ValueError
                draft = eb.compare_draft(rows, ctype, comparator, value, unit)
            except ValueError:
                draft_error = 'Choose a comparator and a unit, and enter a non-negative number.'
        accuracy = status['per_type'].get(ctype)
        return _response('landscape_eligibility_benchmark_type.html', ctype=ctype, dist=dist, status=status, preview=preview,
                         filters=filters, phase_labels=eb.PHASE_LABELS, statuses=STATUSES, units=[u for u in units if u != 'other'],
                         draft=draft, draft_error=draft_error, accuracy=accuracy, data=data, symbol=eb.SYMBOL)
