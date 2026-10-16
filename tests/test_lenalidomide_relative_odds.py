"""Simulation 4.0a: relative odds of grade 3/4 cytopenia from simulated lenalidomide exposure."""
import hashlib
import math
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_kim_pk_runs as fixtures  # noqa: E402

from intelligence_store import lenalidomide_relative_odds as ro
from intelligence_store.covariate_estimation import CovariateEstimationError
from intelligence_store.estimated_pk import compare_published_models


class Evidence(unittest.TestCase):
    def test_pinned_and_refuses_changes(self):
        self.assertEqual(hashlib.sha256(ro.EVIDENCE_PATH.read_bytes()).hexdigest(), ro.EVIDENCE_SHA256)
        with tempfile.TemporaryDirectory() as tmp:
            changed = Path(tmp) / ro.EVIDENCE_PATH.name
            changed.write_bytes(ro.EVIDENCE_PATH.read_bytes() + b' ')
            with self.assertRaises(CovariateEstimationError):
                ro.load_evidence(changed)

    def test_numbers_match_the_quoted_source_sentences(self):
        for name, e in ro.load_evidence()['odds_ratios_multiple_myeloma'].items():
            quoted = re.search(r'= ([\d.]+) \[95% CI: ([\d.]+), ([\d.]+)\]', e['quote']).groups()
            self.assertEqual([float(x) for x in quoted], [e['odds_ratio_per_unit_ln_auc'], *e['ci95']], name)
            self.assertEqual(e['statistically_significant'], e['ci95'][0] > 1.0, name)

    def test_superseded_v1_kept_and_reconciliation_recorded(self):
        self.assertEqual(hashlib.sha256(ro.EVIDENCE_V1_PATH.read_bytes()).hexdigest(), ro.EVIDENCE_V1_SHA256)
        e = ro.load_evidence()
        self.assertEqual(e['supersedes']['evidence_version'], 'lenalidomide-exposure-safety-tga-v1.0')
        pooled = e['second_source']['odds_ratios_all_diseases']['grade_3_4_thrombocytopenia']
        self.assertEqual((pooled['odds_ratio'], pooled['ci95']), (3.337, [1.183, 9.415]))
        self.assertIn('first cycle', e['time_window']['statement'])

    def test_flags_and_missing_items_are_explicit(self):
        e = ro.load_evidence()
        self.assertIs(e['clinical_prediction_validated'], False)
        self.assertIn('intercept', e['not_reported'])


class Formula(unittest.TestCase):
    def test_reference_exposure_gives_one(self):
        r = ro.relative_odds(1.0, 2.972, [1.027, 8.598])
        self.assertAlmostEqual(r['relative_odds'], 1.0)
        self.assertEqual(r['ci95'], [1.0, 1.0])

    def test_matches_the_odds_ratio_definition(self):
        # One unit of ln AUC is an exposure ratio of e: the relative odds must equal the odds ratio itself.
        r = ro.relative_odds(math.e, 2.972, [1.027, 8.598])
        self.assertAlmostEqual(r['relative_odds'], 2.972, places=12)
        self.assertAlmostEqual(r['ci95'][0], 1.027, places=12)
        self.assertAlmostEqual(r['ci95'][1], 8.598, places=12)

    def test_units_cancel(self):
        a = ro.relative_odds(2181 * 2 / 2181, 2.972, [1.027, 8.598])
        b = ro.relative_odds((2181 * 2 / 1000) / (2181 / 1000), 2.972, [1.027, 8.598])  # ug.h/mL instead of ng.h/mL
        self.assertAlmostEqual(a['relative_odds'], b['relative_odds'], places=12)

    def test_below_reference_the_interval_stays_ordered(self):
        r = ro.relative_odds(0.5, 2.972, [1.027, 8.598])
        self.assertLess(r['ci95'][0], r['relative_odds'])
        self.assertLess(r['relative_odds'], r['ci95'][1])
        self.assertLess(r['ci95'][1], 1.0)

    def test_between_patient_range_is_lognormal_and_centred(self):
        r = ro.between_patient_range(2.0, 2.972, 0.544)
        centre = 2.0 ** math.log(2.972)
        self.assertAlmostEqual(math.sqrt(r['p05'] * r['p95']), centre, places=12)  # geometric centre
        self.assertAlmostEqual(math.log(r['p95'] / centre), ro.Z90 * math.log(2.972) * 0.544, places=12)
        zero = ro.between_patient_range(2.0, 2.972, 0.0)
        self.assertAlmostEqual(zero['p05'], zero['p95'])
        with self.assertRaises(ValueError):
            ro.between_patient_range(2.0, 2.972, -0.1)

    def test_bad_ratio_rejected(self):
        for bad in (0, -1, float('nan'), float('inf'), '2'):
            with self.assertRaises(ValueError):
                ro.relative_odds(bad, 2.972, [1.027, 8.598])


class InComparison(unittest.TestCase):
    setUp = fixtures.KimPKRunTests.setUp
    tearDown = fixtures.KimPKRunTests.tearDown

    def test_each_model_row_carries_relative_odds_from_its_own_ratio(self):
        report = compare_published_models(self.revision.id, 'ideal_body_weight_devine', 'linear_multiplicative',
                                          fixtures.request_mg(5.0), 'MM')
        rows = [r for r in report['rows'] if 'reference_exposure' in r]
        self.assertTrue(rows)
        for row in rows:
            ratio = row['reference_exposure']['ratio_to_reference']
            t = row['relative_odds']['endpoints']['grade_3_4_thrombocytopenia']
            self.assertAlmostEqual(t['relative_odds'], ratio ** math.log(2.972), places=12)
            self.assertIs(row['relative_odds']['clinical_prediction_validated'], False)
            self.assertFalse(row['relative_odds']['endpoints']['grade_3_4_neutropenia']['statistically_significant'])
            bp = t['between_patient_90']
            expected_sd = math.sqrt(0.296) if row['model'] == 'lenalidomide_hughes_2019' else 0.189
            self.assertAlmostEqual(bp['omega_cl_sd'], expected_sd, places=12)
            self.assertLess(bp['p05'], t['relative_odds'])
            self.assertLess(t['relative_odds'], bp['p95'])

    def test_page_shows_relative_not_absolute(self):
        page = f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{self.revision.id}/estimated-pk'
        token = re.search(r'name="form_token" value="([^"]+)"', self.client.get(page).get_data(as_text=True)).group(1)
        html = self.client.post(page, data={'form_token': token, 'action': 'models', 'weight_basis': 'ideal_body_weight_devine',
                                            'cl_form': 'linear_multiplicative', 'disease': 'MM', 'horizon': '24',
                                            'events': '0, 5', 'source_ref': 'Invented request'}).get_data(as_text=True)
        for text in ('Relative odds of severe low blood counts', 'Relative, not absolute', 'They are not probabilities',
                     'not statistically significant in the source', 'CC-5013-MCL-001-PK', 'middle 90% of patients',
                     'Two different uncertainties', 'not to the first treatment cycle', 'myeloma-only'):
            self.assertIn(text, html)


if __name__ == '__main__':
    unittest.main()
