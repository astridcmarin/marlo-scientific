"""Build the body map's 3D assets from the HRA United male reference organ set (Digital human 1.0, step 1.3a).

Usage (from the repository root; the source files stay on the owner's computer, outside git):

    PYTHONPATH=. python scripts/build_body_map_assets.py \\
        --source "supplemental-information/hra-3d/male/3D Reference Organ Set for United, Male/3d-vh-m-united.glb" \\
        --stomach supplemental-information/hra-3d/male/stomach.glb

It checks each source file's SHA-256, keeps the parts listed below and leaves out the rest (each exclusion has a
reason), simplifies every kept part to a triangle budget, and writes two GLBs plus a manifest:

    landscape_ui/static/body-map/models/body-route-male-v1.glb    simulation organs (lenalidomide elimination route)
    landscape_ui/static/body-map/models/body-context-male-v1.glb  context organs (anatomy for orientation only)
    intelligence_store/data/body_map_assets_v1.json               manifest: sources, licences, checksums, parts, checks

Every part keeps its HRA node name, label and UBERON ID. Simulation parts also name the body-map-view-v1 node they
draw (gut, plasma, kidney, urine). Context parts name none, so they can never carry a model result (plan, decision 5).

Rebuilding on another computer gives the same parts and checks; the bytes can differ in the last digit of floating
point, so the committed GLBs, pinned in the manifest, are the reference.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from intelligence_store import glb_mesh

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / 'landscape_ui' / 'static' / 'body-map' / 'models'
MANIFEST = ROOT / 'intelligence_store' / 'data' / 'body_map_assets_v1.json'
SCHEMA_VERSION = 'body-map-assets-v1'
BUILD_VERSION = 'body-map-assets-build-v1.0'

SOURCE = {
    'file': '3d-vh-m-united.glb',
    'title': '3D Reference Organ Set for United, Male',
    'publisher': 'Human Reference Atlas (HRA), HuBMAP; NIH Common Fund',
    'body': 'Visible Human male (VH_M)',
    'licence': 'CC BY 4.0',
    'licence_url': 'https://creativecommons.org/licenses/by/4.0/',
    'attribution': 'Human Reference Atlas 3D Reference Object Library (HuBMAP), CC BY 4.0. Simplified for the web.',
    'source_page': 'https://humanatlas.io/3d-reference-library',
    'sha256': None,       # set after the owner's checksum is confirmed
    'bytes': 241633636,
    'hra_version': None,  # owner to record from the download page
}
STOMACH = {
    'file': 'stomach.glb',
    'title': 'Stomach',
    'publisher': 'Innerscene Corp (innerscene.com)',
    'licence': 'CC0 1.0 (public domain)',
    'licence_url': 'https://creativecommons.org/publicdomain/zero/1.0/',
    'attribution': 'Stomach: Innerscene, CC0. Not part of the reference body; placed by hand (approximate).',
    'sha256': None,
    'bytes': 1802672,
    'ontology_id': 'UBERON:0000945',
}

# Simulation organs: drawn in colour, carry body-map-view-v1 results. (source subtree root, body-map node, budget)
ROUTE = [
    ('VH_M_small_intestine', 'gut', 15000),
    ('VH_M_blood_vasculature', 'plasma', 60000),
    ('VH_M_heart', 'plasma', 15000),
    ('VH_M_left_kidney', 'kidney', 30000),
    ('VH_M_right_kidney', 'kidney', 30000),
    ('VH_M_renal_pelvis_ureter', 'urine', 15000),
    ('VH_M_urinary_bladder', 'urine', 5000),
    ('VH_M_urethra', 'urine', 2000),
]
# Context organs: faint, fixed, never carry a result. (source subtree root, budget)
CONTEXT = [
    ('VH_M_skin', 30000), ('Allen_brain', 15000), ('VH_M_spinal_cord', 3000),
    ('VH_M_lungs', 12000), ('VH_M_tracheobronchial_tree', 10000), ('VH_M_larynx', 3000),
    ('VH_M_liver', 10000), ('VH_M_gallbladder_', 1500), ('VH_M_biliary_tree', 3000), ('VH_M_pancreas', 4000),
    ('VH_M_colon', 10000), ('VH_M_spleen', 3000), ('VH_M_thymus', 1500),
    ('VH_M_vertebral_column', 25000), ('VH_M_pelvis', 12000), ('VH_M_lower_limb', 15000),
    ('VH_M_prostate_gland', 3000), ('VH_M_male_genital_duct', 3000),
]
STOMACH_BUDGET = 4000
EXCLUDED = {
    'VH_M_subcutaneous_abdominal_adipose_tissue': 'Fat layer; would hide the organs behind it.',
    'VH_M_visceral_adipose': 'Fat around the abdominal organs; would hide the elimination route.',
    'VH_M_mouth': 'Mouth and teeth: 1.9 million triangles, little value at whole-body scale.',
    'VH_M_eyes': 'Too small to read at whole-body scale; 0.7 million triangles.',
    'VH_M_nerves_of_eye': 'Too small to read at whole-body scale.',
    'VH_M_muscles_of_eye': 'Too small to read at whole-body scale.',
    'VH_M_muscles_of_knee': 'Isolated muscles; misleading without the rest of the musculature.',
    'VH_M_muscles_of_larynx': 'Too small to read at whole-body scale.',
    'VH_M_palatine_tonsil': 'Too small to read at whole-body scale.',
    'Yao_lymph_node': 'A single lymph node; misleading without the rest of the lymphatic system.',
    'VH_M_hyoid': 'Too small to read at whole-body scale.',
}
# Hand placement of the stomach (scene metres): left upper abdomen, between liver and spleen, below the diaphragm.
STOMACH_PLACEMENT = {'translation': [0.055, 0.335, 0.0], 'rotation_y_degrees': 0.0, 'note': 'approximate, by eye'}

MIN_PART_FACES = 40
MAX_BBOX_SHIFT_M = 0.003


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def _subtrees(gltf):
    """Map each node name to the set of its descendants' indices (including itself)."""
    nodes = gltf['nodes']
    memo = {}

    def walk(index):
        if index not in memo:
            out = {index}
            for child in nodes[index].get('children', []):
                out |= walk(child)
            memo[index] = out
        return memo[index]
    return {node.get('name'): walk(i) for i, node in enumerate(nodes)}


