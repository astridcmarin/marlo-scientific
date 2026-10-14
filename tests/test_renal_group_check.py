"""Patient Lab 2.0g: locked plan, reproducible report and the applicability warning it produced."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from intelligence_store.patient_state import UNITS, SCHEMA_VERSION as STATE_SCHEMA, digest
from intelligence_store.renal_group_check import (PLAN_SHA256, _classify, load_observed, load_plan, run_check)
from intelligence_store.covariate_estimation import (CovariateEstimationError, estimate_hughes_covariates,
                                                     load_applicability_findings)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'docs' / 'verification' / 'hughes_renal_group_check_v1.json'


def state(scr):
    values = dict(age_years=65, biological_sex='MALE', weight=80, height=178, serum_creatinine=scr)
    return {'schema_version': STATE_SCHEMA, 'purpose': 'synthetic_educational',
            'fields': {k: {'value': v, 'unit': UNITS[k], 'origin': 'synthetic_input', 'observed_at': None,
                           'source_ref': None} for k, v in values.items()}}


class LockedPlan(unittest.TestCase):
    def test_plan_is_pinned_and_changed_plan_is_refused(self):
        plan = load_plan()
        self.assertEqual(plan['status'], 'locked_before_computation')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'plan.json'
            path.write_bytes((ROOT / 'intelligence_store/data/hughes_renal_group_check_plan_v1.json').read_bytes() + b' ')
            with self.assertRaises(ValueError):
                load_plan(path)

    def test_observed_values_match_the_evidence_file(self):
        observed = load_observed(load_plan())
        self.assertEqual([observed[g]['n'] for g in ('normal', 'mild', 'moderate', 'severe')], [7, 5, 6, 6])
        self.assertEqual(observed['severe']['auc_infinity_mean'], 8191)

    def test_classification_rule(self):
        band = {'p05': 1.0, 'p50': 2.0, 'p95': 3.0}
        self.assertEqual(_classify(2.0, band), 'consistent')
        self.assertEqual(_classify(3.5, band), 'model_under_predicts')
        self.assertEqual(_classify(0.5, band), 'model_over_predicts')


class CommittedReport(unittest.TestCase):
    def test_committed_report_reproduces_exactly(self):
        committed = json.loads(REPORT.read_text())
        self.assertEqual(committed['plan_sha256'], PLAN_SHA256)
        fresh = run_check()
        self.assertEqual(fresh['report_sha256'], committed['report_sha256'])
        body = {k: v for k, v in committed.items() if k != 'report_sha256'}
        self.assertEqual(digest(body), committed['report_sha256'])

    def test_findings_cite_the_committed_report(self):
        committed = json.loads(REPORT.read_text())
        finding = load_applicability_findings()['findings'][0]
        self.assertEqual(hashlib.sha256(REPORT.read_bytes()).hexdigest(), finding['evidence']['report_file_sha256'])
        self.assertEqual(committed['primary_endpoint_by_group'],
                         {'mild': 'consistent', 'moderate': 'model_under_predicts', 'severe': 'model_under_predicts'})
        for group in ('moderate', 'severe'):
            self.assertEqual(committed['classification_across_scenarios'][group], ['model_under_predicts'])
        self.assertEqual(committed['classification_across_scenarios']['mild'], ['consistent'])
        self.assertFalse(committed['clinical_prediction_validated'])


class ApplicabilityWarning(unittest.TestCase):
    def test_warning_appears_only_below_threshold(self):
        low = estimate_hughes_covariates(state(200), 'ideal_body_weight_devine')
        self.assertLess(low['estimates']['creatinine_clearance']['value'], 50)
        self.assertEqual([f['id'] for f in low['applicability_findings']], ['renal-under-prediction-below-50'])
        self.assertTrue(any('under-predicts lenalidomide exposure' in w for w in low['warnings']))
        normal = estimate_hughes_covariates(state(80), 'ideal_body_weight_devine')
        self.assertGreater(normal['estimates']['creatinine_clearance']['value'], 50)
        self.assertEqual(normal['applicability_findings'], [])
        self.assertFalse(any('under-predicts' in w for w in normal['warnings']))

    def test_changed_findings_file_is_refused(self):
        original = ROOT / 'intelligence_store' / 'data' / 'hughes_applicability_findings_v1.json'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'findings.json'
            path.write_bytes(original.read_bytes() + b' ')
            with self.assertRaises(CovariateEstimationError):
                load_applicability_findings(path)


if __name__ == '__main__':
    unittest.main()
