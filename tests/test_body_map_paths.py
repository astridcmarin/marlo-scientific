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

    def test_kidney_flows_start_in_the_aorta_and_follow_the_renal_arteries(self):
        import hashlib
        vessels = body_map_paths.load_vessel_lines()
        aorta = vessels['aorta']['points']
        for side in ('left', 'right'):
            line = self.paths['arterial_lines'][side]
            artery = vessels['renal_arteries'][side]['points']
            self.assertEqual(line[1:-1], artery)
            start = line[0]
            nearest = min(aorta, key=lambda q: abs(q[1] - start[1]))
            # on the aorta's centre line (within 2 mm), not in front of it as in paths v1
            self.assertLess(max(abs(a - b) for a, b in zip(start[::2], nearest[::2])), 0.002)
            self.assertLess(abs(start[1] - artery[0][1]), 1e-4)
        self.assertEqual(self.paths['vessel_lines']['sha256'], body_map_paths.VESSELS_SHA256)
        v1 = (ROOT / 'intelligence_store/data/body_map_flow_paths_v1.json').read_bytes()
        self.assertEqual(hashlib.sha256(v1).hexdigest(), body_map_paths.PATHS_V1_SHA256)
        v3 = (ROOT / 'intelligence_store/data/body_map_flow_paths_v3.json').read_bytes()
        self.assertEqual(hashlib.sha256(v3).hexdigest(), body_map_paths.PATHS_V3_SHA256)

    def test_kidney_clearance_is_drawn_inside_the_kidney_not_in_the_artery(self):
        # paths v4 (Track H items 2-3): outer cortex, medulla, papillae, renal pelvis; no drug flow in the renal artery
        for side, sign in (('left', 1), ('right', -1)):
            path = next(p for p in self.paths['paths'] if p['id'] == f'renal_clearance_{side}')
            self.assertEqual(path['route'], ['outer renal cortex', 'renal pyramids (medulla)', 'renal papillae', 'renal pelvis'])
            start, end = path['points'][0], path['points'][-1]
            kidney = self.paths['anchors'][f'kidney_{side}']
            # starts lateral to the kidney's centre (outer cortex) and ends medial to it (pelvis), on its own side
            self.assertGreater(sign * start[0], sign * kidney[0] + 0.01)
            self.assertLess(sign * end[0], sign * kidney[0])
            self.assertGreater(sign * end[0], 0)
            urine = next(p for p in self.paths['paths'] if p['id'] == f'urine_{side}')
            self.assertEqual(urine['points'][0], end)
        aorta = self.paths['anchors']['aorta_renal_level']
        for path in self.paths['paths']:
            if 'filtration' in path['flows']:
                self.assertTrue(all(abs(pt[0] - aorta[0]) > 0.02 for pt in path['points']))

    def test_blood_paths_follow_the_renal_arteries_in_and_the_renal_veins_out(self):
        import hashlib
        blood = {p['id']: p for p in body_map_paths.blood_paths()}
        vessels = body_map_paths.load_vessel_lines()
        self.assertEqual(hashlib.sha256(body_map_paths.VEINS_FILE.read_bytes()).hexdigest(), body_map_paths.VEINS_SHA256)
        for side in ('left', 'right'):
            inflow = self.paths['arterial_lines'][side]
            self.assertEqual(blood[f'blood_in_{side}']['points'], inflow)
            out = blood[f'blood_out_{side}']['points']
            self.assertEqual(out[0], inflow[-1])
            end = out[-1]
            ivc = min(vessels['inferior_vena_cava']['points'], key=lambda q: abs(q[1] - end[1]))
            self.assertLess(max(abs(a - b) for a, b in zip(end[::2], ivc[::2])), 0.003)
        self.assertEqual({p['kind'] for p in blood.values()}, {'arterial', 'venous'})

    def test_vessel_sides_are_assigned_by_position(self):
        vessels = body_map_paths.load_vessel_lines()
        self.assertGreater(vessels['renal_arteries']['left']['points'][-1][0], 0)
        self.assertLess(vessels['renal_arteries']['right']['points'][-1][0], 0)
        self.assertEqual(vessels['renal_arteries']['left']['atlas_node'], 'VH_M_right_renal_artery')
        self.assertIn('opposite to the kidneys', vessels['naming_note'])

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

    def test_urine_paths_run_down_each_ureter_to_its_own_end_at_the_bladder(self):
        bladder = self.paths['anchors']['bladder']
        ends = []
        for path in (p for p in self.paths['paths'] if p['to_node'] == 'urine'):
            heights = [pt[1] for pt in path['points']]
            self.assertNotEqual(path['points'][-1], bladder)
            self.assertGreater(heights[0], heights[-1] + 0.2)
            self.assertGreater(len(path['points']), 10)
            self.assertLess(abs(path['points'][-1][1] - bladder[1]), 0.03)
            ends.append(path['points'][-1])
        # the ureters open separately, one each side of the midline
        self.assertGreater(ends[0][0] * ends[1][0] * -1, 0)

    def test_non_renal_has_no_path(self):
        self.assertFalse(any('non_renal' in p['flows'] for p in self.paths['paths']))

    def test_absorption_goes_by_the_portal_vein_through_the_liver_without_a_value(self):
        import hashlib
        absorption = next(p for p in self.paths['paths'] if p['id'] == 'absorption')
        portal = body_map_paths.load_portal_lines()
        points = absorption['points']
        hpv = portal['hepatic_portal_vein']['points']
        smv = portal['superior_mesenteric_vein']['points']
        # gut, then the superior mesenteric vein from the point nearest the gut, the whole portal vein, the vena cava
        self.assertEqual(points[-len(hpv) - 1:-1], hpv)
        self.assertEqual(points[1], min(smv, key=lambda q: sum((a - b) ** 2 for a, b in zip(q, points[0]))))
        self.assertEqual(points[-1], portal['hepatic_veins_at_vena_cava']['inferior_vena_cava_point'])
        # it reaches the vena cava above the liver hilum, where the hepatic veins join, not at renal-artery level
        self.assertGreater(points[-1][1], hpv[-1][1] + 0.03)
        self.assertIn('liver (passed through, not modelled)', absorption['route'])
        self.assertEqual(self.paths['portal_route_lines']['sha256'], body_map_paths.PORTAL_SHA256)
        v2 = (ROOT / 'intelligence_store/data/body_map_flow_paths_v2.json').read_bytes()
        self.assertEqual(hashlib.sha256(v2).hexdigest(), body_map_paths.PATHS_V2_SHA256)
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
        self.assertEqual(card['status'], 'depends_on_bioavailability')
        self.assertEqual(card['status_text'], view['band']['status_text'] + ' ' + view['band']['myeloma_note']['text'])
        self.assertTrue(all('with fu 0.60' in row[1] for row in card['rows'][:2]))

    def test_myeloma_note_only_in_moderate_and_severe(self):
        for crcl, expected in ((20, True), (40, True), (65, False), (100, False)):
            note = build_map(crcl, 'explorer')['band']['myeloma_note']
            self.assertEqual(note is not None, expected, crcl)
            if note:
                self.assertEqual(note['classifications'], {'bridoux': 'consistent', 'kim': 'consistent'})
                self.assertIn('not a blind test', note['text'])
                self.assertIn('CC-5013-PK-001', note['text'])

    def test_card_numbers_are_the_view_numbers(self):
        view = build_map(70, 'explorer')
        flows = {f['kind']: f for f in view['flows']}
        rows = dict(self.cards(70)['kidney']['rows'])
        self.assertTrue(rows['Filtration'].startswith(f"{flows['filtration']['value']:.0f} mL/min"))
        self.assertTrue(dict(self.cards(70)['plasma']['rows'])['Total clearance from plasma'].startswith(f"{view['totals']['total_ml_min']:.0f}"))

    def test_flow_cards_carry_the_view_numbers_and_status(self):
        from landscape_ui.body_map_pages import flow_cards
        view = build_map(40, 'explorer')
        flows = {f['kind']: f for f in view['flows']}
        cards = flow_cards(view)
        self.assertEqual(set(cards), {'filtration', 'tubular_secretion', 'renal_excretion', 'absorption'})
        self.assertTrue(dict(cards['filtration']['rows'])['Clearance'].startswith(f"{flows['filtration']['value']:.0f} mL/min"))
        self.assertEqual(cards['tubular_secretion']['status'], 'depends_on_bioavailability')
        self.assertIsNone(cards['absorption']['status'])
        self.assertEqual(dict(cards['absorption']['rows'])['Value'], 'none drawn')

    def test_outline_follows_the_band_status(self):
        from landscape_ui.body_map_pages import STATUS_OUTLINE
        self.assertEqual(STATUS_OUTLINE[build_map(40, 'explorer')['band']['status']], 'caution')
        self.assertIsNone(STATUS_OUTLINE[build_map(110, 'explorer')['band']['status']])


class ViewerScript(unittest.TestCase):
    def setUp(self):
        self.script = (ROOT / 'landscape_ui/static/body-map/body-map-viewer.js').read_text()

    def test_respects_reduced_motion(self):
        self.assertIn('prefers-reduced-motion: reduce', self.script)
        self.assertIn('playing = !!F && !reducedMotion', self.script)

    def test_flows_can_be_selected_and_have_a_key_with_a_scale(self):
        self.assertIn('pickTubes.push(tube)', self.script)
        self.assertIn('return { flow: pickTubes[pixel[0] - 1].kind }', self.script)
        self.assertIn('scale_reference_ml_min', self.script)

    def test_blood_flow_layer_is_a_separate_toggle(self):
        self.assertIn("button('Blood flow', false", self.script)
        self.assertIn('bloodOn', self.script)

    def test_context_organs_get_no_evidence_card(self):
        self.assertIn('e.body_map_node && config.cards ? config.cards[e.body_map_node] : null', self.script)


if __name__ == '__main__':
    unittest.main()
