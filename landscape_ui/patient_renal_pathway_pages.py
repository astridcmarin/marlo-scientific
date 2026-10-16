"""Simulation 2.0b: organ view of lenalidomide elimination pathways for a saved synthetic patient."""
import json
from flask import Response, abort, request
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.patient_renal_pathways import patient_renal_pathways
from intelligence_store.patient_state_revisions import read_revision
from intelligence_store.run_record import RESULT_TYPES, record_for_renal_pathways
from intelligence_store.saved_scenarios import read_scenario
from .workspace_pages import _response
from .scenario_pages import _error

COLORS = {'filtration': '#1f6f8b', 'secretion': '#7b4fa0', 'non_renal': '#8a8f98'}
MAX_STROKE = 34.0


def _diagram(pathways, scale_total):
    """Arrow widths proportional to clearance; both diagrams share one scale so they can be compared."""
    width = lambda v: max(1.5, MAX_STROKE * v / scale_total)
    return {'filtration': width(pathways['filtration_ml_min']), 'secretion': width(pathways['secretion_ml_min']),
            'non_renal': width(pathways['non_renal_ml_min'])}


def register_patient_renal_pathway_pages(bp):
    @bp.get('/workspace/scenarios/<int:scenario_id>/patient-state/revisions/<int:revision_id>/renal-pathways')
    def patient_renal_pathways_page(scenario_id, revision_id):
        if set(request.args) - {'format'} or any(len(request.args.getlist(k)) != 1 for k in request.args):
            abort(400)
        fmt = request.args.get('format', 'html')
        if fmt not in ('html', 'json'):
            abort(400)
        try:
            scenario, revision = read_scenario(scenario_id), read_revision(revision_id)
            if scenario is None or revision is None or revision.scenario_id != scenario_id:
                abort(404)
            view = patient_renal_pathways(revision_id)
            headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
            if fmt == 'json':
                headers['Content-Disposition'] = f'attachment; filename="patient-{revision_id}-renal-pathways.json"'
                return Response(json.dumps(view, indent=2, allow_nan=False) + '\n', mimetype='application/json', headers=headers)
            done = view['status'] == 'completed'
            scale = max(view['calibration']['total_ml_min'], view['pathways_ml_min']['total_ml_min']) if done else 1.0
            normal = {'filtration_ml_min': view['calibration']['filtration_ml_min'], 'secretion_ml_min': view['calibration']['secretion_ml_min'],
                      'non_renal_ml_min': view['calibration']['non_renal_ml_min']}
            response = _response('landscape_patient_renal_pathways.html', scenario=scenario, revision=revision, view=view,
                                 colors=COLORS, result_type=RESULT_TYPES['elimination_pathway_split'],
                                 patient_widths=_diagram(view['pathways_ml_min'], scale) if done else None,
                                 normal_widths=_diagram(normal, scale) if done else None,
                                 record=record_for_renal_pathways(view) if done else None)
            response.headers.update(headers)
            return response
        except ValueError as exc:
            return _error(exc, 409)
        except SQLAlchemyError:
            db.session.rollback()
            return _error('Patient-state storage is temporarily unavailable.', 503)
