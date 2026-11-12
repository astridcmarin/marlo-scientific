"""ICRP 89 reference physiology v2: the reference woman and man side by side (Track H, step 1)."""
import json
import unittest

from intelligence_store import reference_physiology as rp


class V2(unittest.TestCase):
    def setUp(self):
        self.d = rp.load_reference_physiology_v2()
        self.v = self.d['values']

    def test_v1_kept_and_its_values_unchanged(self):
        v1 = rp.load_reference_physiology()['values']
        self.assertEqual(self.v['cardiac_output']['men'], v1['cardiac_output_adult_male']['value'])
        self.assertEqual(self.v['kidneys_blood_flow']['men'], v1['kidney_blood_flow_fraction_adult_male']['value'])
        self.assertEqual(self.v['red_cell_fraction_of_blood']['men'], v1['red_cell_fraction_of_blood_adult_male']['value'])
        self.assertEqual(self.d['supersedes']['file'], 'intelligence_store/data/reference_physiology_icrp89_v1.json')

    def test_every_value_has_both_columns_location_and_quote(self):
        for key, v in self.v.items():
            self.assertIn('women', v, key)
            self.assertIn('men', v, key)
            self.assertTrue(v['location'] and v['quote'], key)
        self.assertIsNone(self.v['glomerular_filtration_rate']['women'])

    def test_blood_flow_columns_sum_to_100_with_the_liver_by_its_arterial_share(self):
        rows = [k for k in self.v if k.endswith('_blood_flow') and k != 'liver_total_blood_flow']
        for sex in ('women', 'men'):
            self.assertAlmostEqual(sum(self.v[k][sex] for k in rows), 100.0, places=6, msg=sex)
        self.assertEqual(self.d['derived_by_platform']['regional_flow_column_sums']['women'], 100.0)

    def test_the_womens_liver_total_inconsistency_is_recorded(self):
        portal = self.d['derived_by_platform']['liver_portal_sum_pct']
        self.assertEqual((portal['women'], portal['printed_total']['women']), (27.5, 27.0))
        self.assertEqual((portal['men'], portal['printed_total']['men']), (25.5, 25.5))
        self.assertIn('27.0', self.v['liver_total_blood_flow']['consistency_note'])

    def test_no_sex_multiplier_and_not_a_patient_value(self):
        self.assertIn('no sex multiplier', self.d['applies_to'])
        self.assertFalse(self.d['clinical_prediction_validated'])
        self.assertFalse(self.d['ready_for_patient_simulation'])


if __name__ == '__main__':
    unittest.main()