def _system_children(gltf):
    """Names of the children of the body's system nodes (the level at which parts are kept or excluded)."""
    nodes = gltf['nodes']
    root = nodes[gltf['scenes'][gltf.get('scene', 0)]['nodes'][0]]
    return [nodes[c]['name'] for s in root.get('children', []) for c in nodes[s].get('children', [])]


def _bbox(vertices):
    return [[round(float(x), 6) for x in vertices.min(axis=0)], [round(float(x), 6) for x in vertices.max(axis=0)]]


def _simplify_group(meshes, budget):
    """Simplify each mesh of a group, sharing the budget in proportion to source triangles."""
    total = sum(len(m['faces']) for m in meshes)
    parts = []
    for mesh in meshes:
        share = max(MIN_PART_FACES, int(round(budget * len(mesh['faces']) / total)))
        vertices, faces, cell = glb_mesh.simplify_to_target(mesh['vertices'], mesh['faces'], share)
        if len(faces) == 0:
            raise glb_mesh.GlbError(f"Part {mesh['name']!r} vanished during simplification.")
        source_box, out_box = np.array(_bbox(mesh['vertices'])), np.array(_bbox(vertices))
        shift = float(np.max(np.abs(source_box - out_box)))
        parts.append({'mesh': mesh, 'vertices': vertices, 'faces': faces, 'cell_m': round(cell, 6),
                      'bbox_shift_m': round(shift, 6)})
    return parts


