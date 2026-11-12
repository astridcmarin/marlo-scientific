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

    def test_row_quotes_carry_the_numbers_in_column_order(self):
        # Table 2 rows read: [base estimate [RSE]] final estimate [RSE] bootstrap median [2.5th-97.5th]. The final model's
        # pair is the last "estimate [RSE]" pair, and the row ends with the bootstrap interval (AI review F10).
        import re
        for key, v in self.p['fixed_effects'].items():
            pairs = re.findall(r'(\d+(?:\.\d+)?) \[(\d+(?:\.\d+)?)\]', v['row_quote'])
            self.assertTrue(pairs, key)
            self.assertEqual((float(pairs[-1][0]), float(pairs[-1][1])), (v['estimate'], v['rse_pct']), key)
            interval = re.search(r'\[(\d+(?:\.\d+)?)\u2013(\d+(?:\.\d+)?)\]$', v['row_quote'])
            self.assertIsNotNone(interval, key)
            self.assertEqual([float(interval.group(1)), float(interval.group(2))], v['bootstrap_ci95'], key)
        self.assertIn('Not yet reviewed by the platform owner', self.p['source']['extraction'])
        self.assertEqual(self.p['source']['citation'][:9], 'Hughes JH')

    def test_v1_kept_unchanged(self):
        import hashlib
        v1 = pp.PRECISION_PATH.with_name('hughes_parameter_precision_v1.json')
        self.assertEqual(hashlib.sha256(v1.read_bytes()).hexdigest(), pp.PRECISION_V1_SHA256)
        import json
        old = json.loads(v1.read_text())
        self.assertEqual(old['fixed_effects'], self.p['fixed_effects'])
        self.assertEqual(self.p['supersedes']['sha256'], pp.PRECISION_V1_SHA256)

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



class RegressionRse(unittest.TestCase):
    """Pins the %RSE-based draws as they were before F08 (12 November 2026), so the old method's output stays known."""
    def test_documented_example_is_unchanged(self):
        p = pp.load_parameter_precision()
        draws = pp.sample_typical_parameters(1000, 20261014, p)
        self.assertEqual(draws[0], {'theta_cl': 11.947604389455979, 'theta_crcl': 0.18055341350385873,
                                    'theta_v': 69.5118106031348, 'theta_ktr': 12.08822102158824})
        crcl, ffm, dose = 40.0, 50.0, 25.0
        cl0 = 12.0 * (ffm / 55) ** 0.75 * (crcl / 90) ** 0.224
        auc = [1000 * dose / (cl0 * d['theta_cl'] / 12.0 * (crcl / 90) ** (d['theta_crcl'] - 0.224)) for d in draws]
        s = pp._summary(auc)
        self.assertAlmostEqual(s['p05'], 2370.550327762076, places=6)
        self.assertAlmostEqual(s['p50'], 2680.8492856760545, places=6)
        self.assertAlmostEqual(s['p95'], 3015.150346323717, places=6)


class Bootstrap(unittest.TestCase):
    """F08 (12 November 2026): draws matched to the published bootstrap 95% intervals."""
    def setUp(self):
        self.p = pp.load_parameter_precision()
        self.draws = pp.sample_typical_parameters_bootstrap(20000, 11, self.p)

    def test_seeded(self):
        self.assertEqual(pp.sample_typical_parameters_bootstrap(50, 5, self.p), pp.sample_typical_parameters_bootstrap(50, 5, self.p))

    def test_percentiles_match_the_bootstrap_intervals_and_the_median_the_estimate(self):
        for key, v in self.p['fixed_effects'].items():
            xs = sorted(d[key] for d in self.draws)
            lo, hi = v['bootstrap_ci95']
            self.assertAlmostEqual(xs[int(0.025 * len(xs))] / lo, 1, delta=0.03, msg=key)
            self.assertAlmostEqual(xs[int(0.975 * len(xs))] / hi, 1, delta=0.03, msg=key)
            self.assertAlmostEqual(xs[len(xs) // 2] / v['estimate'], 1, delta=0.01, msg=key)
            self.assertTrue(xs[0] > 0, key)

    def test_ktr_keeps_its_long_upper_tail(self):
        xs = sorted(d['theta_ktr'] for d in self.draws)
        est = self.p['fixed_effects']['theta_ktr']['estimate']
        self.assertGreater(xs[int(0.975 * len(xs))] - est, 5 * (est - xs[int(0.025 * len(xs))]))

    def test_documented_example_is_wider_than_the_rse_method(self):
        crcl, ffm, dose = 40.0, 50.0, 25.0
        cl0 = 12.0 * (ffm / 55) ** 0.75 * (crcl / 90) ** 0.224
        auc = lambda draws: pp._summary([1000 * dose / (cl0 * d['theta_cl'] / 12.0 * (crcl / 90) ** (d['theta_crcl'] - 0.224)) for d in draws])
        new = auc(pp.sample_typical_parameters_bootstrap(1000, 20261014, self.p))
        old = auc(pp.sample_typical_parameters(1000, 20261014, self.p))
        self.assertGreater(new['p95'] - new['p05'], 1.15 * (old['p95'] - old['p05']))
        self.assertAlmostEqual(new['p05'], 2251.611528787214, places=6)
        self.assertAlmostEqual(new['p95'], 3057.839264782706, places=6)

    def test_interval_must_bracket_the_estimate(self):
        import copy
        bad = copy.deepcopy(self.p)
        bad['fixed_effects']['theta_cl']['bootstrap_ci95'] = [12.5, 13.6]
        with self.assertRaises(ValueError):
            pp.sample_typical_parameters_bootstrap(10, 1, bad)

if __name__ == '__main__':
    unittest.main()
