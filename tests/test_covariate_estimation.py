"""Covariate estimators: worked examples, provenance, pinned sources and the Hughes adapter."""
import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from flask import Flask

from intelligence_store.patient_state import UNITS, SCHEMA_VERSION as STATE_SCHEMA, digest
from intelligence_store.covariate_estimation import (
    ABW_FACTOR, CG_FEMALE_FACTOR, CREATININE_UMOL_PER_MG_DL, DEVINE_BASE_KG, DEVINE_KG_PER_INCH, JANMAHASATIAN,
    WEIGHT_BASES, CovariateEstimationError, adjusted_body_weight, body_mass_index, cockcroft_gault,
    compare_weight_bases, estimate_hughes_covariates, example_state, fat_free_mass_janmahasatian,
    ideal_body_weight_devine, load_formula_registry, load_variability_extract, load_weight_basis_assessment,
    register_covariate_estimation_commands, to_hughes_model_inputs)
from intelligence_store.pk_model_inputs import preview_model_inputs, validate_model_inputs

ROOT = Path(__file__).resolve().parents[1]


def state(**values):
    fields = {}
    for name, value in values.items():
        fields[name] = {'value': value, 'unit': UNITS[name], 'origin': 'synthetic_input',
                        'observed_at': None, 'source_ref': None}
    return {'schema_version': STATE_SCHEMA, 'purpose': 'synthetic_educational', 'fields': fields}


TYPICAL = dict(age_years=60, biological_sex='MALE', weight=72, height=175, serum_creatinine=88.4)
OBESE = dict(age_years=55, biological_sex='FEMALE', weight=130, height=160, serum_creatinine=70)


class FormulaWorkedExamples(unittest.TestCase):
    """Independent hand calculations, not values copied from the implementation."""

    def test_cockcroft_gault(self):
        # (140-60)*72/(72*1.0 mg/dL) = 80; female x0.85 = 68.
        self.assertAlmostEqual(cockcroft_gault(60, 72, 88.4, 'MALE'), 80.0, places=10)
        self.assertAlmostEqual(cockcroft_gault(60, 72, 88.4, 'FEMALE'), 68.0, places=10)
        # Doubling creatinine halves clearance.
        self.assertAlmostEqual(cockcroft_gault(60, 72, 176.8, 'MALE'), 40.0, places=10)

    def test_devine_ideal_body_weight(self):
        self.assertAlmostEqual(ideal_body_weight_devine(152.4, 'MALE'), 50.0, places=10)
        self.assertAlmostEqual(ideal_body_weight_devine(152.4, 'FEMALE'), 45.5, places=10)
        self.assertAlmostEqual(ideal_body_weight_devine(182.88, 'MALE'), 77.6, places=10)  # 72 in

    def test_adjusted_body_weight(self):
        self.assertAlmostEqual(adjusted_body_weight(120, 70), 90.0, places=10)

    def test_body_mass_index_and_janmahasatian(self):
        self.assertAlmostEqual(body_mass_index(80, 180), 24.691358024691358, places=10)
        # 9270*80/(6680+216*24.6914) and 9270*60/(8780+244*22.0386)
        self.assertAlmostEqual(fat_free_mass_janmahasatian(80, 180, 'MALE'), 61.731409544950, places=8)
        self.assertAlmostEqual(fat_free_mass_janmahasatian(60, 165, 'FEMALE'), 39.286845659001, places=8)

    def test_invalid_inputs_are_rejected(self):
        for call in (lambda: cockcroft_gault(140, 70, 80, 'MALE'), lambda: cockcroft_gault(60, 70, 0, 'MALE'),
                     lambda: cockcroft_gault(60, 70, 80, None), lambda: body_mass_index(True, 170),
                     lambda: fat_free_mass_janmahasatian(70, float('nan'), 'MALE'),
                     lambda: ideal_body_weight_devine(50, 'FEMALE')):
            with self.assertRaises(CovariateEstimationError):
                call()

    def test_module_constants_match_pinned_registry(self):
        formulas = load_formula_registry()['formulas']
        registry = load_formula_registry()
        self.assertEqual(registry['constants']['creatinine_umol_per_mg_dl']['value'], CREATININE_UMOL_PER_MG_DL)
        for sex, (num, intercept, slope) in JANMAHASATIAN.items():
            self.assertEqual(formulas['fat_free_mass_janmahasatian']['constants'][sex],
                             {'numerator': num, 'intercept': intercept, 'bmi_slope': slope})
        for sex, base in DEVINE_BASE_KG.items():
            self.assertEqual(formulas['ideal_body_weight_devine']['constants'][sex]['base_kg'], base)
        self.assertEqual(formulas['ideal_body_weight_devine']['constants']['kg_per_inch_over_60'], DEVINE_KG_PER_INCH)
        self.assertEqual(formulas['adjusted_body_weight_0_4']['constants']['correction_factor'], ABW_FACTOR)
        self.assertEqual(formulas['creatinine_clearance_cockcroft_gault']['constants']['female_factor'], CG_FEMALE_FACTOR)
        self.assertEqual(tuple(sorted(formulas['creatinine_clearance_cockcroft_gault']['supported_weight_bases'])),
                         tuple(sorted(WEIGHT_BASES)))


