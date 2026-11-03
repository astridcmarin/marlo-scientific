"""Tests for the body map's pinned 3D assets (Digital human 1.0, step 1.3a)."""
import hashlib
import json
import unittest
from pathlib import Path

from intelligence_store import body_map, body_map_assets, glb_mesh

ROOT = Path(__file__).resolve().parents[1]


class ManifestTest(unittest.TestCase):
    def setUp(self):
        self.manifest = body_map_assets.load_manifest()

    def test_pinned_and_models_unchanged(self):
        result = body_map_assets.verify_models(self.manifest)
        self.assertEqual(len(result), 2)

    def test_sources_licences_and_checksums_recorded(self):
        hra = self.manifest['sources']['hra_united_male']
        self.assertEqual(hra['licence'], 'CC BY 4.0')
        self.assertEqual(hra['sha256'], 'fae3ac193835e9e24cd13a0d0f11e6788183b290b0691b9b83ec81d907d94581')
        stomach = self.manifest['sources']['innerscene_stomach']
        self.assertIn('CC0', stomach['licence'])
        self.assertEqual(stomach['placement']['note'], 'approximate, by eye')
        for source in self.manifest['sources'].values():
            self.assertTrue(source['attribution'])
            self.assertEqual(len(source['sha256']), 64)

    def test_context_parts_never_carry_a_body_map_node(self):
        context = [p for p in self.manifest['parts'] if p['class'] == 'context']
        self.assertTrue(context)
        self.assertTrue(all(p['body_map_node'] is None for p in context))

    def test_simulation_parts_draw_known_body_map_nodes(self):
        known = {node['id'] for node in body_map.NODES}
        simulation = [p for p in self.manifest['parts'] if p['class'] == 'simulation']
        self.assertEqual({p['body_map_node'] for p in simulation}, {'gut', 'plasma', 'kidney', 'urine'})
        self.assertTrue({p['body_map_node'] for p in simulation} <= known)

    def test_kidney_has_both_sides_and_its_structures(self):
        structures = {(p['group'], p['structure']) for p in self.manifest['parts'] if p['body_map_node'] == 'kidney'}
        for side in ('VH_M_left_kidney', 'VH_M_right_kidney'):
            for structure in ('kidney capsule', 'renal cortex', 'renal pyramids', 'renal papillae', 'hilum of kidney'):
                self.assertIn((side, structure), structures)

    def test_only_the_stomach_is_placed_by_hand(self):
        by_hand = [p['name'] for p in self.manifest['parts'] if p['placement'] != 'reference_body']
        self.assertEqual(by_hand, ['stomach'])

    def test_every_exclusion_has_a_reason(self):
        self.assertTrue(self.manifest['excluded'])
        self.assertTrue(all(e['reason'] for e in self.manifest['excluded']))

    def test_recorded_checks_pass(self):
        checks = self.manifest['checks']
        self.assertTrue(checks['all_parts_inside_skin_bounding_box_1cm'])
        self.assertTrue(checks['left_kidney_on_body_left_plus_x'])
        self.assertTrue(checks['right_kidney_on_body_right_minus_x'])
        self.assertTrue(checks['max_bbox_shift_within_limit'])
        self.assertEqual(checks['context_parts_with_body_map_node'], 0)
        for result in checks['kidneys_match_separate_hra_files'].values():
            self.assertTrue(result['within_tolerance'])

    def test_models_stay_small(self):
        for output in self.manifest['outputs']:
            self.assertLess(output['bytes'], 8_000_000)
            self.assertLess(output['faces'], 250_000)

    def test_viewer_assets(self):
        assets = body_map_assets.viewer_assets(self.manifest)
        self.assertEqual([m['static_path'] for m in assets['models']],
                         ['body-map/models/body-route-male-v1.glb', 'body-map/models/body-context-male-v1.glb'])
        self.assertEqual(len(assets['parts']), len(self.manifest['parts']))
        self.assertTrue(any('CC BY 4.0' in a for a in assets['attribution']))


class ModelContentTest(unittest.TestCase):
    """The GLB files agree with the manifest, part by part."""

    def test_nodes_match_manifest(self):
        manifest = body_map_assets.load_manifest()
        expected = {p['name']: p for p in manifest['parts']}
        seen = set()
        for output in manifest['outputs']:
            gltf, binary = glb_mesh.read_glb((ROOT / output['file']).read_bytes())
            for part in glb_mesh.mesh_nodes(gltf, binary):
                record = expected[part['name']]
                self.assertEqual(part['extras']['class'], output['class'])
                self.assertEqual(part['extras']['class'], record['class'])
                self.assertEqual(part['extras']['body_map_node'], record['body_map_node'])
                self.assertEqual(len(part['faces']), record['faces'])
                seen.add(part['name'])
        self.assertEqual(seen, set(expected))


class TamperTest(unittest.TestCase):
    def test_changed_manifest_is_refused(self):
        original = body_map_assets.MANIFEST_SHA256
        try:
            body_map_assets.MANIFEST_SHA256 = '0' * 64
            with self.assertRaises(body_map_assets.BodyMapAssetError):
                body_map_assets.load_manifest()
        finally:
            body_map_assets.MANIFEST_SHA256 = original


if __name__ == '__main__':
    unittest.main()
