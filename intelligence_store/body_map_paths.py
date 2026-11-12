"""Digital human 1.0, step 1.3c: where the body map draws its flows, derived from the pinned 3D models.

The paths are geometry for drawing, not anatomy claims or a model: each one is computed from the simulation-organ GLB
(step 1.3a) with fixed rules, so anyone can rebuild them and get the same file (body-map-flow-paths-v1 schema; file v3).

- Cleared by each kidney (paths v4, Track H items 2 and 3): filtration and secretion are drawn inside the kidney, from a
  point in the outer cortex (the mean of the cortex vertices in the outermost tenth across the body), through the
  centre of the renal pyramids (medulla) and the papillae, to that side's renal pelvis: the route of the tubular fluid.
  Each kidney carries half of each flow. Paths v1-v3 drew them as two tubes inside the renal artery, from the aorta to
  the kidney's centre; neither process happens in the artery. v3 is kept unchanged for traceability.
- The renal artery lines (from the centre of the aorta at the artery's origin, along its centre line from
  body_map_vessel_lines_v1.json, to the kidney's centre) are kept for the blood layer only ('arterial_lines'); they carry
  no drug flow.
- Into urine (paths v4, item 11): from each renal pelvis down the centre line of its own ureter to the ureter's lower
  end, where it opens into the bladder; the two ureters no longer meet at the bladder's centre.
- Absorption (paths v3, Track H item 1): from the small intestine to the nearest point of the superior mesenteric
  vein, up that vein and the hepatic portal vein to the liver, then straight through the liver to the inferior vena
  cava where the hepatic veins join it. Centre lines from body_map_portal_route_lines_v1.json. Drawn without a value;
  the liver is passed through, not modelled: no loss in the liver. Paths v2 drew a straight line from the intestine to
  the vena cava at renal-artery level, a vessel connection that does not exist; v2 is kept unchanged for traceability.
- Non-renal elimination is not drawn as a path: the organ is not known, so the page shows it as a label at the aorta,
  pointing nowhere in particular.
Only simulation organs are used. Context organs (decision 5) never anchor a flow.
"""
import hashlib
import json
from pathlib import Path

import numpy as np

from . import glb_mesh

DATA = Path(__file__).parent / 'data'
ROOT = Path(__file__).resolve().parents[1]
PATHS_FILE = DATA / 'body_map_flow_paths_v4.json'
PATHS_SHA256 = 'f1cdb6d14b09556d8d95e258fe6efdb92767f9190a158b32a63ee5506de18b60'
# Superseded, kept unchanged for traceability: body_map_flow_paths_v3.json (kidney flows drawn inside the renal artery)
PATHS_V3_SHA256 = 'df8482e93c28633fb86152c782c84523bbc7349bd55a7803f36f9963bb5dff94'
# Superseded, kept unchanged for traceability: body_map_flow_paths_v2.json (absorption drawn straight to the vena cava)
PATHS_V2_SHA256 = '8f6df6c623513cdae9404799cd498bd2946bb0dc725a4b17f8b31e25b0a1149a'
# Superseded, kept unchanged for traceability: body_map_flow_paths_v1.json (kidney flows started in front of the aorta)
PATHS_V1_SHA256 = 'd85eb44f468773921647d13448be67df6fff91e61dbd3d2b7f3abd2a3c81cbda'
VESSELS_FILE = DATA / 'body_map_vessel_lines_v1.json'
VESSELS_SHA256 = '310244d195951b1e6ff6e9864f78ae41bc0b5bc248d51451a2f5ff98d55b0238'
VEINS_FILE = DATA / 'body_map_renal_vein_lines_v1.json'
VEINS_SHA256 = '12f9b5763291d4121ed7178a4c34e196a8c72a49a5cd2a24383aa4e6f981ec41'
PORTAL_FILE = DATA / 'body_map_portal_route_lines_v1.json'
PORTAL_SHA256 = '5547b30e84ea29e501b8bc8342f36855567de1b80d446eaaf651bfc0e7b917d3'
SCHEMA_VERSION = 'body-map-flow-paths-v1'
METHOD_VERSION = 'body-map-flow-paths-build-v4.0'
CORTEX_OUTER_FRACTION = 0.1
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


def load_portal_lines():
    raw = PORTAL_FILE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PORTAL_SHA256:
        raise BodyMapPathError('The portal route centre lines are missing or changed; flow paths are not built.')
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


