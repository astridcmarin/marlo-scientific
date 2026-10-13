"""Fictional software fixtures only; none are observed evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result
review = module('_tested_intake', 'intelligence_store/bortezomib_observation_intake.py')
cli = module('_tested_cli', 'scripts/review_bortezomib_observation_intake.py')


def fixture():
    data = review.load_json(review.TEMPLATE_PATH)
    data['data_origin'] = 'published_observations'
    sha = hashlib.sha256(b'FICTIONAL TEST ARCHIVE - NOT EVIDENCE').hexdigest()
    data['sources'][0].update(location='Fictional test caption', sha256=sha)
    checks = data['source_review']
    checks.update(reviewer='Fictional test reviewer', reviewed_on='2026-10-12')
    for field in ('series_selection', 'normalization', 'aggregation', 'population_and_schedule'):
        checks[field] = {'status': 'reviewed', 'source_location': 'Fictional test caption',
                         'rationale': 'Fictional software test only; no source truth claim.'}
    data['observations'] = [{
        'id': 'fictional-1', 'source_id': 'reece2011', 'series_id': 'fictional-series',
        'subject_or_group_id': 'fictional-group', 'visit_id': 'fictional-visit',
        'arm': 'fictional-arm', 'population': 'fictional-population',
        'schedule': 'fictional-schedule', 'pairing_evidence_location': 'Fictional caption',
        'route': 'IV', 'dose_mg_per_m2': 1.3, 'aggregation': 'group_mean_at_time', 'endpoint_n': 12,
        'concentration': {'quantity': 'plasma_total_bortezomib', 'unit': 'nM',
            'value': 1.79, 'time_h': 1, 'source_location': 'Fictional PK point',
            'extraction_uncertainty': 0.1, 'uncertainty_kind': 'absolute_digitization_bound'},
        'response': {'quantity': '20S_inhibition_percentage_points', 'value': 40,
            'time_h': 1, 'source_location': 'Fictional PD point', 'extraction_uncertainty': 1,
            'uncertainty_kind': 'absolute_digitization_bound'}}]
    return data, {'reece2011': sha}


class ObservationIntakeTests(unittest.TestCase):
    def test_blank_template_cannot_advance_science(self):
        result = review.review_intake(review.load_json(review.TEMPLATE_PATH))
        self.assertEqual(result['status'], 'evidence_incomplete')
        self.assertEqual(result['structurally_matched_record_count'], 0)
        self.assertIsNone(result['observed_concentration_domain_nm'])
        self.assertFalse(result['eligible_for_manual_comparison_review'])

    def test_complete_fixture_is_only_manual_review_not_validation(self):
        data, hashes = fixture()
        before = copy.deepcopy(data)
        result = review.review_intake(data, verified_archive_hashes=hashes)
        self.assertEqual(data, before)
        self.assertEqual(result['status'], 'manual_comparison_review_required')
        self.assertEqual(result['normalized_records'][0]['activity_percent_of_baseline'], 60)
        for key in ('clinical_prediction_validated', 'ready_for_patient_simulation',
                    'step105_discrepancy_resolved', 'fitting_performed'):
            self.assertIs(result[key], False)
        self.assertIsNone(result['rmse']); self.assertIsNone(result['mae'])
        self.assertEqual(result, review.review_intake(data, verified_archive_hashes=hashes))
        sha = result.pop('report_sha256')
        self.assertEqual(sha, review.digest(result))

    def test_summary_peaks_are_not_accepted_as_pairs(self):
        data, hashes = fixture()
        data['observations'][0]['aggregation'] = 'mean_of_patient_peak_inhibition_summaries'
        r = review.review_intake(data, verified_archive_hashes=hashes)
        self.assertEqual(r['structurally_matched_record_count'], 0)
        self.assertIn('row_0:peaks_or_unsupported_aggregation', r['blocking_issues'])

    def test_mismatched_sampling_times_and_units_block_records(self):
        for field, value in (('time_h', 2), ('unit', 'ng/mL'), ('quantity', 'unbound_bortezomib')):
            data, hashes = fixture()
            data['observations'][0]['concentration'][field] = value
            r = review.review_intake(data, verified_archive_hashes=hashes)
            self.assertEqual(r['structurally_matched_record_count'], 0)

    def test_missing_or_wrong_uncertainty_cannot_use_sd_or_boolean(self):
        for value, kind in ((None, 'absolute_digitization_bound'), (True, 'absolute_digitization_bound'),
                            (-1, 'absolute_digitization_bound'), (1, 'standard_deviation')):
            data, hashes = fixture()
            data['observations'][0]['response'].update(extraction_uncertainty=value, uncertainty_kind=kind)
            self.assertEqual(review.review_intake(data, verified_archive_hashes=hashes)
                             ['structurally_matched_record_count'], 0)

    def test_declared_hashes_and_development_source_do_not_prove_external_validation(self):
        data, hashes = fixture()
        self.assertFalse(review.review_intake(data)['eligible_for_manual_comparison_review'])
        data['relationship_to_model'] = 'independent_dataset'
        r = review.review_intake(data, verified_archive_hashes=hashes)
        self.assertIn('development_source_cannot_be_external_validation', r['blocking_issues'])

    def test_duplicate_records_and_bad_denominators_are_flagged(self):
        data, hashes = fixture()
        data['observations'].append(copy.deepcopy(data['observations'][0]))
        r = review.review_intake(data, verified_archive_hashes=hashes)
        self.assertIn('row_1:duplicate_sampling_record', r['blocking_issues'])
        for n in (True, 0, 1.5):
            data, hashes = fixture(); data['observations'][0]['endpoint_n'] = n
            self.assertEqual(review.review_intake(data, verified_archive_hashes=hashes)
                             ['structurally_matched_record_count'], 0)

    def test_invalid_schema_nonfinite_and_duplicate_json_fail(self):
        with self.assertRaises(ValueError): review.review_intake({'schema_version': 'unknown'})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'input.json'
            for text in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
                path.write_text(text)
                with self.assertRaises(ValueError): review.load_json(path)
        for value in (True, '1', float('inf'), 10**1000):
            self.assertFalse(review.number(value))

    def test_changed_model_reference_blocks_review(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'model.json'; path.write_text('{}')
            with patch.object(review, 'MODEL_PATH', path), self.assertRaises(ValueError):
                review.review_intake(review.load_json(review.TEMPLATE_PATH))

    def test_cli_empty_report_roundtrip_never_overwrites(self):
        command = [sys.executable, str(ROOT/'scripts/review_bortezomib_observation_intake.py')]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'report.json'
            result = subprocess.run(command+['--output', str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('evidence_incomplete', result.stdout)
            self.assertEqual(json.loads(path.read_text())['submitted_record_count'], 0)
            original = path.read_bytes()
            self.assertNotEqual(subprocess.run(command+['--output', str(path)], capture_output=True).returncode, 0)
            self.assertEqual(path.read_bytes(), original)
            self.assertNotEqual(subprocess.run(command+['--patient-id', '1'], capture_output=True).returncode, 0)

    def test_archive_hashing_rejects_traversal_symlink_and_hash_mismatch(self):
        data, hashes = fixture()
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); path = base/'input.json'
            source = base/'source.txt'; source.write_bytes(b'FICTIONAL TEST ARCHIVE - NOT EVIDENCE')
            data['sources'][0]['archive_file'] = 'source.txt'
            self.assertEqual(cli.archive_hashes(data, path), hashes)
            source.write_bytes(b'altered')
            self.assertFalse(review.review_intake(data, verified_archive_hashes=cli.archive_hashes(data, path))
                             ['eligible_for_manual_comparison_review'])
            for name in ('../source.txt', '/tmp/source.txt'):
                data['sources'][0]['archive_file'] = name
                with self.assertRaises(ValueError): cli.archive_hashes(data, path)
            sub = base/'inner'; sub.mkdir(); (sub/'outside-link').symlink_to(source)
            data['sources'][0]['archive_file'] = 'outside-link'
            with self.assertRaises(ValueError): cli.archive_hashes(data, sub/'input.json')

if __name__ == '__main__':
    unittest.main()
