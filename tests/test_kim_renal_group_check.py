"""Patient Lab 2.1c: locked plan, covariate construction and reproducible report for the Kim renal-group check."""
import hashlib
import json
from pathlib import Path
import random
import tempfile
import unittest

from intelligence_store.patient_state import UNITS, SCHEMA_VERSION as STATE_SCHEMA, digest
from intelligence_store.covariate_estimation import CovariateEstimationError, cockcroft_gault, egfr_ckd_epi_2021
from intelligence_store.kim_model import (estimate_kim_covariates, load_applicability_findings,
                                          load_dose_proportionality_evidence)
from intelligence_store.kim_renal_group_check import (PLAN_SHA256, backsolve_serum_creatinine, draw_subject, load_plan,
                                                      run_check, scenario_settings)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'docs' / 'verification' / 'kim_renal_group_check_v1.json'


class LockedPlan(unittest.TestCase):
    def test_plan_is_pinned_and_changed_plan_is_refused(self):
        self.assertEqual(load_plan()['status'], 'locked_before_computation')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'plan.json'
            path.write_bytes((ROOT / 'intelligence_store/data/kim_renal_group_check_plan_v1.json').read_bytes() + b' ')
            with self.assertRaises(ValueError):
                load_plan(path)

    def test_sensitivity_scenarios_change_only_their_listed_keys(self):
        plan = load_plan()
        primary = scenario_settings(plan, 'primary')
        for name, spec in plan['scenarios'].items():
            settings = scenario_settings(plan, name)
            changed = {k for k in settings if settings[k] != primary[k]}
            self.assertTrue(changed <= set(spec), name)
        self.assertEqual(scenario_settings(plan, 'sensitivity_exponential_form')['cl_form'], 'exponential')


class CovariateConstruction(unittest.TestCase):
    def test_backsolved_creatinine_reproduces_clearance(self):
        for age, weight, sex, crcl in ((40, 60, 'MALE', 140), (75, 100, 'FEMALE', 10), (60, 80, 'FEMALE', 45)):
            scr = backsolve_serum_creatinine(crcl, age, weight, sex)
            self.assertAlmostEqual(cockcroft_gault(age, weight, scr, sex), crcl, places=9)

    def test_subject_covariates_follow_from_one_person(self):
        settings = scenario_settings(load_plan(), 'primary')
        subject = draw_subject(random.Random(1), settings, 'moderate')
        self.assertTrue(30 <= subject['crcl'] <= 50)
        self.assertAlmostEqual(cockcroft_gault(subject['age'], subject['weight'], subject['scr_umol_l'], subject['sex']),
                               subject['crcl'], places=9)
        self.assertEqual(subject['egfr'], egfr_ckd_epi_2021(subject['age'], subject['scr_umol_l'], subject['sex']))


class CommittedReport(unittest.TestCase):
    def test_committed_report_reproduces_exactly(self):
        committed = json.loads(REPORT.read_text())
        self.assertEqual(committed['plan_sha256'], PLAN_SHA256)
        self.assertEqual(run_check()['report_sha256'], committed['report_sha256'])
        body = {k: v for k, v in committed.items() if k != 'report_sha256'}
        self.assertEqual(digest(body), committed['report_sha256'])
        self.assertFalse(committed['clinical_prediction_validated'])

    def test_recorded_result(self):
        committed = json.loads(REPORT.read_text())
        self.assertEqual(committed['primary_endpoint_by_group'],
                         {'mild': 'consistent', 'moderate': 'consistent', 'severe': 'model_under_predicts'})
        self.assertEqual(committed['classification_across_scenarios']['mild'], ['consistent'])
        for group in ('moderate', 'severe'):
            self.assertEqual(committed['classification_across_scenarios'][group], ['consistent', 'model_under_predicts'])


def state(scr):
    values = dict(age_years=65, biological_sex='FEMALE', weight=70, height=165, serum_creatinine=scr)
    return {'schema_version': STATE_SCHEMA, 'purpose': 'synthetic_educational',
            'fields': {k: {'value': v, 'unit': UNITS[k], 'origin': 'synthetic_input', 'observed_at': None,
                           'source_ref': None} for k, v in values.items()}}


