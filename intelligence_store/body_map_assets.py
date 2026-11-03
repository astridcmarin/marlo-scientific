"""Digital human 1.0, step 1.3a: the body map's 3D assets, pinned.

The manifest (body-map-assets-v1) records where every 3D part came from (HRA United male set, CC BY 4.0; one hand-
placed stomach, CC0), how it was simplified, which body-map-view-v1 node it draws, and the checksum of each GLB the page
serves. Built by scripts/build_body_map_assets.py; never edited by hand.

The rule from the plan's decision 5 is enforced here as well as in the build: only simulation parts name a body-map node;
context parts name none, so the viewer cannot attach a model result to them.
"""
import hashlib
import json
from pathlib import Path

DATA = Path(__file__).parent / 'data'
ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = DATA / 'body_map_assets_v1.json'
MANIFEST_SHA256 = '49d382245ed67b4fdaf93d01d610b10b2fa57c64ad6a9d7f18ad5ed34771eca1'
SCHEMA_VERSION = 'body-map-assets-v1'
CLASSES = ('simulation', 'context')


class BodyMapAssetError(ValueError):
    pass


def load_manifest():
    raw = MANIFEST_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise BodyMapAssetError('The body map asset manifest is missing or changed; the 3D view is not available.')
    manifest = json.loads(raw)
    if manifest.get('schema_version') != SCHEMA_VERSION:
        raise BodyMapAssetError('Unexpected body map asset manifest schema.')
    for part in manifest['parts']:
        if part['class'] not in CLASSES:
            raise BodyMapAssetError(f"Part {part['name']!r} has an unknown class.")
        if part['class'] == 'context' and part['body_map_node'] is not None:
            raise BodyMapAssetError(f"Context part {part['name']!r} names a body-map node.")
        if part['class'] == 'simulation' and not part['body_map_node']:
            raise BodyMapAssetError(f"Simulation part {part['name']!r} names no body-map node.")
    return manifest


def verify_models(manifest=None):
    """Check every served GLB against its pinned checksum. Returns {relative path: True}; raises on any mismatch."""
    manifest = manifest or load_manifest()
    result = {}
    for output in manifest['outputs']:
        path = ROOT / output['file']
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != output['sha256']:
            raise BodyMapAssetError(f"3D model {output['file']} is missing or changed.")
        result[output['file']] = True
    return result


def viewer_assets(manifest=None):
    """What the 3D viewer needs: model paths with checksums, attribution, and each part's class and body-map node.

    `static_path` is relative to the landscape blueprint's static folder (served at /landscape/static/<static_path>).
    """
    manifest = manifest or load_manifest()
    static_prefix = 'landscape_ui/static/'
    return {
        'schema_version': manifest['schema_version'],
        'coordinate_frame': manifest['coordinate_frame'],
        'models': [{'static_path': o['file'][len(static_prefix):], 'class': o['class'], 'sha256': o['sha256'],
                    'bytes': o['bytes']} for o in manifest['outputs']],
        'attribution': [s['attribution'] for s in manifest['sources'].values()],
        'parts': [{k: p[k] for k in ('name', 'group', 'structure', 'class', 'body_map_node', 'placement')}
                  for p in manifest['parts']],
        'not_this': manifest['not_this'],
    }
