"""Digital human 1.0, step 1.3c: where the body map draws its flows, derived from the pinned 3D models.

The paths are geometry for drawing, not anatomy claims or a model: each one is computed from the simulation-organ GLB
(step 1.3a) with fixed rules, so anyone can rebuild them and get the same file (body-map-flow-paths-v1).

- Into each kidney (paths v2): from the centre of the aorta at the renal artery's origin, along the centre line of that
  renal artery, to the kidney's centre. The centre lines come from body_map_vessel_lines_v1.json, extracted from the
  named Atlas vessels, because the route model merges all arteries into one part. Paths v1 took the aorta point from
  that merged part and so started each kidney flow 2-4 cm in front of the aorta, off the renal arteries; v1 is kept
  unchanged for traceability. Filtration and secretion are drawn as two strands along this path; each kidney carries
  half of each flow.
- Into urine: from each renal pelvis down the centre line of its ureter to the bladder.
- Absorption: from the small intestine into the blood (the centre of the inferior vena cava at renal-artery level),
  drawn without a value.
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
PATHS_FILE = DATA / 'body_map_flow_paths_v2.json'
PATHS_SHA256 = '8f6df6c623513cdae9404799cd498bd2946bb0dc725a4b17f8b31e25b0a1149a'
# Superseded, kept unchanged for traceability: body_map_flow_paths_v1.json (kidney flows started in front of the aorta)
PATHS_V1_SHA256 = 'd85eb44f468773921647d13448be67df6fff91e61dbd3d2b7f3abd2a3c81cbda'
VESSELS_FILE = DATA / 'body_map_vessel_lines_v1.json'
VESSELS_SHA256 = '310244d195951b1e6ff6e9864f78ae41bc0b5bc248d51451a2f5ff98d55b0238'
SCHEMA_VERSION = 'body-map-flow-paths-v1'
METHOD_VERSION = 'body-map-flow-paths-build-v2.0'
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


def load_vessel_lines():
    raw = VESSELS_FILE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != VESSELS_SHA256:
        raise BodyMapPathError('The body map vessel centre lines are missing or changed; flow paths are not built.')
    return json.loads(raw)


def _at_height(points, y):
    """A vertical centre line (ordered by height) interpolated at height y."""
    pts = np.array(sorted(points, key=lambda p: p[1]))
    if not pts[0][1] <= y <= pts[-1][1]:
        raise BodyMapPathError(f'Height {y:.3f} m is outside the vessel centre line.')
    return np.array([np.interp(y, pts[:, 1], pts[:, i]) for i in range(3)])


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


def compute_paths(raw, vessels=None):
    vessels = vessels or load_vessel_lines()
    parts = _parts(raw)
    pelvis = parts['VH_M_renal_pelvis_ureter:renal pelvis and calyces']
    bladder = _centre(parts['VH_M_urinary_bladder'])
    aorta_line = vessels['aorta']['points']
    paths, anchors, origins = [], {}, []
    for side, sign in (('left', 1), ('right', -1)):
        group = f'VH_M_{side}_kidney'
        kidney = _centre(np.vstack([parts[f'{group}:kidney capsule']]))
        artery = [np.array(p) for p in vessels['renal_arteries'][side]['points']]
        if np.sign(artery[-1][0]) != sign or np.sign(kidney[0]) != sign:
            raise BodyMapPathError(f'The {side} renal artery and kidney are not on the same side.')
        aorta = _at_height(aorta_line, float(artery[0][1]))
        origins.append(float(artery[0][1]))
        paths.append({'id': f'renal_inflow_{side}', 'flows': ['filtration', 'tubular_secretion'], 'share_per_path': 0.5,
                      'side': side, 'from_node': 'plasma', 'to_node': 'kidney',
                      'points': [aorta] + artery + [kidney]})
        side_pelvis = pelvis[pelvis[:, 0] * sign > 0]
        ureter = _centre_line(parts[f'VH_M_renal_pelvis_ureter:{side} ureter'], URETER_SAMPLES)
        paths.append({'id': f'urine_{side}', 'flows': ['renal_excretion'], 'share_per_path': 0.5, 'side': side,
                      'from_node': 'kidney', 'to_node': 'urine',
                      'points': [side_pelvis.mean(axis=0)] + list(ureter) + [bladder]})
        anchors[f'kidney_{side}'] = kidney
    gut = parts['VH_M_small_intestine'].mean(axis=0)
    renal_level = float(np.mean(origins))
    ivc = _at_height(vessels['inferior_vena_cava']['points'], renal_level)
    paths.append({'id': 'absorption', 'flows': ['absorption'], 'share_per_path': 1.0, 'side': None,
                  'from_node': 'gut', 'to_node': 'plasma', 'points': [gut, ivc]})
    anchors.update(aorta_renal_level=_at_height(aorta_line, renal_level), bladder=bladder, gut=gut)
    rounded = lambda p: [round(float(x), DECIMALS) for x in p]
    return {
        'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION,
        'source_model': {'file': SOURCE_MODEL, 'sha256': hashlib.sha256(raw).hexdigest()},
        'vessel_lines': {'file': 'intelligence_store/data/' + VESSELS_FILE.name, 'sha256': VESSELS_SHA256},
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
