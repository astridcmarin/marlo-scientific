"""Digital human 1.0, step 1.2: the lenalidomide elimination body map as data."""
import copy
import json
import sys
import unittest
from pathlib import Path

from intelligence_store import body_map as bm
from intelligence_store.lenalidomide_renal_pathways import calibrate, load_evidence, pathways

ROOT = Path(__file__).resolve().parent.parent


def flow(view, kind):
    return next(f for f in view['flows'] if f['kind'] == kind)


class MapData(unittest.TestCase):
    def test_flows_add_up(self):
        for crcl in (10, 18, 29.9, 30, 37, 49.9, 50, 74, 80, 80.1, 110, 140):
            v = bm.explorer_map(crcl)
            self.assertEqual(v['status'], 'completed', crcl)
            f, s, r, n = (flow(v, k)['value'] for k in ('filtration', 'tubular_secretion', 'renal_excretion', 'non_renal'))
            self.assertAlmostEqual(f + s, r, places=9)
            self.assertAlmostEqual(r + n, v['totals']['total_ml_min'], places=9)
            shares = [flow(v, k)['share_of_elimination'] for k in ('filtration', 'tubular_secretion', 'non_renal')]
            self.assertAlmostEqual(sum(shares), 1.0, places=12)
            alt = [flow(v, k)['alternative_share'] for k in ('filtration', 'tubular_secretion')] + [shares[2]]
            self.assertAlmostEqual(sum(alt), 1.0, places=12)
            self.assertAlmostEqual(flow(v, 'filtration')['alternative_value'] + flow(v, 'tubular_secretion')['alternative_value'], r, places=9)

    def test_routes_fall_with_kidney_function(self):
        previous = None
        for crcl in range(140, 9, -5):
            v = bm.explorer_map(crcl)
            current = (flow(v, 'renal_excretion')['value'], v['totals']['fraction_excreted_unchanged'], v['totals']['relative_exposure_same_dose'])
            if previous:
                self.assertLess(current[0], previous[0])
                self.assertLess(current[1], previous[1])
                self.assertGreater(current[2], previous[2])
            previous = current
            self.assertEqual(flow(v, 'non_renal')['value'], bm.explorer_map(110)['flows'][4]['value'])

    def test_same_numbers_as_the_pathway_model(self):
        cal = calibrate(load_evidence(), bm.CALIBRATION_CRCL, bm.FU)
        for crcl in (12, 37, 74, 120):
            p = pathways(cal, crcl, bm.READING)
            v = bm.explorer_map(crcl)
            self.assertEqual(flow(v, 'filtration')['value'], p['filtration_ml_min'])
            self.assertEqual(flow(v, 'tubular_secretion')['value'], p['secretion_ml_min'])
            self.assertEqual(v['totals']['fraction_excreted_unchanged'], p['fe'])
        self.assertEqual((bm.FU, bm.READING, bm.CALIBRATION_CRCL), (0.77, 'A_intact_nephron', 110.0))

    def test_band_boundaries_follow_the_study(self):
        expect = {140: 'normal', 80.1: 'normal', 80: 'mild', 50: 'mild', 49.9: 'moderate', 30: 'moderate', 29.9: 'severe', 10: 'severe'}
        for crcl, band in expect.items():
            self.assertEqual(bm.band_for(crcl)['id'], band, crcl)
        self.assertIsNone(bm.band_for(9.9))
        self.assertIsNone(bm.band_for(140.1))

    def test_band_status_comes_from_the_locked_report(self):
        report = bm.load_pathway_report()
        scen = report['decision']['classification_by_scenario']
        statuses = {b['id']: bm.band_status(b, report) for b in bm.BANDS}
        self.assertEqual(statuses['normal'], 'calibrated')
        self.assertEqual(scen['primary']['moderate']['A_intact_nephron'], 'model_under_predicts')
        self.assertEqual(statuses['moderate'], 'check_disagrees')
        severe = {s['severe_without_dialysis']['A_intact_nephron'] for s in scen.values()}
        self.assertEqual(statuses['severe'], 'checked_consistent' if severe == {'consistent'} else 'consistent_primary_only')
        v = bm.explorer_map(37)
        self.assertEqual(v['band']['status'], 'check_disagrees')
        self.assertTrue(all(flow(v, k)['status'] == 'check_disagrees' for k in ('filtration', 'tubular_secretion', 'renal_excretion')))
        self.assertIn('probably lower', v['band']['status_text'])

    def test_not_drawn_outside_the_checked_range(self):
        for crcl in (5, 9.99, 140.01, 200):
            v = bm.explorer_map(crcl)
            self.assertEqual(v['status'], 'outside_range')
            self.assertNotIn('flows', v)
        for bad in (float('nan'), float('inf'), True, '50', None):
            with self.assertRaises(bm.BodyMapError):
                bm.explorer_map(bad)

    def test_nodes_and_provenance(self):
        v = bm.explorer_map(74)
        ids = {n['id']: n for n in v['nodes']}
        self.assertEqual(ids['kidney']['uberon_id'], 'UBERON:0002113')
        self.assertEqual(ids['glomerulus']['parent'], 'kidney')
        for f in v['flows']:
            self.assertIn(f['from'], ids)
            self.assertIn(f['to'], ids)
        self.assertEqual(v['model']['fu_record_sha256'], bm.FU_RECORD_SHA256)
        self.assertFalse(v['clinical_prediction_validated'])
        self.assertEqual(v, bm.explorer_map(74))            # reproducible
        self.assertEqual(len(v['view_sha256']), 64)

    def test_changed_inputs_are_refused(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'x.json'
            path.write_bytes(bm.FU_RECORD_PATH.read_bytes() + b' ')
            original = bm.FU_RECORD_PATH
            try:
                bm.FU_RECORD_PATH = path
                with self.assertRaises(bm.BodyMapError):
                    bm.explorer_map(74)
            finally:
                bm.FU_RECORD_PATH = original


class RecordMode(unittest.TestCase):
    """Record mode reuses the 2.0b estimate; needs the database (runs in CI)."""

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import test_kim_pk_runs as fixtures
        self.fixtures = fixtures
        fixtures.KimPKRunTests.setUp(self)

    def tearDown(self):
        self.fixtures.KimPKRunTests.tearDown(self)

    def test_record_map_matches_the_patient_pathways_page(self):
        from intelligence_store.patient_renal_pathways import patient_renal_pathways
        pv = patient_renal_pathways(self.revision.id)
        v = bm.record_map(self.revision.id)
        self.assertEqual(v['mode'], 'record')
        self.assertEqual(v['record']['revision_id'], self.revision.id)
        if pv['status'] == 'completed' and bm.RANGE[0] <= pv['crcl_ml_min'] <= bm.RANGE[1]:
            self.assertEqual(v['crcl_ml_min'], pv['crcl_ml_min'])
            for kind, key in (('filtration', 'filtration_ml_min'), ('tubular_secretion', 'secretion_ml_min'),
                              ('non_renal', 'non_renal_ml_min'), ('renal_excretion', 'renal_ml_min')):
                self.assertEqual(flow(v, kind)['value'], pv['pathways_ml_min'][key])
            self.assertEqual(v['totals']['relative_exposure_same_dose'], pv['relative_exposure_same_dose'])
        else:
            self.assertNotEqual(v['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
