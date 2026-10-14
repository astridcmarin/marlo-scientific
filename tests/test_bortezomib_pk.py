"""Simulation 3.0b: bortezomib three-compartment PK engine and its comparison with the label."""
import math
from pathlib import Path
import tempfile
import unittest

from intelligence_store.covariate_estimation import CovariateEstimationError
from intelligence_store.bortezomib_pk import (compare_with_label, concentration_curve, disposition_rates,
                                              load_label_reference, rate_constants, rk4_concentration,
                                              single_dose_summary, standard_regimen, unit_bolus_coefficients)

DATA = Path(__file__).resolve().parents[1] / 'intelligence_store' / 'data'


class Engine(unittest.TestCase):
    def test_exact_solution_matches_independent_integration_across_doses(self):
        events = standard_regimen(1.3, cycles=1)
        times = [0.0, 0.05, 0.5, 2.0, 24.0, 71.99, 72.0, 72.1, 170.0, 240.0, 240.2, 300.0, 504.0]
        exact = concentration_curve(events, times)
        numeric = rk4_concentration(events, times, step_h=0.002)
        for t, a, b in zip(times, exact, numeric):
            self.assertLess(abs(a - b), 1e-6 * max(1.0, a), t)

    def test_roots_and_unit_response(self):
        k = rate_constants()
        lams = disposition_rates(k)
        self.assertTrue(lams[0] > lams[1] > lams[2] > 0)
        self.assertAlmostEqual(math.fsum(c for c, _ in unit_bolus_coefficients(k)), 1 / k['v1_l_m2'], places=12)

    def test_exposure_equals_dose_over_clearance(self):
        summary = single_dose_summary(1.3)
        self.assertAlmostEqual(summary['auc_0_inf_ng_h_ml'], summary['auc_from_clearance_ng_h_ml'], places=6)
        self.assertAlmostEqual(summary['c0_ng_ml'], 1300 / 9.6, places=9)

    def test_regimen(self):
        self.assertEqual([t for t, _ in standard_regimen(cycles=2)], [0, 72, 168, 240, 504, 576, 672, 744])


class LabelComparison(unittest.TestCase):
    def test_repeat_dose_disposition_matches_and_first_dose_clearance_does_not(self):
        rows = {r['quantity']: r for r in compare_with_label()['rows']}
        self.assertEqual(rows['terminal_half_life_h']['placement'], 'inside')
        self.assertEqual(rows['volume_of_distribution_l_m2']['placement'], 'inside')
        self.assertAlmostEqual(rows['clearance_repeat_dose_l_h']['model'], 14.904, places=3)
        self.assertEqual(rows['clearance_first_dose_l_h']['placement'], 'below')
        self.assertGreater(rows['clearance_first_dose_l_h']['fold_difference'], 6)

    def test_changed_label_file_is_refused(self):
        name = 'bortezomib_label_pk_v1.json'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / name
            path.write_bytes((DATA / name).read_bytes() + b' ')
            with self.assertRaises(CovariateEstimationError):
                load_label_reference(path)


if __name__ == '__main__':
    unittest.main()