class PinnedSources(unittest.TestCase):
    def test_changed_files_are_refused(self):
        for loader, name in ((load_formula_registry, 'covariate_formula_registry_v1.json'),
                             (load_weight_basis_assessment, 'hughes_weight_basis_assessment_v1.json'),
                             (load_variability_extract, 'hughes_variability_extract_v1.json')):
            original = (ROOT / 'intelligence_store' / 'data' / name).read_bytes()
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / name
                path.write_bytes(original + b' ')
                with self.assertRaises(CovariateEstimationError):
                    loader(path)

    def test_variability_extract_reproduces_table2(self):
        extract = load_variability_extract()
        omega = extract['random_effects']['omega_matrix']
        reported = extract['table2_reported']
        self.assertAlmostEqual(100 * math.sqrt(omega[0][0]), reported['bsv_cl_pct_cv'], delta=0.05)
        self.assertAlmostEqual(100 * math.sqrt(omega[1][1]), reported['bsv_v_pct_cv'], delta=0.05)
        self.assertAlmostEqual(100 * math.sqrt(omega[2][2]), reported['bsv_ktr_pct_cv'], delta=0.05)
        self.assertAlmostEqual(omega[0][1] / math.sqrt(omega[0][0] * omega[1][1]), reported['corr_cl_v'], delta=0.001)
        self.assertGreater(omega[0][0] * omega[1][1] - omega[0][1] ** 2, 0)  # positive definite 2x2 block

    def test_assessment_is_unresolved_and_names_supported_bases(self):
        assessment = load_weight_basis_assessment()
        self.assertEqual(assessment['status'], 'unresolved')
        self.assertIn(assessment['decision']['primary_assumption'], WEIGHT_BASES)
        self.assertEqual(set(assessment['basis_evidence']), set(WEIGHT_BASES))

    def test_reconstruction_script_supports_recorded_primary_assumption(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'reconstruct_hughes_crcl_weight_basis.py'),
                                 '--n', '4000'], capture_output=True, text=True, check=True, timeout=120)
        report = json.loads(result.stdout)
        primary = load_weight_basis_assessment()['decision']['primary_assumption']
        for scenario in report['scenarios'].values():
            self.assertEqual(scenario['closest_basis'], primary)


