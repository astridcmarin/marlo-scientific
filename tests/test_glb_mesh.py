"""Tests for the GLB mesh tools behind the body map's 3D assets (step 1.3a)."""
import struct
import unittest

import numpy as np

from intelligence_store import glb_mesh


def sphere(radius=1.0, rings=40, segments=80, centre=(0.0, 0.0, 0.0)):
    """A closed UV sphere as (vertices, faces), with duplicate seam and pole vertices left in on purpose."""
    vertices, faces = [], []
    for i in range(rings + 1):
        theta = np.pi * i / rings
        for j in range(segments + 1):
            phi = 2 * np.pi * j / segments
            vertices.append([radius * np.sin(theta) * np.cos(phi), radius * np.cos(theta),
                             radius * np.sin(theta) * np.sin(phi)])
    width = segments + 1
    for i in range(rings):
        for j in range(segments):
            a, b, c, d = i * width + j, i * width + j + 1, (i + 1) * width + j, (i + 1) * width + j + 1
            faces += [[a, c, b], [b, c, d]]
    return np.array(vertices) + np.array(centre), np.array(faces)


class WeldTest(unittest.TestCase):
    def test_weld_merges_seam_and_drops_degenerate_faces(self):
        vertices, faces = sphere()
        welded_v, welded_f = glb_mesh.weld(vertices, faces)
        self.assertLess(len(welded_v), len(vertices))
        self.assertEqual(len(welded_v), 39 * 80 + 2)
        self.assertTrue(np.all(welded_f[:, 0] != welded_f[:, 1]))


class SimplifyTest(unittest.TestCase):
    def setUp(self):
        self.vertices, self.faces = sphere(radius=0.05, centre=(0.1, 0.3, -0.02))

    def test_reaches_target_and_keeps_shape(self):
        v, f, cell = glb_mesh.simplify_to_target(self.vertices, self.faces, 1000)
        self.assertLessEqual(len(f), 1000)
        self.assertGreater(len(f), 500)
        self.assertGreater(cell, 0)
        radius = np.linalg.norm(v - np.array([0.1, 0.3, -0.02]), axis=1)
        self.assertLess(np.max(np.abs(radius - 0.05)), 0.003)

    def test_deterministic(self):
        first = glb_mesh.simplify_to_target(self.vertices, self.faces, 800)
        second = glb_mesh.simplify_to_target(self.vertices, self.faces, 800)
        np.testing.assert_array_equal(first[0], second[0])
        np.testing.assert_array_equal(first[1], second[1])

    def test_small_mesh_only_welded(self):
        v, f, cell = glb_mesh.simplify_to_target(self.vertices, self.faces, 10 ** 6)
        self.assertEqual(cell, 0.0)
        self.assertEqual(len(f), len(glb_mesh.weld(self.vertices, self.faces)[1]))

    def test_positions_stay_in_their_cells(self):
        cell = 0.01
        v, _ = glb_mesh.cluster_simplify(*glb_mesh.weld(self.vertices, self.faces), cell)
        low, high = self.vertices.min(axis=0), self.vertices.max(axis=0)
        self.assertTrue(np.all(v >= low - 1e-12) and np.all(v <= high + cell))

    def test_rejects_bad_cell(self):
        with self.assertRaises(glb_mesh.GlbError):
            glb_mesh.cluster_simplify(self.vertices, self.faces, 0.0)


class RoundTripTest(unittest.TestCase):
    def test_write_then_read(self):
        vertices, faces = glb_mesh.weld(*sphere(rings=10, segments=20))
        raw = glb_mesh.write_glb([{'name': 'ball', 'vertices': vertices, 'faces': faces,
                                   'extras': {'class': 'context', 'ontology_id': 'UBERON:0000000'}}],
                                 asset_extras={'build': 'test'})
        self.assertEqual(struct.unpack_from('<I', raw, 0)[0], glb_mesh.GLB_MAGIC)
        self.assertEqual(len(raw) % 4, 0)
        gltf, binary = glb_mesh.read_glb(raw)
        self.assertEqual(gltf['asset']['extras'], {'build': 'test'})
        parts = list(glb_mesh.mesh_nodes(gltf, binary))
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]['name'], 'ball')
        self.assertEqual(parts[0]['extras']['class'], 'context')
        np.testing.assert_allclose(parts[0]['vertices'], vertices, atol=1e-6)
        np.testing.assert_array_equal(parts[0]['faces'], faces)
        self.assertEqual(raw, glb_mesh.write_glb([{'name': 'ball', 'vertices': vertices, 'faces': faces,
                                                    'extras': {'class': 'context', 'ontology_id': 'UBERON:0000000'}}],
                                                  asset_extras={'build': 'test'}))

    def test_node_transforms_are_applied(self):
        vertices, faces = glb_mesh.weld(*sphere(rings=6, segments=12))
        gltf, binary = glb_mesh.read_glb(glb_mesh.write_glb([{'name': 'a', 'vertices': vertices, 'faces': faces}]))
        gltf['nodes'][0].update({'translation': [1.0, 2.0, 3.0], 'scale': [2.0, 2.0, 2.0]})
        part = next(glb_mesh.mesh_nodes(gltf, binary))
        np.testing.assert_allclose(part['vertices'], vertices * 2 + [1.0, 2.0, 3.0], atol=1e-5)

    def test_parent_transforms_compose(self):
        vertices, faces = glb_mesh.weld(*sphere(rings=6, segments=12))
        gltf, binary = glb_mesh.read_glb(glb_mesh.write_glb([{'name': 'child', 'vertices': vertices, 'faces': faces}]))
        gltf['nodes'].append({'name': 'parent', 'children': [0], 'rotation': [0.0, 0.0, 0.7071068, 0.7071068]})
        gltf['scenes'][0]['nodes'] = [1]
        part = next(glb_mesh.mesh_nodes(gltf, binary))
        self.assertEqual(part['ancestors'], ('parent',))
        rotated = np.c_[-vertices[:, 1], vertices[:, 0], vertices[:, 2]]
        np.testing.assert_allclose(part['vertices'], rotated, atol=1e-5)

    def test_rejects_non_glb(self):
        with self.assertRaises(glb_mesh.GlbError):
            glb_mesh.read_glb(b'not a glb file at all')
        raw = bytearray(glb_mesh.write_glb([{'name': 'a', 'vertices': np.eye(3), 'faces': np.array([[0, 1, 2]])}]))
        raw[8:12] = struct.pack('<I', len(raw) + 4)
        with self.assertRaises(glb_mesh.GlbError):
            glb_mesh.read_glb(bytes(raw))


if __name__ == '__main__':
    unittest.main()
