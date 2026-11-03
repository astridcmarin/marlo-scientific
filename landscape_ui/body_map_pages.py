"""Digital human 1.0, step 1.3b: the lenalidomide elimination body map page (record mode).

The 3D organs come from the pinned asset manifest (step 1.3a); the numbers come from body-map-view-v1 (step 1.2), which
uses the same pathway model and estimate as the 2.0b patient page. The page always carries a 2D flow diagram with the
same numbers, so it works without WebGL and the 3D view is never the only place a number appears.
"""
import json

from flask import Response, abort, request, url_for
from sqlalchemy.exc import SQLAlchemyError

from intelligence_store.body_map import NODES, record_map
from intelligence_store.body_map_assets import BodyMapAssetError, load_manifest, viewer_assets
from intelligence_store.extensions import db
from intelligence_store.patient_renal_pathways import patient_renal_pathways
from intelligence_store.patient_state_revisions import read_revision
from intelligence_store.run_record import RESULT_TYPES, record_for_body_map
from intelligence_store.saved_scenarios import read_scenario
from .scenario_pages import _error
from .workspace_pages import _response

CONTEXT_LABEL = 'Anatomy for orientation, not simulated. No model result is attached to this organ.'
LEGEND = 'Coloured organs carry model results; grey organs are anatomy for orientation.'
# Fixed camera presets (scene metres; yaw and pitch in radians). The first is the default, so screenshots are comparable.
CAMERA_PRESETS = [
    {'id': 'body', 'label': 'Whole body', 'yaw': 0.0, 'pitch': 0.0, 'scale': 1.05, 'cx': 0.0, 'cy': 0.0},
    {'id': 'abdomen', 'label': 'Abdomen', 'yaw': 0.0, 'pitch': 0.0, 'scale': 3.2, 'cx': 0.0, 'cy': 0.3},
    {'id': 'kidneys', 'label': 'Kidneys', 'yaw': 0.0, 'pitch': 0.0, 'scale': 6.5, 'cx': 0.0, 'cy': 0.29},
    {'id': 'side', 'label': 'Side', 'yaw': 1.5708, 'pitch': 0.0, 'scale': 1.05, 'cx': 0.0, 'cy': 0.0},
]
COLORS = {'filtration': '#1f6f8b', 'tubular_secretion': '#7b4fa0', 'non_renal': '#8a8f98', 'renal_excretion': '#b8892a'}
MAX_STROKE = 30.0


def _part_titles(manifest):
    titles = {}
    for part in manifest['parts']:
        base = part['group'].replace('VH_M_', '').replace('Allen_', '').replace('_', ' ').strip()
        title = f"{base}: {part['structure']}" if part.get('structure') else base
        titles[part['name']] = {'title': title[:1].upper() + title[1:]}
    return titles


def viewer_config(manifest):
    assets = viewer_assets(manifest)
    return {
        'models': [{'url': url_for('landscape.static', filename=m['static_path']), 'class': m['class'],
                    'sha256': m['sha256']} for m in assets['models']],
        'parts': _part_titles(manifest),
        'node_labels': {n['id']: n['label'] for n in NODES},
        'context_label': CONTEXT_LABEL,
        'camera_presets': CAMERA_PRESETS,
    }


def flow_widths(view):
    """Line widths proportional to clearance on the view's fixed scale (the normal-function total)."""
    top = view['drawing_scale']['max_flow_ml_min']
    return {f['kind']: max(1.5, MAX_STROKE * f['value'] / top) for f in view['flows'] if f['value'] is not None}


def register_body_map_pages(bp):
    @bp.get('/workspace/scenarios/<int:scenario_id>/patient-state/revisions/<int:revision_id>/body-map')
    def patient_body_map(scenario_id, revision_id):
        if set(request.args) - {'format'} or any(len(request.args.getlist(k)) != 1 for k in request.args):
            abort(400)
        fmt = request.args.get('format', 'html')
        if fmt not in ('html', 'json'):
            abort(400)
        try:
            scenario, revision = read_scenario(scenario_id), read_revision(revision_id)
            if scenario is None or revision is None or revision.scenario_id != scenario_id:
                abort(404)
            view = record_map(revision_id)
            headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
            if fmt == 'json':
                headers['Content-Disposition'] = f'attachment; filename="patient-{revision_id}-body-map.json"'
                return Response(json.dumps(view, indent=2, allow_nan=False) + '\n', mimetype='application/json',
                                headers=headers)
            done = view['status'] == 'completed'
            manifest, config, assets_error = None, None, None
            if done:
                try:
                    manifest = load_manifest()
                    config = viewer_config(manifest)
                except BodyMapAssetError as exc:
                    assets_error = str(exc)
            pathways_view = patient_renal_pathways(revision_id) if done else None
            response = _response(
                'landscape_body_map.html', scenario=scenario, revision=revision, view=view, done=done,
                result_type=RESULT_TYPES['elimination_pathway_split'], config=config, assets_error=assets_error,
                legend=LEGEND, presets=CAMERA_PRESETS, colors=COLORS, widths=flow_widths(view) if done else None,
                flows={f['kind']: f for f in view['flows']} if done else None,
                attribution=[s['attribution'] for s in manifest['sources'].values()] if manifest else [],
                record=record_for_body_map(view, pathways_view) if done else None)
            response.headers.update(headers)
            return response
        except ValueError as exc:
            return _error(exc, 409)
        except SQLAlchemyError:
            db.session.rollback()
            return _error('Patient-state storage is temporarily unavailable.', 503)
