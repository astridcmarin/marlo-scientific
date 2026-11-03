"""Extract vessel centre lines for the body map flow paths from the HRA United male set (Digital human 1.0, paths v2).

    PYTHONPATH=. python scripts/build_body_map_vessel_lines.py /path/to/3d-vh-m-united.glb

The route model merges all arteries into one part, so the renal arteries and the aorta cannot be told apart in it
(paths v1 placed the start of each kidney flow 2-4 cm in front of the aorta). This script reads the original Atlas
file, which names each vessel, and writes centre lines for the abdominal aorta, the two renal arteries and the inferior
vena cava to intelligence_store/data/body_map_vessel_lines_v1.json. The source file stays on the owner's computer;
its SHA-256 is checked before anything is read.

Centre lines are geometry for drawing, not measurements. Each point is the middle of the vessel's bounding box in a
thin slice: height slices for the aorta and vena cava, slices across the body for the renal arteries.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from intelligence_store import glb_mesh

SOURCE_SHA256 = 'fae3ac193835e9e24cd13a0d0f11e6788183b290b0691b9b83ec81d907d94581'
OUT = Path(__file__).resolve().parents[1] / 'intelligence_store' / 'data' / 'body_map_vessel_lines_v1.json'
DECIMALS = 4
HEIGHT_RANGE = (0.24, 0.36)      # metres; covers both renal artery origins and both kidney hila
HEIGHT_STEP = 0.005
SLICE_HALF = 0.002
ARTERY_BINS = 12


def _slices_by_height(vertices):
    points = []
    for y in np.arange(HEIGHT_RANGE[0], HEIGHT_RANGE[1] + 1e-9, HEIGHT_STEP):
        s = vertices[np.abs(vertices[:, 1] - y) < SLICE_HALF]
        if len(s) >= 6:
            mid = (s.min(axis=0) + s.max(axis=0)) / 2
            mid[1] = y
            points.append(mid)
    return points


def _slices_across(vertices):
    """Centre line of a mostly horizontal vessel, ordered from the midline outwards."""
    x = vertices[:, 0]
    inner, outer = (x.min(), x.max()) if abs(x.min()) < abs(x.max()) else (x.max(), x.min())
    edges = np.linspace(inner, outer, ARTERY_BINS + 1)
    points = []
    for a, b in zip(edges[:-1], edges[1:]):
        lo, hi = min(a, b), max(a, b)
        s = vertices[(x >= lo) & (x <= hi)]
        if len(s) >= 6:
            points.append((s.min(axis=0) + s.max(axis=0)) / 2)
    return points


def build(raw):
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise SystemExit('This is not the pinned HRA United male file (SHA-256 differs).')
    gltf, binary = glb_mesh.read_glb(raw)
    by_name = {}
    for part in glb_mesh.mesh_nodes(gltf, binary):
        by_name.setdefault(part['name'], []).append(part['vertices'])
    get = lambda *names: np.vstack([v for n in names for v in by_name[n]])
    rounded = lambda pts: [[round(float(c), DECIMALS) for c in p] for p in pts]
    arteries = {}
    for atlas_name in ('VH_M_left_renal_artery', 'VH_M_right_renal_artery'):
        v = get(atlas_name)
        body_side = 'left' if np.median(v[:, 0]) > 0 else 'right'   # body left is +x in this frame
        arteries[body_side] = {'atlas_node': atlas_name, 'points': rounded(_slices_across(v))}
    return {
        'schema_version': 'body-map-vessel-lines-v1',
        'source': {'file': '3d-vh-m-united.glb', 'set': 'HRA 3D Reference Organ Set for United, Male', 'sha256': SOURCE_SHA256,
                   'licence': 'CC BY 4.0', 'storage': "Kept on the platform owner's computer; not committed."},
        'coordinate_frame': 'HRA Visible Human male reference body; metres; +y up; body left is +x.',
        'method': (f'Middle of the bounding box of each vessel in thin slices: height slices every {HEIGHT_STEP} m '
                   f'(half-width {SLICE_HALF} m) from {HEIGHT_RANGE[0]} to {HEIGHT_RANGE[1]} m for the aorta and inferior '
                   f'vena cava; {ARTERY_BINS} slices across the body for each renal artery, ordered from the midline out.'),
        'not_this': 'Drawing geometry only: not measurements of vessel size, position or flow.',
        'aorta': {'atlas_node': 'VH_M_descending_aorta_b', 'points': rounded(_slices_by_height(get('VH_M_descending_aorta_b')))},
        'inferior_vena_cava': {'atlas_node': 'VH_M_inferior_vena_cava_a + VH_M_inferior_vena_cava_b',
                               'points': rounded(_slices_by_height(get('VH_M_inferior_vena_cava_a', 'VH_M_inferior_vena_cava_b')))},
        'renal_arteries': arteries,
        'naming_note': ('The Atlas node named "left renal artery" lies on the body\'s right (-x) and "right renal artery" on '
                        'the body\'s left (+x), opposite to the kidneys, whose sides were confirmed in step 1.3a. Sides here '
                        'are assigned by position, and the Atlas node name is kept for traceability.'),
    }


if __name__ == '__main__':
    data = build(Path(sys.argv[1]).read_bytes())
    OUT.write_text(json.dumps(data, indent=1) + '\n')
    print(hashlib.sha256(OUT.read_bytes()).hexdigest())