def compute_paths(raw, vessels=None, portal=None):
    vessels = vessels or load_vessel_lines()
    portal = portal or load_portal_lines()
    parts = _parts(raw)
    pelvis = parts['VH_M_renal_pelvis_ureter:renal pelvis and calyces']
    bladder = _centre(parts['VH_M_urinary_bladder'])
    aorta_line = vessels['aorta']['points']
    paths, anchors, origins, arterial = [], {}, [], {}
    for side, sign in (('left', 1), ('right', -1)):
        group = f'VH_M_{side}_kidney'
        kidney = _centre(parts[f'{group}:kidney capsule'])
        artery = [np.array(p) for p in vessels['renal_arteries'][side]['points']]
        if np.sign(artery[-1][0]) != sign or np.sign(kidney[0]) != sign:
            raise BodyMapPathError(f'The {side} renal artery and kidney are not on the same side.')
        aorta = _at_height(aorta_line, float(artery[0][1]))
        origins.append(float(artery[0][1]))
        arterial[side] = [aorta] + artery + [kidney]
        cortex = parts[f'{group}:renal cortex']
        outer = cortex[np.abs(cortex[:, 0]) >= np.quantile(np.abs(cortex[:, 0]), 1 - CORTEX_OUTER_FRACTION)].mean(axis=0)
        medulla = parts[f'{group}:renal pyramids'].mean(axis=0)
        papillae = parts[f'{group}:renal papillae'].mean(axis=0)
        side_pelvis = pelvis[pelvis[:, 0] * sign > 0].mean(axis=0)
        paths.append({'id': f'renal_clearance_{side}', 'flows': ['filtration', 'tubular_secretion'], 'share_per_path': 0.5,
                      'side': side, 'from_node': 'plasma', 'to_node': 'kidney',
                      'route': ['outer renal cortex', 'renal pyramids (medulla)', 'renal papillae', 'renal pelvis'],
                      'points': [outer, medulla, papillae, side_pelvis]})
        ureter = _centre_line(parts[f'VH_M_renal_pelvis_ureter:{side} ureter'], URETER_SAMPLES)
        paths.append({'id': f'urine_{side}', 'flows': ['renal_excretion'], 'share_per_path': 0.5, 'side': side,
                      'from_node': 'kidney', 'to_node': 'urine',
                      'points': [side_pelvis] + list(ureter)})
        anchors[f'kidney_{side}'] = kidney
    gut = parts['VH_M_small_intestine'].mean(axis=0)
    renal_level = float(np.mean(origins))
    smv = [np.array(p) for p in portal['superior_mesenteric_vein']['points']]
    join = min(range(len(smv)), key=lambda i: float(np.linalg.norm(smv[i] - gut)))
    hpv = [np.array(p) for p in portal['hepatic_portal_vein']['points']]
    hepatic_ivc = np.array(portal['hepatic_veins_at_vena_cava']['inferior_vena_cava_point'])
    paths.append({'id': 'absorption', 'flows': ['absorption'], 'share_per_path': 1.0, 'side': None,
                  'from_node': 'gut', 'to_node': 'plasma',
                  'route': ['small intestine', 'superior mesenteric vein', 'hepatic portal vein', 'liver (passed through, not modelled)',
                            'inferior vena cava at the hepatic veins'],
                  'points': [gut] + smv[join:] + hpv + [hepatic_ivc]})
    anchors.update(aorta_renal_level=_at_height(aorta_line, renal_level), bladder=bladder, gut=gut)
    rounded = lambda p: [round(float(x), DECIMALS) for x in p]
    return {
        'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION,
        'source_model': {'file': SOURCE_MODEL, 'sha256': hashlib.sha256(raw).hexdigest()},
        'vessel_lines': {'file': 'intelligence_store/data/' + VESSELS_FILE.name, 'sha256': VESSELS_SHA256},
        'portal_route_lines': {'file': 'intelligence_store/data/' + PORTAL_FILE.name, 'sha256': PORTAL_SHA256},
        'coordinate_frame': 'HRA Visible Human male reference body; metres; +y up; body left is +x.',
        'not_this': 'Drawing paths only: where flows are drawn, not anatomical claims, measurements or a model.',
        'paths': [dict(p, points=[rounded(x) for x in p['points']]) for p in paths],
        'arterial_lines': {side: [rounded(x) for x in pts] for side, pts in arterial.items()},
        'anchors': {k: rounded(v) for k, v in sorted(anchors.items())},
    }


def load_vein_lines():
    raw = VEINS_FILE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != VEINS_SHA256:
        raise BodyMapPathError('The renal vein centre lines are missing or changed; blood flow is not drawn.')
    return json.loads(raw)


def blood_paths(paths=None, vessels=None, veins=None):
    """Digital human 1.1c: where reference blood flow is drawn (drawing geometry only; no value is attached here).

    In: along each renal artery line (aorta, renal artery, kidney's centre). Out: from the kidney's centre along its renal
    vein to the inferior vena cava at the vein's own height. Built from pinned files, so it is the same on every page.
    """
    paths = paths or load_paths()
    vessels = vessels or load_vessel_lines()
    veins = veins or load_vein_lines()
    rounded = lambda p: [round(float(x), DECIMALS) for x in p]
    out = []
    for side in ('left', 'right'):
        inflow = paths['arterial_lines'][side]
        out.append({'id': f'blood_in_{side}', 'kind': 'arterial', 'side': side, 'points': inflow})
        vein = veins['renal_veins'][side]['points']
        ivc = _at_height(vessels['inferior_vena_cava']['points'], float(vein[0][1]))
        out.append({'id': f'blood_out_{side}', 'kind': 'venous', 'side': side,
                    'points': [inflow[-1]] + list(reversed(vein)) + [rounded(ivc)]})
    return out


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
