"""Bridoux 2016 check, stage 1: the observed design is pinned and internally consistent before any exposure is read."""
import unittest

from intelligence_store import lenalidomide_bridoux_check as bc


class Stage1Design(unittest.TestCase):
    def setUp(self):
        self.d = bc.load_design()

    def test_pinned_and_refuses_changes(self):
        original = bc.DESIGN_SHA256
        try:
            bc.DESIGN_SHA256 = '0' * 64
            with self.assertRaises(ValueError):
                bc.load_design()
        finally:
            bc.DESIGN_SHA256 = original

    def test_group_counts_add_up(self):
        g = self.d['design']['per_group']
        groups = ('normal', 'mild', 'moderate', 'severe', 'esrd')
        self.assertEqual(sum(g['n_enrolled'][k] for k in groups), g['n_enrolled']['total'])
        for k in groups:
            self.assertEqual(sum(g['male_female'][k]), g['n_enrolled'][k], k)
        self.assertEqual([sum(x) for x in zip(*(g['male_female'][k] for k in groups))], g['male_female']['total'])

    def test_group_means_lie_inside_their_definitions(self):
        crcl = self.d['design']['per_group']['crcl_mean_sd_ml_min']
        self.assertGreater(crcl['normal'][0], 80)
        self.assertTrue(50 <= crcl['mild'][0] <= 80)
        self.assertTrue(30 <= crcl['moderate'][0] < 50)
        self.assertLess(crcl['severe'][0], 30)

    def test_no_exposure_value_and_the_deviation_is_recorded(self):
        self.assertNotIn('auc', {k.lower() for k in self.d['design']['per_group']})
        self.assertIn('Results text', self.d['deviation']['what'])
        self.assertIn('not changed', self.d['deviation']['effect'])
        self.assertEqual(self.d['fallbacks_triggered_by_the_locked_plan']['weight_kg'],
                         'not reported per group or study-wide: uniform 55-95 kg')


if __name__ == '__main__':
    unittest.main()
