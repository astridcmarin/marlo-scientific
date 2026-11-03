"""Digital human 1.0, step 1.3c: flow paths derived from the pinned 3D models, and what the viewer may attach to organs."""
import json
from pathlib import Path
import unittest

from intelligence_store import body_map_paths
from intelligence_store.body_map import NODES, build_map
from intelligence_store.body_map_assets import load_manifest

ROOT = Path(__file__).resolve().parents[1]
SIMULATION_NODES = {'gut', 'plasma', 'kidney', 'urine'}


class PathsFile(unittest.TestCase):
    def setUp(self):
        self.paths = body_map_paths.load_paths()

    def test_rebuilds_exactly_from_the_committed_model(self):
        rebuilt = body_map_paths.compute_paths((ROOT / body_map_paths.SOURCE_MODEL).read_bytes())
        self.assertEqual(rebuilt, self.paths)

    def test_source_model_is_the_pinned_route_model(self):
        route = next(o for o in load_manifest()['outputs'] if o['class'] == 'simulation')
        self.assertEqual(self.paths['source_model']['file'], route['file'])
        self.assertEqual(self.paths['source_model']['sha256'], route['sha256'])

    def test_paths_join_simulation_nodes_only(self):
        known = {n['id'] for n in NODES}
        for path in self.paths['paths']:
            self.assertIn(path['from_node'], SIMULATION_NODES & known)
            self.assertIn(path['to_node'], SIMULATION_NODES & known)

    def test_each_kidney_gets_half_of_each_renal_flow(self):
        inflows = [p for p in self.paths['paths'] if p['to_node'] == 'kidney']
        self.assertEqual({p['side'] for p in inflows}, {'left', 'right'})
        for path in inflows:
            self.assertEqual(path['flows'], ['filtration', 'tubular_secretion'])
            self.assertEqual(path['share_per_path'], 0.5)
        self.assertGreater(next(p for p in inflows if p['side'] == 'left')['points'][-1][0], 0)
        self.assertLess(next(p for p in inflows if p['side'] == 'right')['points'][-1][0], 0)

    def test_urine_paths_run_down_the_ureters_to_the_bladder(self):
        bladder = self.paths['anchors']['bladder']
        for path in (p for p in self.paths['paths'] if p['to_node'] == 'urine'):
            heights = [pt[1] for pt in path['points']]
            self.assertEqual(path['points'][-1], bladder)
            self.assertGreater(heights[0], heights[-1] + 0.2)
            self.assertGreater(len(path['points']), 10)

    def test_non_renal_has_no_path(self):
        self.assertFalse(any('non_renal' in p['flows'] for p in self.paths['paths']))

    def test_absorption_is_drawn_direct_without_a_value(self):
        absorption = next(p for p in self.paths['paths'] if p['id'] == 'absorption')
        self.assertEqual(len(absorption['points']), 2)
        self.assertIsNone(next(f for f in build_map(110, 'explorer')['flows'] if f['kind'] == 'absorption')['value'])

    def test_changed_file_is_refused(self):
        original = body_map_paths.PATHS_SHA256
        try:
            body_map_paths.PATHS_SHA256 = '0' * 64
            with self.assertRaises(body_map_paths.BodyMapPathError):
                body_map_paths.load_paths()
        finally:
            body_map_paths.PATHS_SHA256 = original


class EvidenceCards(unittest.TestCase):
    def cards(self, crcl):
        from landscape_ui.body_map_pages import evidence_cards
        return evidence_cards(build_map(crcl, 'explorer'))

    def test_cards_exist_only_for_simulation_nodes(self):
        self.assertEqual(set(self.cards(110)), SIMULATION_NODES)

    def test_kidney_card_carries_the_band_status_and_both_unbound_fractions(self):
        view = build_map(40, 'explorer')
        card = self.cards(40)['kidney']
        self.assertEqual(card['status'], 'check_disagrees')
        self.assertEqual(card['status_text'], view['band']['status_text'])
        self.assertTrue(all('with fu 0.60' in row[1] for row in card['rows'][:2]))

    def test_card_numbers_are_the_view_numbers(self):
        view = build_map(70, 'explorer')
        flows = {f['kind']: f for f in view['flows']}
        rows = dict(self.cards(70)['kidney']['rows'])
        self.assertTrue(rows['Filtration'].startswith(f"{flows['filtration']['value']:.0f} mL/min"))
        self.assertTrue(dict(self.cards(70)['plasma']['rows'])['Total clearance from plasma'].startswith(f"{view['totals']['total_ml_min']:.0f}"))

    def test_outline_follows_the_band_status(self):
        from landscape_ui.body_map_pages import STATUS_OUTLINE
        self.assertEqual(STATUS_OUTLINE[build_map(40, 'explorer')['band']['status']], 'warning')
        self.assertIsNone(STATUS_OUTLINE[build_map(110, 'explorer')['band']['status']])


class ViewerScript(unittest.TestCase):
    def setUp(self):
        self.script = (ROOT / 'landscape_ui/static/body-map/body-map-viewer.js').read_text()

    def test_respects_reduced_motion(self):
        self.assertIn('prefers-reduced-motion: reduce', self.script)
        self.assertIn('playing = !!F && !reducedMotion', self.script)

    def test_context_organs_get_no_evidence_card(self):
        self.assertIn('e.body_map_node && config.cards ? config.cards[e.body_map_node] : null', self.script)


if __name__ == '__main__':
    unittest.main()