class KimApplicabilityFinding(unittest.TestCase):
    def test_finding_cites_the_committed_report(self):
        finding = load_applicability_findings()['findings'][0]
        self.assertEqual(hashlib.sha256(REPORT.read_bytes()).hexdigest(), finding['evidence']['report_file_sha256'])
        committed = json.loads(REPORT.read_text())
        self.assertEqual(committed['primary_endpoint_by_group']['severe'], 'model_under_predicts')
        self.assertEqual(finding['status'], 'exploratory_finding_not_validation')

    def test_severe_warning_below_egfr_30(self):
        low = estimate_kim_covariates(state(180))
        self.assertLess(low['estimates']['egfr_indexed']['value'], 30)
        self.assertEqual([f['id'] for f in low['applicability_findings']], ['renal-under-prediction-severe'])
        self.assertTrue(any('may under-predict' in w and 'severe' in w for w in low['warnings']))
        self.assertFalse(any('moderate renal impairment' in w for w in low['warnings']))

    def test_moderate_warning_from_egfr_30_to_below_50(self):
        moderate = estimate_kim_covariates(state(120))
        egfr = moderate['estimates']['egfr_indexed']['value']
        self.assertTrue(30 <= egfr < 50, egfr)
        self.assertEqual([f['id'] for f in moderate['applicability_findings']], ['renal-under-prediction-moderate'])
        self.assertEqual(moderate['applicability_findings'][0]['evidence_report'], 'docs/verification/lenalidomide_renal_recheck_v1.json')
        self.assertTrue(any('moderate renal impairment' in w for w in moderate['warnings']))
        self.assertEqual(moderate['findings_version'], 'kim-applicability-findings-v2.0')

    def test_no_renal_warning_at_or_above_egfr_50(self):
        mild = estimate_kim_covariates(state(80))
        self.assertGreaterEqual(mild['estimates']['egfr_indexed']['value'], 50)
        self.assertEqual(mild['applicability_findings'], [])
        self.assertFalse(any('may under-predict' in w for w in mild['warnings']))

    def test_band_edges(self):
        from intelligence_store.kim_model import finding_applies
        severe, moderate = load_applicability_findings()['findings']
        self.assertEqual([finding_applies(severe, v) for v in (29.99, 30, 50)], [True, False, False])
        self.assertEqual([finding_applies(moderate, v) for v in (29.99, 30, 49.99, 50)], [False, True, True, False])

    def test_superseded_findings_kept_unchanged(self):
        from intelligence_store import kim_model as K
        self.assertEqual(hashlib.sha256(K.SUPERSEDED_FINDINGS_PATH.read_bytes()).hexdigest(), K.SUPERSEDED_FINDINGS_SHA256)
        current = load_applicability_findings()
        self.assertEqual(current['supersedes']['sha256'], K.SUPERSEDED_FINDINGS_SHA256)
        old = json.loads(K.SUPERSEDED_FINDINGS_PATH.read_text())['findings'][0]
        carried = {k: v for k, v in current['findings'][0].items() if k != 'recheck'}
        self.assertEqual(carried, old)

    def test_moderate_finding_cites_the_recheck(self):
        moderate = load_applicability_findings()['findings'][1]
        report = moderate['evidence']['report']
        self.assertEqual(hashlib.sha256((ROOT / report).read_bytes()).hexdigest(), moderate['evidence']['report_file_sha256'])
        result = json.loads((ROOT / report).read_text())['result_by_model']['lenalidomide_kim_2026']
        self.assertEqual(result['primary']['moderate'], 'model_under_predicts')
        self.assertEqual(result['across_scenarios']['moderate'], ['model_under_predicts'])
        self.assertEqual(moderate['status'], 'exploratory_finding_not_validation')

    def test_changed_findings_or_dose_evidence_is_refused(self):
        data = ROOT / 'intelligence_store' / 'data'
        for name, loader in (('kim_applicability_findings_v2.json', load_applicability_findings),
                             ('lenalidomide_dose_proportionality_evidence_v1.json', load_dose_proportionality_evidence)):
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / name
                path.write_bytes((data / name).read_bytes() + b' ')
                with self.assertRaises(CovariateEstimationError):
                    loader(path)


class DoseProportionalityEvidence(unittest.TestCase):
    def test_source_file_is_the_pinned_report(self):
        source = load_dose_proportionality_evidence()['primary_source']
        self.assertEqual(hashlib.sha256((ROOT / source['local_file']).read_bytes()).hexdigest(), source['sha256'])

    def test_quotes_appear_on_the_cited_page(self):
        try:
            import pypdf
        except ImportError:
            self.skipTest('pypdf not installed')
        source = load_dose_proportionality_evidence()['primary_source']
        text = ' '.join((pypdf.PdfReader(str(ROOT / source['local_file'])).pages[19].extract_text() or '').split())
        for quote in source['quotes']:
            self.assertIn(quote, text)


if __name__ == '__main__':
    unittest.main()
