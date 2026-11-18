"""Acceptance rule v2 extended to Gupta 2017 and Luo 2021 (plan acceptance_rule_v2_plan_v2.json, decision 0004):
plan pin, the keys the executable reads, the %RSE conversions, correlation, and a synthetic dry run of the plan's own
executable through the plan object. No observed value is classified here."""
import copy
import math
import random
import unittest

from intelligence_store import acceptance_rule_v2_gupta_luo as ar
from intelligence_store import dataset_ledger as dl
from intelligence_store import parameter_uncertainty as pu


class Plan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = ar.load_plan()
        cls.adapters = ar._adapters(cls.plan)

    def test_pinned_and_declares_only_not_blind_uses(self):
        self.assertEqual(self.plan['plan_version'], 'acceptance-rule-v2-plan-v2.0')
        self.assertIs(dl.validate_plan_datasets(self.plan), self.plan)
        self.assertTrue(all(d['role'] == 'checked_not_blind' for d in self.plan['datasets']))

    def test_the_plan_carries_every_key_the_executable_reads(self):
        rule = self.plan['rule']
        for check in ar.CHECKS:
            self.assertIn(check, rule['outer_parameter_sets'])
            self.assertIn(check, rule['inner_trials_per_set'])
            spec = ar._check_spec(self.plan, check)
            self.assertEqual(rule['outer_parameter_sets'][check] * rule['inner_trials_per_set'][check], spec['own_virtual_trials'])
        self.assertEqual(len(rule['seeds']), 5)
        self.assertEqual(rule['indeterminate_margin'], 0.05)
        self.assertEqual(next(iter(self.plan['uncertainty_scenarios'])), 'independent')
        for name, u in self.plan['uncertainty_scenarios'].items():
            for key in ('correlation', 'shape', 'rse_add_percentage_points', 'run_on'):
                self.assertIn(key, u, f'{name}: {key}')
            self.assertIn(u['shape'], pu.SHAPES)
            self.assertIn(u['run_on'], ('every simulation scenario of the check', 'primary simulation scenario'))
            self.assertEqual(set(u['rse_add_percentage_points']), set(ar.MODEL_KEY.values()))

    def test_own_trial_counts_match_the_checks(self):
        from intelligence_store import ixazomib_pk_gupta_check as g, daratumumab_pk_luo_check_v2 as l2
        self.assertEqual(ar._check_spec(self.plan, 'gupta_ixazomib')['own_virtual_trials'], g.load_plan()['simulation']['virtual_trials'])
        self.assertEqual(ar._check_spec(self.plan, 'luo_daratumumab')['own_virtual_trials'], l2.load_plan()['simulation']['virtual_trials'])

    def test_every_fixed_effect_is_drawn_or_named_as_not_drawn(self):
        for check in ar.CHECKS:
            key = ar.MODEL_KEY[check]
            spec = self.plan['parameter_uncertainty'][key]
            drawn = {d['name'] for d in spec['draw']}
            fx = set(self.adapters[check]['extract']['parameters']['fixed_effects'])
            self.assertEqual(drawn | set(spec['not_drawn']), fx, check)
            self.assertFalse(drawn & set(spec['not_drawn']), check)

    def test_li_2017_is_out_of_scope_and_says_why(self):
        self.assertIn('compared_model_to_model', self.plan['scope']['not_in_scope']['li_2017_pomalidomide'])
        self.assertNotIn('li', ' '.join(c['id'] for c in self.plan['scope']['checks']))

    def test_endpoints_are_the_checks_own(self):
        import json
        from intelligence_store import daratumumab_pk_luo_check as l1
        g = json.loads((ar.ROOT / 'docs/verification/ixazomib_pk_gupta_check_v1.json').read_text())
        a = self.adapters['gupta_ixazomib']
        self.assertEqual(a['endpoints'], list(g['classification_by_endpoint']))
        self.assertEqual(len(a['endpoints']), 20)
        for e in a['endpoints']:
            self.assertEqual(a['old']['primary'][e], g['classification_by_endpoint'][e]['primary'], e)
        luo = json.loads((ar.ROOT / 'docs/verification/daratumumab_pk_luo_check_v2.json').read_text())
        b = self.adapters['luo_daratumumab']
        self.assertEqual(b['endpoints'], [e[0] for e in l1.ENDPOINTS])
        for e in b['endpoints']:
            self.assertEqual(b['old']['primary'][e], luo['classification_by_endpoint'][e]['primary'], e)


