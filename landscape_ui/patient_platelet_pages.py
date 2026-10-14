"""Patient Lab 2.2b: bortezomib platelet curves in a saved synthetic patient's absolute counts."""
import json
import math
from flask import Response, abort, request
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.bortezomib_platelets import MAX_CYCLES
from intelligence_store.bortezomib_patient_platelets import patient_platelet_view
from intelligence_store.patient_state_revisions import read_revision
from intelligence_store.saved_scenarios import read_scenario
from .bortezomib_platelet_pages import COLORS, LABELS
from .workspace_pages import _response
from .scenario_pages import _error

X0, X1, Y0, Y1 = 70.0, 740.0, 30.0, 250.0


def _chart(view):
    end = view['times_h'][-1]
    top = max(view['baseline_1e9_per_l'] * 1.5, 100.0)
    top = math.ceil(top / 50.0) * 50.0
    x = lambda t: X0 + (X1 - X0) * t / end
    y = lambda c: Y1 - (Y1 - Y0) * c / top
    lines = [{'label': LABELS[name], 'color': COLORS[name],
              'points': ' '.join(f'{x(t):.2f},{y(c):.2f}' for t, c in zip(view['times_h'], v['absolute_1e9_per_l']))}
             for name, v in view['variants'].items()]
    grades = [{'grade': b['grade'], 'value': b['upper_exclusive'], 'y': y(b['upper_exclusive'])} for b in view['grading']['thresholds']]
    old = {b['upper_exclusive'] for b in view['grading']['thresholds']}
    current = [{'grade': b['grade'], 'value': b['upper_exclusive'], 'y': y(b['upper_exclusive'])}
               for b in view['current_grading']['thresholds'] if b['upper_exclusive'] not in old]
    nadir = view['observed_context']['illustrative_average_individual_nadir_1e9_per_l']
    return {'lines': lines, 'grades': grades, 'current_grades': current, 'baseline_y': y(view['baseline_1e9_per_l']), 'nadir_y': y(nadir),
            'ticks': [{'y': y(v), 'label': f'{v:g}'} for v in range(0, int(top) + 1, 50)],
            'days': [{'x': x(24.0 * d), 'label': f'{d + 1}'} for d in range(0, int(end / 24) + 1, 7)],
            'doses': [x(t) for t in view['regimen']['dose_times_h']]}


def register_patient_platelet_pages(bp):
    @bp.get('/workspace/scenarios/<int:scenario_id>/patient-state/revisions/<int:revision_id>/bortezomib-platelets')
    def patient_bortezomib_platelets(scenario_id, revision_id):
        if set(request.args) - {'cycles', 'format'} or any(len(request.args.getlist(k)) != 1 for k in request.args):
            abort(400)
        fmt = request.args.get('format', 'html')
        raw = request.args.get('cycles', '1')
        if fmt not in ('html', 'json') or raw not in {str(n) for n in range(1, MAX_CYCLES + 1)}:
            abort(400)
        try:
            scenario, revision = read_scenario(scenario_id), read_revision(revision_id)
            if scenario is None or revision is None or revision.scenario_id != scenario_id:
                abort(404)
            view = patient_platelet_view(revision_id, int(raw))
            headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
            if fmt == 'json':
                headers['Content-Disposition'] = f'attachment; filename="patient-{revision_id}-bortezomib-platelets.json"'
                return Response(json.dumps(view, indent=2, allow_nan=False) + '\n', mimetype='application/json', headers=headers)
            response = _response('landscape_patient_bortezomib_platelets.html', scenario=scenario, revision=revision,
                                 view=view, chart=_chart(view) if view['status'] == 'completed' else None,
                                 labels=LABELS, colors=COLORS, max_cycles=MAX_CYCLES)
            response.headers.update(headers)
            return response
        except ValueError as exc:
            return _error(exc, 409)
        except SQLAlchemyError:
            db.session.rollback()
            return _error('Patient-state storage is temporarily unavailable.', 503)
