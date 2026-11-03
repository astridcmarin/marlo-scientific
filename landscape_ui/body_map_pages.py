"""Digital human 1.0, steps 1.3b and 1.4: the lenalidomide elimination body map pages (record and explorer modes).

The 3D organs come from the pinned asset manifest (step 1.3a); the numbers come from body-map-view-v1 (step 1.2), which
uses the same pathway model and estimate as the 2.0b patient page. The page always carries a 2D flow diagram with the
same numbers, so it works without WebGL and the 3D view is never the only place a number appears.
"""
import json

from flask import Response, abort, request, url_for
from sqlalchemy.exc import SQLAlchemyError

from intelligence_store.body_map import NODES, RANGE, explorer_map, record_map
from intelligence_store.body_map_context import BodyMapContextError, body_map_context
from intelligence_store.body_map_assets import BodyMapAssetError, load_manifest, viewer_assets
from intelligence_store.body_map_paths import BodyMapPathError, load_paths
from intelligence_store.extensions import db
from intelligence_store.patient_renal_pathways import patient_renal_pathways
from intelligence_store.patient_state_revisions import read_revision
from intelligence_store.run_record import RESULT_TYPES, record_for_body_map, record_for_body_map_explorer
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
# Explorer: the control starts at the calibration point of the pathway model (normal function).
EXPLORER_DEFAULT_CRCL = 110
EXPLORER_STEP = 1


def _part_titles(manifest):
    titles = {}
    for part in manifest['parts']:
        base = part['group'].replace('VH_M_', '').replace('Allen_', '').replace('_', ' ').strip()
        title = f"{base}: {part['structure']}" if part.get('structure') else base
        titles[part['name']] = {'title': title[:1].upper() + title[1:]}
    return titles


# Flow colours in the 3D view (bright, for the dark panel); same hues as the 2D diagram.
FLOW_COLORS_3D = {'filtration': [0.31, 0.76, 0.97], 'tubular_secretion': [0.70, 0.53, 1.0],
                  'renal_excretion': [1.0, 0.79, 0.16], 'absorption': [0.96, 0.56, 0.69]}
# Largest tube diameter (metres): the whole normal-function clearance through one tube would be this wide.
TUBE_DIAMETER_AT_SCALE_M = 0.02
STATUS_OUTLINE = {'calibrated': None, 'checked_consistent': None, 'consistent_primary_only': 'caution',
                  'check_disagrees': 'warning'}


def _fmt(value):
    return f'{value:.0f}'


def evidence_cards(view):
    """What selecting a simulation organ shows. Numbers are copied from the body-map view; context organs get none."""
    flows = {f['kind']: f for f in view['flows']}
    band, totals, normal = view['band'], view['totals'], view['normal_reference']
    source = ('Simulation 2.0a lenalidomide pathway model (intact-nephron reading, calibrated at creatinine clearance '
              f"{view['model']['calibration_crcl_ml_min']:g} mL/min); view {view['view_sha256'][:12]}.")
    f, s, r, n = flows['filtration'], flows['tubular_secretion'], flows['renal_excretion'], flows['non_renal']
    return {
        'kidney': {'title': 'Kidneys: filtration and tubular secretion', 'status': band['status'], 'status_text': band['status_text'],
                   'rows': [['Filtration', f"{_fmt(f['value'])} mL/min ({_fmt(f['alternative_value'])} with fu 0.60)"],
                            ['Tubular secretion', f"{_fmt(s['value'])} mL/min ({_fmt(s['alternative_value'])} with fu 0.60)"],
                            ['Renal total', f"{_fmt(r['value'])} mL/min, {100 * r['share_of_elimination']:.0f}% of elimination"]],
                   'basis': [f['basis'], s['basis']], 'source': source},
        'urine': {'title': 'Ureters and bladder: unchanged drug in urine', 'status': band['status'], 'status_text': band['status_text'],
                  'rows': [['Into urine', f"{_fmt(r['value'])} mL/min"],
                           ['Dose leaving unchanged in urine', f"{100 * totals['fraction_excreted_unchanged']:.0f}% (normal function {100 * normal['fraction_excreted_unchanged']:.0f}%)"]],
                  'basis': [r['basis']], 'source': source},
        'plasma': {'title': 'Blood (plasma)', 'status': 'calibrated', 'status_text': None,
                   'rows': [['Total clearance from plasma', f"{_fmt(totals['total_ml_min'])} mL/min"],
                            ['Non-renal routes', f"{_fmt(n['value'])} mL/min (routes not identified; held constant)"],
                            ['Typical exposure at the same dose', f"about {totals['relative_exposure_same_dose']:.1f}x the normal-function reference"]],
                   'basis': ['The heart and vessels stand for the blood; the heart itself carries no separate number.', n['basis']],
                   'source': source},
        'gut': {'title': 'Small intestine: oral dose', 'status': None, 'status_text': None,
                'rows': [['Absorption', 'drawn without a value']],
                'basis': [flows['absorption']['note']], 'source': source},
    }