class Conversions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = ar.load_plan()
        cls.adapters = ar._adapters(cls.plan)

    def _m(self, check, scenario='independent'):
        return {m['name']: m for m in ar.marginals(self.plan, check, self.adapters[check]['extract'], scenario)}

    def test_gupta_rse_belongs_to_the_log_estimate(self):
        m = self._m('gupta_ixazomib')
        self.assertEqual(m['cl_l_h']['distribution'], 'log_normal')
        self.assertAlmostEqual(m['cl_l_h']['sd'], 0.07 * 0.62)
        self.assertAlmostEqual(m['cl_l_h']['centre'], 1.86)
        self.assertAlmostEqual(m['v3_l']['sd'], 0.01 * 5.73)
        self.assertAlmostEqual(m['bsa_exponent_on_v4']['sd'], 0.18 * 2.06)
        self.assertEqual(m['bsa_exponent_on_v4']['distribution'], 'normal')
        self.assertNotIn('tlag_h', m)

    def test_luo_rse_is_a_coefficient_of_variation(self):
        m = self._m('luo_daratumumab')
        self.assertAlmostEqual(m['cl_l_h']['sd'], math.sqrt(math.log(1 + 0.084 ** 2)))
        self.assertAlmostEqual(m['sex_shift_on_v1']['sd'], 0.454 * 0.105)
        self.assertEqual(m['alb_exponent_on_cl']['distribution'], 'normal')
        self.assertNotIn('ka_per_h', m)
        self.assertNotIn('f_sc', m)

    def test_rounding_scenario_adds_half_the_last_printed_digit(self):
        up = self._m('gupta_ixazomib', 'rse_rounding_upper')
        self.assertAlmostEqual(up['v3_l']['sd'], 0.015 * 5.73)
        lup = self._m('luo_daratumumab', 'rse_rounding_upper')
        self.assertAlmostEqual(lup['v1_l']['sd'], math.sqrt(math.log(1 + 0.0415 ** 2)))

    def test_a_zero_rse_cannot_be_drawn(self):
        with self.assertRaises(ValueError):
            pu.marginal('tlag_h', {'value': 0.2, 'rse_percent': 0, 'log_estimate': -1.52}, 'log_normal', 'rse_of_log_estimate')

    def test_luo_shift_factors_stay_positive_six_sd_out(self):
        m = self._m('luo_daratumumab')
        for name in ('igg_shift_on_cl', 'sex_shift_on_v1'):
            self.assertGreater(1 + m[name]['centre'] - 6 * m[name]['sd'], 0, name)

    def test_every_scenario_gives_a_positive_definite_correlation(self):
        for check in ar.CHECKS:
            for u in self.plan['uncertainty_scenarios']:
                ms = ar.marginals(self.plan, check, self.adapters[check]['extract'], u)
                ar.cholesky_for(self.plan, check, ms, u)

    def test_a_correlation_that_is_not_positive_definite_is_refused(self):
        with self.assertRaises(ValueError):
            pu.correlation_matrix(['a', 'b', 'c'], pairs=[('a', 'b', 0.9), ('b', 'c', 0.9), ('a', 'c', -0.9)])

    def test_correlated_draws_reproduce_the_planned_correlation(self):
        ms = ar.marginals(self.plan, 'luo_daratumumab', self.adapters['luo_daratumumab']['extract'], 'identifiability_pairs')
        low = ar.cholesky_for(self.plan, 'luo_daratumumab', ms, 'identifiability_pairs')
        rng = random.Random(7)
        logs = [pu.draw(rng, ms, low)[0] for _ in range(6000)]

        def corr(a, b):
            x = [math.log(d[a]) for d in logs]
            y = [math.log(d[b]) for d in logs]
            mx, my = sum(x) / len(x), sum(y) / len(y)
            sxy = sum((p - mx) * (q - my) for p, q in zip(x, y))
            return sxy / math.sqrt(sum((p - mx) ** 2 for p in x) * sum((q - my) ** 2 for q in y))
        self.assertAlmostEqual(corr('vmax_mg_h', 'km_ug_ml'), 0.8, delta=0.03)
        self.assertAlmostEqual(corr('cl_l_h', 'vmax_mg_h'), -0.5, delta=0.04)
        self.assertAlmostEqual(corr('cl_l_h', 'km_ug_ml'), 0.0, delta=0.04)

    def test_drawn_values_do_not_touch_the_pinned_extract(self):
        ex = self.adapters['gupta_ixazomib']['extract']
        before = copy.deepcopy(ex)
        x = ar.with_values(ex, {'cl_l_h': 99.0})
        self.assertEqual(x['parameters']['fixed_effects']['cl_l_h']['value'], 99.0)
        self.assertEqual(ex, before)


