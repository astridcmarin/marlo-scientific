"""Acceptance rule v2 (AI review F03): plan pinned, rule logic, and a dry run on synthetic observed ratios only."""
import hashlib
import random
import unittest
from pathlib import Path

from intelligence_store import acceptance_rule_v2 as ar
from intelligence_store import dataset_ledger as dl
from intelligence_store.parameter_draws import draw, spreads

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = {'mild': 1.4, 'moderate': 2.6, 'severe': 4.1}


class Plan(unittest.TestCase):
    def setUp(self):
        self.plan = ar.load_plan()

    def test_plan_pins_the_four_checks_as_committed(self):
        self.assertEqual([c['id'] for c in self.plan['scope']['checks']], list(ar.CHECKS))
        for c in self.plan['scope']['checks']:
            for key in ('plan', 'report'):
                self.assertEqual(hashlib.sha256((ROOT / c[key]['file']).read_bytes()).hexdigest(), c[key]['sha256'], c['id'])
        self.assertFalse(self.plan['clinical_prediction_validated'])

    def test_rule_as_approved(self):
        r = self.plan['rule']
        self.assertEqual(r['indeterminate_margin'], 0.05)
        self.assertEqual((r['outer_parameter_sets'], r['inner_trials_per_set']), (200, 50))
        self.assertEqual(len(r['seeds']), 5)
        self.assertEqual(r['parameter_uncertainty']['hughes_2019']['source']['sha256'],
                         hashlib.sha256((ROOT / r['parameter_uncertainty']['hughes_2019']['source']['file']).read_bytes()).hexdigest())

    def test_not_blind_and_the_ledger_agrees(self):
        dl.validate_plan_datasets(self.plan)
        self.assertTrue(all(d['role'] == 'checked_not_blind' for d in self.plan['datasets']))


class Rule(unittest.TestCase):
    S = {'p05': 1.0, 'p50': 1.5, 'p95': 2.0}

    def test_classes(self):
        self.assertEqual(ar.classify(1.5, self.S, 0.05), 'consistent')
        self.assertEqual(ar.classify(2.2, self.S, 0.05), 'model_under_predicts')
        self.assertEqual(ar.classify(0.9, self.S, 0.05), 'model_over_predicts')
        for near in (2.09, 1.91, 1.04, 0.96, 2.0, 1.0):
            self.assertEqual(ar.classify(near, self.S, 0.05), 'indeterminate', near)

    def test_kim_draws_cover_every_bootstrapped_parameter(self):
        ks = ar.kim_spread()
        self.assertIn('cl_egfr_coefficient', ks)
        self.assertNotIn('absorption_rate_h', ks)
        self.assertEqual(set(ar.hughes_spread()), set(ar.HUGHES_KEYS))
        d = draw(random.Random(1), ks)
        self.assertEqual(ar.kim_extract(d)['parameters']['cl_egfr_coefficient']['value'], d['cl_egfr_coefficient'])

    def test_spreads_refuse_an_interval_that_does_not_bracket(self):
        with self.assertRaises(ValueError):
            spreads({'x': (1.0, [1.2, 2.0])})


class DryRun(unittest.TestCase):
    """End to end on synthetic observed ratios (CLAUDE.md, F18): the rule runs, every row is filled, nothing observed."""
    @classmethod
    def setUpClass(cls):
        override = {c: {m: dict(SYNTHETIC) for m in (ar.HUGHES, ar.KIM)} for c in ar.CHECKS}
        cls.report = ar.run_check(observed_override=override, n_outer=2, inner=3, seeds=[1, 2])

    def test_every_check_scenario_model_and_group_has_a_verdict(self):
        self.assertTrue(self.report['synthetic_observed'])
        for check in ar.CHECKS:
            rows = self.report['results'][check]['rows']
            self.assertTrue(rows, check)
            for r in rows:
                self.assertIn(r['verdict_v2'], ('consistent', 'model_under_predicts', 'model_over_predicts', 'indeterminate'))
                self.assertEqual(r['observed_ratio'], SYNTHETIC[r['group']])
                self.assertIsNotNone(r['verdict_v1'], (check, r['scenario'], r['model'], r['group']))
                self.assertEqual(len(r['class_by_seed']), 2)

    def test_seeded(self):
        override = {c: {m: dict(SYNTHETIC) for m in (ar.HUGHES, ar.KIM)} for c in ar.CHECKS}
        again = ar.run_check(observed_override=override, n_outer=2, inner=3, seeds=[1, 2], checks=('hughes_cc5013',))
        self.assertEqual(again['results']['hughes_cc5013']['rows'], self.report['results']['hughes_cc5013']['rows'])



class Result(unittest.TestCase):
    """The run of 12 November 2026 on the observed ratios, after the plan commit."""
    @classmethod
    def setUpClass(cls):
        import json
        cls.report = json.loads(ar.REPORT_PATH.read_text())

    def test_report_follows_the_plan(self):
        r = self.report
        self.assertEqual(r['plan_sha256'], ar.PLAN_SHA256)
        self.assertFalse(r['synthetic_observed'])
        self.assertEqual((r['outer_parameter_sets'], r['inner_trials_per_set'], r['indeterminate_margin']), (200, 50, 0.05))
        self.assertEqual(set(r['results']), set(ar.CHECKS))
        self.assertFalse(r['clinical_prediction_validated'])

    def test_hughes_check_reproduces(self):
        fresh = ar.run_check(checks=('hughes_cc5013',))
        self.assertEqual(fresh['results']['hughes_cc5013'], self.report['results']['hughes_cc5013'])

    def test_every_changed_verdict_is_listed(self):
        rows = [(c, r) for c, v in self.report['results'].items() for r in v['rows']]
        changed = {(c, r['scenario'], r['model'], r['group']) for c, r in rows if r['verdict_v2'] != r['verdict_v1']}
        listed = {(x['check'], x['scenario'], x['model'], x['group']) for x in self.report['changes_from_v1']}
        self.assertEqual(changed, listed)

    def test_findings_line_and_rule_labels(self):
        from intelligence_store.check_findings import load_findings
        f = load_findings()['findings']
        self.assertTrue(all(x.get('acceptance_rule') for x in f))
        line = next(x for x in f if x['id'] == 'acceptance_rule_v2')
        self.assertEqual(line['report'], 'docs/verification/acceptance_rule_v2_lenalidomide_v1.json')

if __name__ == '__main__':
    unittest.main()
