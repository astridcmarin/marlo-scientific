"""Digital human 1.0, step 1.3b: the record-mode body map page with the 3D viewer."""
import copy
import json
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_kim_pk_runs as fixtures  # noqa: E402

from intelligence_store.body_map import record_map
from intelligence_store.body_map_assets import MANIFEST_SHA256, load_manifest
from intelligence_store.patient_renal_pathways import patient_renal_pathways
from intelligence_store.patient_state_revisions import save_revision
from intelligence_store.run_record import record_for_body_map
from landscape_ui.body_map_pages import CAMERA_PRESETS, CONTEXT_LABEL, flow_widths

ROOT = Path(__file__).resolve().parents[1]


class BodyMapPage(unittest.TestCase):
    setUp = fixtures.KimPKRunTests.setUp
    tearDown = fixtures.KimPKRunTests.tearDown

    def revision_with(self, **kw):
        parent = getattr(self, '_latest', self.revision)
        self._latest = save_revision(self.scenario.id, fixtures.full_state(**kw), parent_revision_id=parent.id, title=str(kw))
        return self._latest

    def url(self, revision_id, suffix=''):
        return f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{revision_id}/body-map{suffix}'

    def config(self, html):
        match = re.search(r'<script id="body-map-config" type="application/json">(.*?)</script>', html, re.S)
        self.assertIsNotNone(match)
        return json.loads(match.group(1))

    def test_page_carries_viewer_numbers_and_fallback(self):
        rev = self.revision_with(serum_creatinine=120)
        response = self.client.get(self.url(rev.id))
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for text in ('body-map-viewer', 'Not a clinical prediction', 'Outside check disagrees', 'Flow diagram',
                     'Tubular secretion', 'with fu 0.60', 'Run record', 'Coloured: carries model results',
                     'Grey: anatomy for orientation', 'Human Reference Atlas', 'placed by hand (approximate)',
                     'body-map-viewer.js', 'Limits of this map'):
            self.assertIn(text, html)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_viewer_config_pins_the_models(self):
        rev = self.revision_with(serum_creatinine=80)
        config = self.config(self.client.get(self.url(rev.id)).get_data(as_text=True))
        manifest = load_manifest()
        self.assertEqual({m['sha256'] for m in config['models']}, {o['sha256'] for o in manifest['outputs']})
        for model in config['models']:
            self.assertTrue(model['url'].startswith('/landscape/static/body-map/models/'))
            self.assertEqual(self.client.get(model['url']).status_code, 200)
        self.assertEqual(config['camera_presets'][0]['id'], 'body')
        self.assertEqual(config['context_label'], CONTEXT_LABEL)
        self.assertEqual(set(config['parts']), {p['name'] for p in manifest['parts']})
        self.assertEqual(set(config['node_labels']), {'gut', 'plasma', 'kidney', 'glomerulus', 'tubule', 'urine', 'non_renal'})

    def test_numbers_match_the_body_map_view(self):
        rev = self.revision_with(serum_creatinine=80)
        view = record_map(rev.id)
        html = self.client.get(self.url(rev.id)).get_data(as_text=True)
        flows = {f['kind']: f for f in view['flows']}
        self.assertIn(f"{flows['filtration']['value']:.0f}<br>", html)
        self.assertIn(f"{view['totals']['total_ml_min']:.0f}</td>", html)
        widths = flow_widths(view)
        self.assertGreater(widths['renal_excretion'], widths['non_renal'])
        self.assertAlmostEqual(widths['renal_excretion'], widths['filtration'] + widths['tubular_secretion'], places=6)

    def test_json_download_is_the_body_map_view(self):
        rev = self.revision_with(serum_creatinine=80)
        payload = self.client.get(self.url(rev.id, '?format=json')).get_json()
        self.assertEqual(payload['schema_version'], 'body-map-view-v1')
        self.assertEqual(payload['mode'], 'record')
        self.assertIs(payload['clinical_prediction_validated'], False)

    def test_run_record_adds_the_3d_assets(self):
        rev = self.revision_with(serum_creatinine=80)
        record = record_for_body_map(record_map(rev.id), patient_renal_pathways(rev.id))
        self.assertEqual(record['kind'], 'body_map')
        labels = {c['label']: c['sha256'] for c in record['checksums']}
        self.assertEqual(labels['3D asset manifest'], MANIFEST_SHA256)
        self.assertIn('3D model (simulation organs)', labels)
        self.assertIn('3D model (context organs)', labels)
        self.assertIs(record['validation']['clinical_prediction_validated'], False)
        self.assertTrue(any('reference anatomy' in item for item in record['limitations']))

    def test_missing_inputs_draw_no_map(self):
        state = copy.deepcopy(fixtures.full_state())
        state['fields']['serum_creatinine'] = {'value': None, 'unit': state['fields']['serum_creatinine']['unit'],
                                               'origin': 'unknown', 'observed_at': None, 'source_ref': None}
        parent = getattr(self, '_latest', self.revision)
        rev = save_revision(self.scenario.id, state, parent_revision_id=parent.id, title='missing')
        html = self.client.get(self.url(rev.id)).get_data(as_text=True)
        self.assertIn('Map not drawn', html)
        self.assertNotIn('body-map-config', html)

    def test_outside_the_checked_range_draws_no_map(self):
        rev = self.revision_with(serum_creatinine=600)
        html = self.client.get(self.url(rev.id)).get_data(as_text=True)
        self.assertIn('Map not drawn', html)
        self.assertNotIn('body-map-config', html)

    def test_bad_requests(self):
        rev = self.revision_with(serum_creatinine=80)
        self.assertEqual(self.client.get(self.url(rev.id, '?format=xml')).status_code, 400)
        self.assertEqual(self.client.get(self.url(rev.id, '?crcl=50')).status_code, 400)
        wrong = f'/landscape/workspace/scenarios/{self.scenario.id + 999}/patient-state/revisions/{rev.id}/body-map'
        self.assertEqual(self.client.get(wrong).status_code, 404)

    def test_detail_page_links_to_the_body_map(self):
        rev = self.revision_with(serum_creatinine=80)
        detail = self.client.get(f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{rev.id}')
        self.assertIn('Lenalidomide body map (3D)', detail.get_data(as_text=True))


class StaticViewer(unittest.TestCase):
    """The viewer script checks checksums before drawing and draws no number of its own."""

    def setUp(self):
        self.script = (ROOT / 'landscape_ui/static/body-map/body-map-viewer.js').read_text()

    def test_checks_checksums_before_drawing(self):
        self.assertIn("crypto.subtle.digest('SHA-256'", self.script)
        self.assertLess(self.script.index("crypto.subtle.digest('SHA-256'"), self.script.index('parseGlb(buffer).forEach(upload)'))
        self.assertIn('does not match its recorded checksum', self.script)

    def test_no_external_resources(self):
        self.assertNotRegex(self.script, r'https?://')

    def test_presets_start_with_a_fixed_whole_body_view(self):
        self.assertEqual(CAMERA_PRESETS[0], {'id': 'body', 'label': 'Whole body', 'yaw': 0.0, 'pitch': 0.0,
                                             'scale': 1.05, 'cx': 0.0, 'cy': 0.0})


if __name__ == '__main__':
    unittest.main()
