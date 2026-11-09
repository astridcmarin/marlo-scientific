"""Reviewer's checklist M7: the typical curve's own uncertainty from the published precision (Hughes 2019 Table 2)."""
import math
import statistics
import unittest

from intelligence_store import population_pk as pp
from intelligence_store.pk_parameter_reference import load_parameter_extract


class Precision(unittest.TestCase):
    def setUp(self):
        self.p = pp.load_parameter_precision()

    def test_estimates_match_the_implemented_parameters(self):
        params = load_parameter_extract()['parameters']
        fx = self.p['fixed_effects']
        self.assertEqual(fx['theta_cl']['estimate'], params['apparent_clearance']['value'])
        self.assertEqual(fx['theta_v']['estimate'], params['apparent_volume']['value'])
        self.assertEqual(fx['theta_ktr']['estimate'], params['transit_rate']['value'])
        self.assertEqual(fx['theta_crcl']['estimate'], params['crcl_exponent']['value'])

    def test_row_quotes_carry_the_numbers(self):
        for key, v in self.p['fixed_effects'].items():
            for n in (v['estimate'], v['rse_pct'], *v['bootstrap_ci95']):
                self.assertIn(f'{n:g}', v['row_quote'].replace('0.0', '0.0'), (key, n))
        self.assertIn('Not yet reviewed by the platform owner', self.p['source']['extraction'])

    def test_draws_are_seeded_and_match_the_stated_precision(self):
        a = pp.sample_typical_parameters(4000, 7, self.p)
        self.assertEqual(a, pp.sample_typical_parameters(4000, 7, self.p))
        for key, v in self.p['fixed_effects'].items():
            values = [d[key] for d in a]
            self.assertAlmostEqual(statistics.mean(values) / v['estimate'], 1, delta=0.02)
            self.assertAlmostEqual(statistics.stdev(values) / (v['estimate'] * v['rse_pct'] / 100), 1, delta=0.06)
        self.assertTrue(all(d['theta_cl'] > 0 and d['theta_v'] > 0 and d['theta_ktr'] > 0 for d in a))

    def test_ktr_disagreement_is_recorded(self):
        self.assertIn('KTR', self.p['notes'][0])
        self.assertEqual(self.p['fixed_effects']['theta_ktr']['bootstrap_ci95'], [11.9, 36.8])

    def test_changed_file_is_refused(self):
        original = pp.PRECISION_SHA256
        try:
            pp.PRECISION_SHA256 = '0' * 64
            with self.assertRaises(ValueError):
                pp.load_parameter_precision()
        finally:
            pp.PRECISION_SHA256 = original

    def test_auc_uncertainty_follows_cl_only(self):
        # AUC to infinity = dose / CL, so its spread comes from theta_cl and the CrCl exponent alone.
        draws = pp.sample_typical_parameters(2000, 3, self.p)
        crcl = 40.0
        fx = self.p['fixed_effects']
        ratio = [d['theta_cl'] / fx['theta_cl']['estimate'] * (crcl / 90) ** (d['theta_crcl'] - fx['theta_crcl']['estimate'])
                 for d in draws]
        spread = statistics.stdev(math.log(r) for r in ratio)
        expected = math.sqrt(0.05 ** 2 + (math.log(crcl / 90) * 0.224 * 0.316) ** 2)
        self.assertAlmostEqual(spread, expected, delta=0.01)


if __name__ == '__main__':
    unittest.main()