def build(source_raw, stomach_raw):
    gltf, binary = glb_mesh.read_glb(source_raw)
    subtrees = _subtrees(gltf)
    listed = [r for r, *_ in ROUTE] + [r for r, _ in CONTEXT]
    unaccounted = sorted(set(_system_children(gltf)) - set(listed) - set(EXCLUDED))
    if unaccounted:
        raise glb_mesh.GlbError(f'Source parts neither kept nor excluded: {unaccounted}')
    missing = sorted(set(listed) - set(subtrees))
    if missing:
        raise glb_mesh.GlbError(f'Listed parts not found in the source: {missing}')
    meshes = list(glb_mesh.mesh_nodes(gltf, binary))

    def group(root):
        members = subtrees[root]
        return [m for m in meshes if m['index'] in members]

    skin = group('VH_M_skin')
    skin_box = _bbox(np.vstack([m['vertices'] for m in skin]))

    def entries(root, cls, node, budget):
        out = []
        for part in _simplify_group(group(root), budget):
            mesh, extras = part['mesh'], part['mesh']['extras']
            out.append({
                'name': mesh['name'], 'group': root, 'class': cls, 'body_map_node': node,
                'label': extras.get('label'), 'ontology_id': extras.get('ontologyid'),
                'source': 'hra_united_male', 'placement': 'reference_body',
                'source_faces': int(len(mesh['faces'])), 'faces': int(len(part['faces'])),
                'cell_m': part['cell_m'], 'bbox': _bbox(part['vertices']), 'bbox_shift_m': part['bbox_shift_m'],
                '_vertices': part['vertices'], '_faces': part['faces'],
            })
        return out

    route = [e for root, node, budget in ROUTE for e in entries(root, 'simulation', node, budget)]
    context = [e for root, budget in CONTEXT for e in entries(root, 'context', None, budget)]

    # The stomach: separate source, hand-placed, labelled approximate.
    s_gltf, s_binary = glb_mesh.read_glb(stomach_raw)
    s_meshes = list(glb_mesh.mesh_nodes(s_gltf, s_binary))
    s_vertices = np.vstack([m['vertices'] for m in s_meshes])
    offsets = np.cumsum([0] + [len(m['vertices']) for m in s_meshes[:-1]])
    s_faces = np.vstack([m['faces'] + o for m, o in zip(s_meshes, offsets)])
    angle = np.radians(STOMACH_PLACEMENT['rotation_y_degrees'])
    rot = np.array([[np.cos(angle), 0, np.sin(angle)], [0, 1, 0], [-np.sin(angle), 0, np.cos(angle)]])
    s_vertices = s_vertices @ rot.T + np.array(STOMACH_PLACEMENT['translation'])
    v, f, cell = glb_mesh.simplify_to_target(s_vertices, s_faces, STOMACH_BUDGET)
    context.append({
        'name': 'stomach', 'group': 'stomach', 'class': 'context', 'body_map_node': None, 'label': 'stomach',
        'ontology_id': STOMACH['ontology_id'], 'source': 'innerscene_stomach', 'placement': 'approximate_by_hand',
        'source_faces': int(len(s_faces)), 'faces': int(len(f)), 'cell_m': round(cell, 6), 'bbox': _bbox(v),
        'bbox_shift_m': None, '_vertices': v, '_faces': f,
    })

    files = {}
    for key, parts, title in (('route', route, 'simulation organs'), ('context', context, 'context organs')):
        payload = [{'name': p['name'], 'vertices': p['_vertices'], 'faces': p['_faces'],
                    'extras': {'class': p['class'], 'body_map_node': p['body_map_node'], 'label': p['label'],
                               'ontology_id': p['ontology_id'], 'placement': p['placement']}} for p in parts]
        raw = glb_mesh.write_glb(payload, asset_extras={'build': BUILD_VERSION, 'content': title,
                                                         'attribution': [SOURCE['attribution']] +
                                                         ([STOMACH['attribution']] if key == 'context' else [])})
        files[key] = raw

    checks = _checks(route, context, skin_box)
    for part in route + context:
        part.pop('_vertices')
        part.pop('_faces')
    names = {'route': 'body-route-male-v1.glb', 'context': 'body-context-male-v1.glb'}
    manifest = {
        'schema_version': SCHEMA_VERSION,
        'build_version': BUILD_VERSION,
        'plan': 'docs/DIGITAL_HUMAN_1_LENALIDOMIDE_ELIMINATION.md (rendering decision; decision 5, context organs)',
        'coordinate_frame': 'HRA Visible Human male reference body; metres; +y up; body left is +x.',
        'sources': {'hra_united_male': SOURCE, 'innerscene_stomach': {**STOMACH, 'placement': STOMACH_PLACEMENT}},
        'outputs': [{'file': f'landscape_ui/static/body-map/models/{names[k]}', 'class': 'simulation' if k == 'route' else 'context',
                     'sha256': sha256_bytes(raw), 'bytes': len(raw),
                     'faces': sum(p['faces'] for p in (route if k == 'route' else context))} for k, raw in files.items()],
        'parts': route + context,
        'excluded': [{'name': name, 'reason': reason} for name, reason in sorted(EXCLUDED.items())],
        'checks': checks,
        'not_this': ('Geometry for drawing only. Organ shapes and positions are reference anatomy, not the simulated '
                     'patient; no part carries a drug amount or concentration.'),
    }
    return manifest, {names[k]: raw for k, raw in files.items()}


