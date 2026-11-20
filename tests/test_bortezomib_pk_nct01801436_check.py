import json
import math
import unittest

from intelligence_store import bortezomib_pk_nct01801436_check as check


class NcaEmulationTests(unittest.TestCase):
    def test_monoexponential_moments(self):
        k, c0 = 0.05, 100.0
        times = [0.01 * 2 ** i for i in range(14)]
        conc = [c0 * math.exp(-k * t) for t in times]
        r = check.nca(times, conc, 'linear_up_log_down', 3, dose_ug=1000.0)
        self.assertAlmostEqual(r['c0_ng_ml'], c0, places=9)
        self.assertAlmostEqual(r['lambda_z_per_h'], k, places=12)
        self.assertAlmostEqual(r['auc_inf_ng_h_ml'], c0 / k, delta=1e-6 * c0 / k)
        # Linear AUMC trapezoids over-estimate on wide late intervals; the moment stays within 3 %.
        self.assertAlmostEqual(r['mrt_h'], 1 / k, delta=0.03 / k)
        self.assertAlmostEqual(r['cl_l_h'], 1000.0 / (c0 / k), places=6)
        self.assertAlmostEqual(r['vss_l'], r['cl_l_h'] * r['mrt_h'], places=12)

    def test_rejects_non_finite_profile(self):
        with self.assertRaises(ValueError):
            check.nca([1, 2, 3], [3.0, float('nan'), 1.0], 'linear', 3, 1.0)


class PlanGateTests(unittest.TestCase):
    def test_both_models_may_be_checked_blind(self):
        check.check_blind_allowed()

    def test_interval_fixes_n(self):
        lo, hi = check.interval(100.0, 10.0)
        self.assertAlmostEqual(hi - lo, 2 * 2.2622 * 10.0 / math.sqrt(10))
        with self.assertRaises(ValueError):
            check.interval(100.0, 10.0, n=9)

    def test_excluded_endpoints_refused(self):
        obs = check.synthetic_observed()
        obs['endpoints']['cl_day1'] = {'mean': 26.0, 'sd': 18.5, 'n': 10}
        with self.assertRaises(ValueError):
            check._validate_observed(obs)

    def test_lignet_day1_72h_sample_is_pre_dose(self):
        prof = check.lignet_profiles((48.0, 72.0))
        self.assertLess(prof['day1'][1], prof['day1'][0])


if __name__ == '__main__':
    unittest.main()


def _load_builder():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent / 'scripts' / 'build_nct01801436_observed.py'
    spec = importlib.util.spec_from_file_location('build_nct01801436_observed', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _synthetic_record(builder, n='10'):
    """A record in the ClinicalTrials.gov shape with made-up values; not derived from the real record."""
    def outcome(title, unit, value):
        return {'title': title, 'unitOfMeasure': unit, 'paramType': 'MEAN', 'dispersionType': 'Standard Deviation',
                'groups': [{'id': 'OG000'}], 'denoms': [{'units': 'Participants', 'counts': [{'groupId': 'OG000', 'value': n}]}],
                'classes': [{'categories': [{'measurements': [{'groupId': 'OG000', 'value': value, 'spread': '1.5'}]}]}]}
    outs = [outcome(t, u.upper(), str(i + 1)) for i, (t, u) in enumerate(builder.ENDPOINTS.values())]
    outs += [outcome(t, 'x', '99') for t in builder.NEVER_SELECTED]
    return json.dumps({'resultsSection': {'outcomeMeasuresModule': {'outcomeMeasures': outs}}}).encode()


class ObservedBuilderTests(unittest.TestCase):
    def test_selects_named_endpoints_only(self):
        b = _load_builder()
        built = b.build(_synthetic_record(b), '2026-11-20', expected_sha256=None)
        self.assertEqual(set(built['endpoints']), set(check.OBSERVED_KEYS))
        self.assertEqual(built['endpoints']['auc_last_day11'], {**built['endpoints']['auc_last_day11'], 'mean': 1.0, 'sd': 1.5, 'n': 10})
        check._validate_observed(built)

    def test_refuses_wrong_checksum_and_n(self):
        b = _load_builder()
        with self.assertRaises(ValueError):
            b.extract(_synthetic_record(b))
        with self.assertRaises(ValueError):
            b.extract(_synthetic_record(b, n='9'), expected_sha256=None)


class RecordedResultTests(unittest.TestCase):
    def test_observed_file_is_pinned_and_owner_checked(self):
        obs = check.load_observed()
        self.assertTrue(obs['reviewed_by_owner'])
        check._validate_observed(obs)

    def test_ledger_records_both_blind_uses_and_rerun_is_allowed(self):
        from intelligence_store import dataset_ledger as dl
        ledger = dl.load_ledger()
        self.assertEqual(ledger['datasets'][check.DATASET]['values_first_seen'], '2026-11-20')
        uses = {u['model'] for u in ledger['uses'] if u['dataset'] == check.DATASET and u['role'] == 'checked_blind'}
        self.assertEqual(uses, set(check.MODELS))
        check.check_blind_allowed(ledger)

    def test_recorded_report_matches_a_rerun_of_the_primary_endpoint(self):
        report = json.loads(check.REPORT_PATH.read_text())
        self.assertEqual(report['results'][check.MODELS[0]]['primary_class'], 'model_under_predicts')
        lig = check.model_endpoints(check.lignet_profiles(check.SAMPLING_H), check.SAMPLING_H, check.PRIMARY_READING, check.BODY)
        self.assertAlmostEqual(lig['auc_last_day11'], report['model_values'][check.MODELS[0]]['primary']['auc_last_day11'], places=9)
