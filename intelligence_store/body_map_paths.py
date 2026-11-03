"""Digital human 1.0, step 1.3c: where the body map draws its flows, derived from the pinned 3D models.

The paths are geometry for drawing, not anatomy claims or a model: each one is computed from the simulation-organ GLB
(step 1.3a) with fixed rules, so anyone can rebuild them and get the same file (body-map-flow-paths-v1).

- Into each kidney: from the aorta at the level of that kidney's hilum, through the hilum, to the kidney's centre.
  Filtration and secretion are drawn as two strands along this path; each kidney carries half of each flow.
- Into urine: from each renal pelvis down the centre line of its ureter to the bladder.
- Absorption: from the small intestine into the blood (the inferior vena cava at kidney level), drawn without a value.
  It does not pass through the liver: the model has no first-pass or liver step.
- Non-renal elimination is not drawn as a path: the routes are not identified, so the page shows it as a label at the
  aorta, pointing nowhere in particular.
Only simulation organs are used. Context organs (decision 5) never anchor a flow.
"""
import hashlib
import json
from pathlib import Path

import numpy as np

from . import glb_mesh

DATA = Path(__file__).parent / 'data'
ROOT = Path(__file__).resolve().parents[1]
PATHS_FILE = DATA / 'body_map_flow_paths_v1.json'
PATHS_SHA256 = 'd85eb44f468773921647d13448be67df6fff91e61dbd3d2b7f3abd2a3c81cbda'
SCHEMA_VERSION = 'body-map-flow-paths-v1'
METHOD_VERSION = 'body-map-flow-paths-build-v1.0'
SOURCE_MODEL = 'landscape_ui/static/body-map/models/body-route-male-v1.glb'
URETER_SAMPLES = 20
DECIMALS = 4


class BodyMapPathError(ValueError):
    pass


def _parts(raw):
    gltf, binary = glb_mesh.read_glb(raw)
    parts = {}
    for part in glb_mesh.mesh_nodes(gltf, binary):
        if part['extras'].get('class') != 'simulation':
            raise BodyMapPathError(f"Part {part['name']!r} in the route model is not a simulation organ.")
        parts[part['name']] = part['vertices']
    return parts


def _centre(vertices):
    return (vertices.min(axis=0) + vertices.max(axis=0)) / 2


def _vessel_point(vertices, y, side):
    """Middle of a central vessel at height y: vertices within 1 cm of y and 4 cm of the midline, on one side or both."""
    near = vertices[(np.abs(vertices[:, 1] - y) < 0.01) & (np.abs(vertices[:, 0]) < 0.04)]
    if side == 'left':
        near = near[near[:, 0] > -0.005]
    elif side == 'right':
        near = near[near[:, 0] < 0.005]
    if len(near) < 3:
        raise BodyMapPathError(f'No central vessel found at height {y:.3f} m.')
    point = np.median(near, axis=0)
    point[1] = y
    return point


def _centre_line(vertices, samples):
    """A tube's centre line, top to bottom: the mean of its vertices in equal height slices."""
    top, bottom = vertices[:, 1].max(), vertices[:, 1].min()
    edges = np.linspace(top, bottom, samples + 1)
    points = []
    for upper, lower in zip(edges[:-1], edges[1:]):
        chosen = vertices[(vertices[:, 1] <= upper) & (vertices[:, 1] >= lower)]
        if len(chosen):
            points.append(chosen.mean(axis=0))
    return np.array(points)


def compute_paths(raw):
    parts = _parts(raw)
    arteries = parts['VH_M_blood_vasculature:arteries']
    veins = parts['VH_M_blood_vasculature:veins']
    pelvis = parts['VH_M_renal_pelvis_ureter:renal pelvis and calyces']
    bladder = _centre(parts['VH_M_urinary_bladder'])
    paths, anchors = [], {}
    for side, sign in (('left', 1), ('right', -1)):
        group = f'VH_M_{side}_kidney'
        kidney = _centre(np.vstack([parts[f'{group}:kidney capsule']]))
        hilum = parts[f'{group}:hilum of kidney'].mean(axis=0)
        aorta = _vessel_point(arteries, float(hilum[1]), None)
        paths.append({'id': f'renal_inflow_{side}', 'flows': ['filtration', 'tubular_secretion'], 'share_per_path': 0.5,
                      'side': side, 'from_node': 'plasma', 'to_node': 'kidney', 'points': [aorta, hilum, kidney]})
        side_pelvis = pelvis[pelvis[:, 0] * sign > 0]
        ureter = _centre_line(parts[f'VH_M_renal_pelvis_ureter:{side} ureter'], URETER_SAMPLES)
        paths.append({'id': f'urine_{side}', 'flows': ['renal_excretion'], 'share_per_path': 0.5, 'side': side,
                      'from_node': 'kidney', 'to_node': 'urine',
                      'points': [side_pelvis.mean(axis=0)] + list(ureter) + [bladder]})
        anchors[f'kidney_{side}'] = kidney
    gut = parts['VH_M_small_intestine'].mean(axis=0)
    renal_level = float(np.mean([p['points'][1][1] for p in paths if p['id'].startswith('renal_inflow')]))
    ivc = _vessel_point(veins, renal_level, 'right')
    paths.append({'id': 'absorption', 'flows': ['absorption'], 'share_per_path': 1.0, 'side': None,
                  'from_node': 'gut', 'to_node': 'plasma', 'points': [gut, ivc]})
    anchors.update(aorta_renal_level=_vessel_point(arteries, renal_level, None), bladder=bladder, gut=gut)
    rounded = lambda p: [round(float(x), DECIMALS) for x in p]
    return {
        'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION,
        'source_model': {'file': SOURCE_MODEL, 'sha256': hashlib.sha256(raw).hexdigest()},
        'coordinate_frame': 'HRA Visible Human male reference body; metres; +y up; body left is +x.',
        'not_this': 'Drawing paths only: where flows are drawn, not anatomical claims, measurements or a model.',
        'paths': [dict(p, points=[rounded(x) for x in p['points']]) for p in paths],
        'anchors': {k: rounded(v) for k, v in sorted(anchors.items())},
    }


def load_paths():
    raw = PATHS_FILE.read_bytes()
    if PATHS_SHA256 is None or hashlib.sha256(raw).hexdigest() != PATHS_SHA256:
        raise BodyMapPathError('The body map flow paths are missing or changed; flows are not drawn.')
    return json.loads(raw)


def write_paths():
    """Rebuild the paths file from the committed route model (run from the repository root)."""
    data = compute_paths((ROOT / SOURCE_MODEL).read_bytes())
    PATHS_FILE.write_text(json.dumps(data, indent=2) + '\n')
    return hashlib.sha256(PATHS_FILE.read_bytes()).hexdigest()
