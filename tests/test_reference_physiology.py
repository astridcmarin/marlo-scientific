"""Digital human 1.1, steps 1.1a-1.1b: pinned reference physiology, blood-to-plasma ratio, and the kidney extraction."""
import hashlib
import unittest
from unittest import mock

from intelligence_store import body_map, reference_physiology as rp
from intelligence_store.body_map import BodyMapError, explorer_map
from intelligence_store.run_record import record_for_body_map_explorer


class PinnedSources(unittest.TestCase):
    def test_files_are_pinned_and_refuse_changes(self):
        for path, pin in ((rp.ICRP_PATH, rp.ICRP_SHA256), (rp.CHEN_PATH, rp.CHEN_SHA256)):
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), pin)
        with mock.patch.object(rp, 'ICRP_SHA256', '0' * 64), self.assertRaises(rp.ReferencePhysiologyError):
            rp.load_reference_physiology()

    def test_icrp_values_as_printed(self):
        v = rp.load_reference_physiology()['values']
        self.assertEqual(v['cardiac_output_adult_male']['value'], 6.5)
        self.assertEqual(v['kidney_blood_flow_fraction_adult_male']['value'], 19)
        self.assertEqual(v['red_cell_fraction_of_blood_adult_male']['value'], 43)
        self.assertTrue(all('PDF page' in x['location'] for x in v.values()))

    def test_derived_flows_match_the_recorded_derivation(self):
        f = rp.renal_flows()
        derived = rp.load_reference_physiology()['derived_by_platform']
        self.assertAlmostEqual(f['renal_blood_flow_ml_min'], derived['renal_blood_flow_ml_min']['value'])
        self.assertAlmostEqual(f['renal_plasma_flow_ml_min'], derived['renal_plasma_flow_ml_min']['value'])

    def test_blood_to_plasma_is_assumed_with_its_limits(self):
        d = rp.load_blood_plasma()
        self.assertEqual(d['values']['whole_blood_to_plasma_auc_ratio']['value'], 0.931)
        self.assertEqual(d['use_on_platform']['blood_to_plasma_ratio'], 0.931)
        self.assertEqual(d['use_on_platform']['status'], 'assumed')
        self.assertTrue(any('radioactivity' in x for x in d['use_on_platform']['limits']))
        self.assertFalse(d['clinical_prediction_validated'])


class Extraction(unittest.TestCase):
    def test_extraction_is_renal_blood_clearance_over_reference_blood_flow(self):
        view = explorer_map(110)
        renal = next(f for f in view['flows'] if f['kind'] == 'renal_excretion')['value']
        expected = renal / 0.931 / rp.renal_flows()['renal_blood_flow_ml_min']
        self.assertAlmostEqual(view['extraction']['ratio'], expected)
        self.assertAlmostEqual(view['extraction']['ratio'] + view['extraction']['returned_by_renal_veins'], 1)
        self.assertEqual(view['schema_version'], 'body-map-view-v2')

    def test_blood_flow_is_the_same_at_every_kidney_function(self):
        flows = {explorer_map(c)['blood_flow']['renal_blood_flow_ml_min'] for c in (10, 40, 65, 110, 140)}
        self.assertEqual(len(flows), 1)
        ratios = [explorer_map(c)['extraction']['ratio'] for c in (10, 40, 65, 110, 140)]
        self.assertEqual(ratios, sorted(ratios))

    def test_extraction_carries_the_band_status(self):
        self.assertEqual(explorer_map(40)['extraction']['status'], 'check_disagrees')
        self.assertEqual(explorer_map(110)['extraction']['status'], 'calibrated')

    def test_inconsistent_extraction_is_refused(self):
        with mock.patch.object(body_map, 'renal_flows', return_value={'renal_blood_flow_ml_min': 100.0, 'renal_plasma_flow_ml_min': 57.0,
                                                                     'cardiac_output_l_min': 6.5, 'kidney_fraction_pct': 19,
                                                                     'red_cell_fraction_pct': 43}):
            with self.assertRaises(BodyMapError):
                explorer_map(140)

    def test_run_record_lists_the_assumptions_and_sources(self):
        record = record_for_body_map_explorer(explorer_map(40))
        names = [a['name'] for a in record['assumptions']]
        self.assertIn('Renal blood flow', names)
        self.assertIn('Blood-to-plasma ratio', names)
        labels = [c['label'] for c in record['checksums']]
        self.assertIn('Reference physiology (ICRP 89)', labels)
        self.assertIn('Blood-to-plasma extract (Chen 2012)', labels)


if __name__ == '__main__':
    unittest.main()
