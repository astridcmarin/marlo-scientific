"""Patient Lab 2.1c: locked plan, covariate construction and reproducible report for the Kim renal-group check."""
import json
from pathlib import Path
import random
import tempfile
import unittest

from intelligence_store.patient_state import digest
from intelligence_store.covariate_estimation import cockcroft_gault, egfr_ckd_epi_2021
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


if __name__ == '__main__':
    unittest.main()