def _checks(route, context, skin_box):
    lo, hi = np.array(skin_box[0]), np.array(skin_box[1])
    inside = all(np.all(np.array(p['bbox'][0]) >= lo - 0.01) and np.all(np.array(p['bbox'][1]) <= hi + 0.01)
                 for p in route + context)
    kidneys = {p['group']: p['bbox'] for p in route if p['body_map_node'] == 'kidney'}
    left = np.array([b for p, b in ((p['group'], p['bbox']) for p in route) if p == 'VH_M_left_kidney'])
    right = np.array([b for p, b in ((p['group'], p['bbox']) for p in route) if p == 'VH_M_right_kidney'])
    shifts = [p['bbox_shift_m'] for p in route + context if p['bbox_shift_m'] is not None]
    return {
        'all_parts_inside_skin_bounding_box_1cm': bool(inside),
        'left_kidney_on_body_left_plus_x': bool(left[:, 0, 0].min() > 0) if len(left) else None,
        'right_kidney_on_body_right_minus_x': bool(right[:, 1, 0].max() < 0) if len(right) else None,
        'kidney_groups': sorted(kidneys),
        'max_bbox_shift_m': round(max(shifts), 6),
        'max_bbox_shift_limit_m': MAX_BBOX_SHIFT_M,
        'max_bbox_shift_within_limit': bool(max(shifts) <= MAX_BBOX_SHIFT_M),
        'context_parts_with_body_map_node': sum(1 for p in context if p['body_map_node']),
        'simulation_nodes_drawn': sorted({p['body_map_node'] for p in route}),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--source', required=True)
    parser.add_argument('--stomach', required=True)
    args = parser.parse_args()
    source_raw, stomach_raw = Path(args.source).read_bytes(), Path(args.stomach).read_bytes()
    for label, spec, raw in (('United male set', SOURCE, source_raw), ('Stomach', STOMACH, stomach_raw)):
        if spec['sha256'] and sha256_bytes(raw) != spec['sha256']:
            raise SystemExit(f'{label} does not match its recorded checksum; nothing was built.')
    manifest, files = build(source_raw, stomach_raw)
    manifest['sources']['hra_united_male']['sha256'] = sha256_bytes(source_raw)
    manifest['sources']['innerscene_stomach']['sha256'] = sha256_bytes(stomach_raw)
    MODELS.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        (MODELS / name).write_bytes(raw)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    for output in manifest['outputs']:
        print(f"{output['file']}: {output['bytes'] / 1e6:.1f} MB, {output['faces']:,} triangles")
    print(json.dumps(manifest['checks'], indent=2))


if __name__ == '__main__':
    main()