class HughesCovariateEstimates(unittest.TestCase):
    def test_estimate_records_chain_and_hashes(self):
        report = estimate_hughes_covariates(state(**TYPICAL), 'total_body_weight')
        self.assertEqual(report['status'], 'estimated')
        self.assertAlmostEqual(report['estimates']['creatinine_clearance']['value'], 80.0, places=10)
        self.assertEqual([d['quantity'] for d in report['derivations']],
                         ['body_mass_index', 'fat_free_mass', 'creatinine_clearance'])
        crcl_step = report['derivations'][-1]
        self.assertEqual(crcl_step['formula_id'], 'creatinine_clearance_cockcroft_gault')
        self.assertEqual(crcl_step['assumptions']['weight_basis'], 'total_body_weight')
        self.assertEqual(crcl_step['inputs']['dosing_weight']['from'], 'patient_state.weight')
        body = {k: v for k, v in report.items() if k != 'report_sha256'}
        self.assertEqual(report['report_sha256'], digest(body))
        self.assertEqual(report, estimate_hughes_covariates(state(**TYPICAL), 'total_body_weight'))
        self.assertFalse(report['ready_for_patient_simulation'])
        self.assertEqual(report['simulation_status'], 'not_run')

    def test_weight_basis_has_no_default_and_is_labelled(self):
        with self.assertRaises(CovariateEstimationError):
            estimate_hughes_covariates(state(**TYPICAL), None)
        with self.assertRaises(CovariateEstimationError):
            estimate_hughes_covariates(state(**TYPICAL), 'lean_body_weight')
        report = estimate_hughes_covariates(state(**TYPICAL), 'ideal_body_weight_devine')
        self.assertTrue(report['weight_basis_evidence']['is_primary_assumption'])
        self.assertEqual(report['weight_basis_evidence']['assessment_status'], 'unresolved')
        self.assertEqual(report['derivations'][2]['quantity'], 'ideal_body_weight')

    def test_obese_patient_orders_bases(self):
        values = {b: estimate_hughes_covariates(state(**OBESE), b)['estimates']['creatinine_clearance']['value']
                  for b in WEIGHT_BASES}
        self.assertGreater(values['total_body_weight'], values['adjusted_body_weight_0_4'])
        self.assertGreater(values['adjusted_body_weight_0_4'], values['ideal_body_weight_devine'])

    def test_missing_inputs_produce_no_estimate(self):
        partial = dict(TYPICAL)
        del partial['serum_creatinine']
        report = estimate_hughes_covariates(state(**partial), 'ideal_body_weight_devine')
        self.assertEqual(report['status'], 'missing_inputs')
        self.assertEqual(report['missing_fields'], ['serum_creatinine'])
        self.assertIsNone(report['estimates'])
        with self.assertRaises(CovariateEstimationError):
            to_hughes_model_inputs(report)

    def test_coverage_and_conflict_warnings(self):
        impaired = dict(TYPICAL, serum_creatinine=300, egfr_indexed=20, creatinine_clearance=50)
        report = estimate_hughes_covariates(state(**impaired), 'ideal_body_weight_devine')
        status = {c['field']: c['status'] for c in report['coverage_checks']}
        self.assertEqual(status['serum_creatinine'], 'outside_reported_range')
        self.assertEqual(status['creatinine_clearance'], 'outside_reported_range')
        text = ' '.join(report['warnings'])
        self.assertIn('extrapolation', text)
        self.assertIn('Indexed eGFR', text)
        self.assertIn('neither replaces the other', text)

    def test_short_stature_is_flagged_for_ideal_weight(self):
        short = dict(TYPICAL, height=150)
        report = estimate_hughes_covariates(state(**short), 'ideal_body_weight_devine')
        self.assertTrue(any('Devine' in w for w in report['warnings']))

    def test_adapter_feeds_existing_hughes_input_preview(self):
        report = estimate_hughes_covariates(example_state(), 'ideal_body_weight_devine')
        inputs = to_hughes_model_inputs(report)
        canonical = validate_model_inputs(inputs)
        for field in canonical['fields'].values():
            self.assertEqual(field['origin'], 'assumption')
            self.assertIn(report['report_sha256'], field['source_ref'])
        self.assertIn('ideal_body_weight_devine', canonical['fields']['creatinine_clearance']['source_ref'])
        preview = preview_model_inputs(inputs)
        self.assertEqual(preview['status'], 'parameter_preview_available')
        self.assertFalse(preview['ready_for_patient_simulation'])
        tampered = copy.deepcopy(report)
        tampered['estimates']['creatinine_clearance']['value'] = 120.0
        with self.assertRaises(CovariateEstimationError):
            to_hughes_model_inputs(tampered)

    def test_comparison_isolates_weight_basis_effect(self):
        comparison = compare_weight_bases(state(**OBESE))
        rows = {r['weight_basis']: r for r in comparison['rows']}
        self.assertEqual(set(rows), set(WEIGHT_BASES))
        ffm = {r['fat_free_mass_kg'] for r in rows.values()}
        self.assertEqual(len(ffm), 1)  # FFM does not depend on the CrCl weight basis
        high, low = rows['total_body_weight'], rows['ideal_body_weight_devine']
        expected = (high['creatinine_clearance_ml_min'] / low['creatinine_clearance_ml_min']) ** 0.224
        self.assertAlmostEqual(high['typical_apparent_clearance_l_h'] / low['typical_apparent_clearance_l_h'], expected, places=12)
        self.assertLess(comparison['summary']['typical_cl_max_to_min_ratio'], comparison['summary']['crcl_max_to_min_ratio'])


class CovariateEstimateCommand(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        register_covariate_estimation_commands(app)
        self.runner = app.test_cli_runner()

    def test_example_comparison(self):
        result = self.runner.invoke(args=['covariate-estimate', '--example', '--compare-bases'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(len(json.loads(result.stdout)['rows']), 3)

    def test_weight_basis_is_required(self):
        result = self.runner.invoke(args=['covariate-estimate', '--example'])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('--weight-basis', result.output)

    def test_output_file_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'estimate.json'
            args = ['covariate-estimate', '--example', '--weight-basis', 'ideal_body_weight_devine', '--output', str(path)]
            self.assertEqual(self.runner.invoke(args=args).exit_code, 0)
            self.assertNotEqual(self.runner.invoke(args=args).exit_code, 0)


if __name__ == '__main__':
    unittest.main()