def viewer_config(manifest, view=None, paths=None):
    assets = viewer_assets(manifest)
    config = {
        'models': [{'url': url_for('landscape.static', filename=m['static_path']), 'class': m['class'],
                    'sha256': m['sha256']} for m in assets['models']],
        'parts': _part_titles(manifest),
        'node_labels': {n['id']: n['label'] for n in NODES},
        'context_label': CONTEXT_LABEL,
        'camera_presets': CAMERA_PRESETS,
    }
    if view is not None and paths is not None and view.get('status') == 'completed':
        flows = {f['kind']: f for f in view['flows']}
        config['flows'] = {
            'paths': paths['paths'], 'anchors': paths['anchors'],
            'values': {kind: (flows[kind]['value'] if flows[kind]['value'] is not None else None) for kind in flows},
            'scale_ml_min': view['drawing_scale']['max_flow_ml_min'],
            'tube_diameter_at_scale_m': TUBE_DIAMETER_AT_SCALE_M,
            'colors': FLOW_COLORS_3D,
            'labels': {'renal': f"Into the kidneys: filtration {_fmt(flows['filtration']['value'])} + secretion {_fmt(flows['tubular_secretion']['value'])} mL/min",
                       'urine': f"Into urine: {_fmt(flows['renal_excretion']['value'])} mL/min ({100 * view['totals']['fraction_excreted_unchanged']:.0f}% of the dose)",
                       'non_renal': f"Non-renal: {_fmt(flows['non_renal']['value'])} mL/min, routes not identified",
                       'absorption': 'Absorbed into the blood (no value drawn)'},
            'band': {'id': view['band']['id'], 'status': view['band']['status'], 'text': view['band']['status_text'],
                     'outline': STATUS_OUTLINE[view['band']['status']]},
        }
        config['cards'] = evidence_cards(view)
    return config


def flow_widths(view):
    """Line widths proportional to clearance on the view's fixed scale (the normal-function total)."""
    top = view['drawing_scale']['max_flow_ml_min']
    return {f['kind']: max(1.5, MAX_STROKE * f['value'] / top) for f in view['flows'] if f['value'] is not None}


def _context(view):
    try:
        return body_map_context(view), None
    except (BodyMapContextError, ValueError, OSError) as exc:
        return None, str(exc)


def _page_parts(view):
    done = view['status'] == 'completed'
    manifest, config, assets_error = None, None, None
    if done:
        try:
            manifest = load_manifest()
            config = viewer_config(manifest, view, load_paths())
        except (BodyMapAssetError, BodyMapPathError) as exc:
            assets_error = str(exc)
    return done, manifest, config, assets_error


def parse_crcl(raw):
    """The explorer's creatinine clearance from the query string: a finite decimal number, or None if absent."""
    if raw is None:
        return None
    text = raw.strip()
    if not text or len(text) > 12:
        raise ValueError('Enter creatinine clearance as a number of mL/min.')
    try:
        value = float(text)
    except ValueError:
        raise ValueError('Enter creatinine clearance as a number of mL/min.') from None
    if value != value or value in (float('inf'), float('-inf')):
        raise ValueError('Enter creatinine clearance as a number of mL/min.')
    return value


def register_body_map_pages(bp):
    @bp.get('/patient-lab/body-map')
    def body_map_explorer():
        if set(request.args) - {'format', 'crcl'} or any(len(request.args.getlist(k)) != 1 for k in request.args):
            abort(400)
        fmt = request.args.get('format', 'html')
        if fmt not in ('html', 'json'):
            abort(400)
        try:
            crcl = parse_crcl(request.args.get('crcl'))
        except ValueError:
            abort(400)
        if crcl is None:
            crcl = float(EXPLORER_DEFAULT_CRCL)
        view = explorer_map(crcl)
        done = view['status'] == 'completed'
        context, context_error = _context(view) if done else (None, None)
        headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
        if fmt == 'json':
            headers['Content-Disposition'] = f'attachment; filename="body-map-explorer-crcl-{crcl:g}.json"'
            body = {'body_map_view': view, 'observed_context': context}
            return Response(json.dumps(body, indent=2, allow_nan=False) + '\n', mimetype='application/json', headers=headers)
        done, manifest, config, assets_error = _page_parts(view)
        response = _response(
            'landscape_body_map.html', scenario=None, revision=None, view=view, done=done, explorer=True,
            context=context, context_error=context_error,
            explorer_control={'value': crcl, 'min': RANGE[0], 'max': RANGE[1], 'step': EXPLORER_STEP,
                              'default': EXPLORER_DEFAULT_CRCL},
            result_type=RESULT_TYPES['elimination_pathway_split_explorer'], config=config, assets_error=assets_error,
            legend=LEGEND, presets=CAMERA_PRESETS, colors=COLORS, widths=flow_widths(view) if done else None,
            flows={f['kind']: f for f in view['flows']} if done else None,
            attribution=[s['attribution'] for s in manifest['sources'].values()] if manifest else [],
            record=record_for_body_map_explorer(view, context) if done else None)
        response.headers.update(headers)
        return response

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
                    config = viewer_config(manifest, view, load_paths())
                except (BodyMapAssetError, BodyMapPathError) as exc:
                    assets_error = str(exc)
            pathways_view = patient_renal_pathways(revision_id) if done else None
            context, context_error = _context(view) if done else (None, None)
            response = _response(
                'landscape_body_map.html', scenario=scenario, revision=revision, view=view, done=done, explorer=False,
                context=context, context_error=context_error,
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