class Reading(unittest.TestCase):
    def test_a_verdict_that_moves_between_uncertainty_scenarios_is_undecided(self):
        r = ar.reading({'independent': 'consistent', 'uniform_positive_0_5': 'model_under_predicts'},
                       {'primary': 'consistent'}, 'consistent')
        self.assertEqual(r['reading'], ar.UNDECIDED)
        self.assertEqual(r['verdict_v2'], 'consistent')
        self.assertTrue(r['changed'])

    def test_a_stable_verdict_is_read_as_it_is(self):
        r = ar.reading({'independent': 'consistent', 'normal_on_natural_scale': 'consistent'},
                       {'primary': 'consistent', 'omega_equals_cv': 'model_under_predicts'}, 'consistent')
        self.assertEqual(r['reading'], 'consistent')
        self.assertFalse(r['robust_across_simulation_scenarios'])
        self.assertFalse(r['changed'])


class DryRun(unittest.TestCase):
    """The plan's own executable, through the plan object, on synthetic observed values only."""

    @classmethod
    def setUpClass(cls):
        cls.plan = ar.load_plan()
        ad = ar._adapters(cls.plan)
        cls.synthetic = {c: {e: 1.0 for e in ad[c]['endpoints']} for c in ar.CHECKS}
        cls.report = ar.run_check(cls.plan, observed_override=cls.synthetic, n_outer=2, inner=1, seeds=[1, 2],
                                  simulation_scenarios=['primary', 'omega_equals_cv'])

    def test_every_endpoint_is_read_under_every_uncertainty_scenario(self):
        self.assertTrue(self.report['synthetic_observed'])
        for check, r in self.report['results'].items():
            for e, v in r['endpoints'].items():
                self.assertEqual(set(v['by_uncertainty_scenario']), set(self.plan['uncertainty_scenarios']), (check, e))
                self.assertEqual(set(v['by_simulation_scenario']), {'primary', 'omega_equals_cv'}, (check, e))
                self.assertIn(v['reading'], ('consistent', 'model_under_predicts', 'model_over_predicts', 'indeterminate', ar.UNDECIDED))

    def test_no_observed_value_reaches_the_dry_run(self):
        for check, r in self.report['results'].items():
            self.assertTrue(all(row['observed'] == 1.0 for row in r['rows']), check)

    def test_a_partial_synthetic_run_is_refused(self):
        partial = copy.deepcopy(self.synthetic)
        partial['gupta_ixazomib'].pop(next(iter(partial['gupta_ixazomib'])))
        with self.assertRaises(ValueError):
            ar.run_check(self.plan, observed_override=partial, n_outer=1, inner=1, seeds=[1],
                         checks=('gupta_ixazomib',), simulation_scenarios=['primary'])

    def test_the_run_is_reproducible(self):
        again = ar.run_check(self.plan, observed_override=self.synthetic, n_outer=2, inner=1, seeds=[1, 2],
                             simulation_scenarios=['primary', 'omega_equals_cv'])
        self.assertEqual(again['report_sha256'], self.report['report_sha256'])


    def test_the_number_of_workers_does_not_change_the_report(self):
        two = ar.run_check(self.plan, observed_override=self.synthetic, n_outer=2, inner=1, seeds=[1, 2],
                           simulation_scenarios=['primary', 'omega_equals_cv'], workers=2)
        self.assertEqual(two['report_sha256'], self.report['report_sha256'])

if __name__ == '__main__':
    unittest.main()
