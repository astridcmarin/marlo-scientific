import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('_tested_btz_evidence',ROOT/'intelligence_store/bortezomib_evidence_review.py')
review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)


class EvidenceReviewTests(unittest.TestCase):
    def test_source_table_footnotes_preserve_endpoint_specific_denominators(self):
        result=review.build_evidence_review();rows=result['rows']
        self.assertEqual([r['n'] for r in rows],[11,11,11,11,12,12,11,11])
        self.assertEqual([r['mean_peak_inhibition_percent'] for r in rows],
                         [69.7,83.4,78.3,83.5,73,78.6,78.2,82.9])
        self.assertEqual([r['sd_percentage_points'] for r in rows],[11,7.02,7.09,7.05,10.8,6.5,9.27,9.46])
        self.assertEqual(result['evidence']['population']['evaluable_per_dose'],12)
        self.assertEqual(result['evidence']['population']['randomized_per_dose'],21)
        self.assertNotIn('pooled_n',result)

    def test_bounds_screen_does_not_create_pairs_or_prediction_metrics(self):
        r=review.build_evidence_review()
        self.assertEqual(r['summary_count'],8);self.assertEqual(r['summaries_above_ceiling'],7)
        self.assertEqual(r['status'],'review_required')
        self.assertEqual(r['rows'][0]['excess_above_ceiling_percentage_points'],0)
        self.assertAlmostEqual(r['rows'][4]['excess_above_ceiling_percentage_points'],1.9)
        self.assertEqual(r['matched_concentration_response_pairs'],0)
        self.assertIsNone(r['rmse']);self.assertIsNone(r['mae'])
        for row in r['rows']:
            self.assertIsNone(row['paired_plasma_concentration_nm'])
            self.assertIsNone(row['paired_time_h'])
            self.assertIsNone(row['model_prediction_at_observed_concentration'])
        self.assertFalse(r['clinical_prediction_validated']);self.assertFalse(r['ready_for_patient_simulation'])
        self.assertIn('not_independent_external_validation',r['evidence']['relationship_to_model'])
        self.assertFalse(r['evidence']['model_source_review']['independent_review'])

    def test_report_hash_is_deterministic_and_returned_mutation_is_isolated(self):
        original=review.build_evidence_review();other=review.build_evidence_review()
        self.assertEqual(original,other)
        digest=other.pop('report_sha256')
        self.assertEqual(digest,hashlib.sha256(json.dumps(other,sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest())
        original['rows'][0]['n']=999
        self.assertEqual(review.build_evidence_review()['rows'][0]['n'],11)

    def test_missing_and_tampered_either_reference_block_review(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'reference.json'
            for target in ['DATA_PATH','MODEL_PATH']:
                with patch.object(review,target,path):
                    with self.assertRaises(ValueError):review.build_evidence_review()
                    path.write_text('{}')
                    with self.assertRaises(ValueError):review.build_evidence_review()
                path.unlink(missing_ok=True)

    def test_standalone_export_roundtrip_and_no_overwrite(self):
        command=[sys.executable,str(ROOT/'scripts/review_bortezomib_evidence.py')]
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'review.json'
            p=subprocess.run(command+['--output',str(path)],cwd=d,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(json.loads(path.read_text()),review.build_evidence_review())
            before=path.read_bytes()
            self.assertNotEqual(subprocess.run(command+['--output',str(path)],capture_output=True).returncode,0)
            self.assertEqual(path.read_bytes(),before)
            self.assertNotEqual(subprocess.run(command+['--patient-id','1'],capture_output=True).returncode,0)


class EvidencePageTests(unittest.TestCase):
    def setUp(self):
        from flask import Flask
        from landscape_ui import register_landscape
        app=Flask(__name__);app.config['TESTING']=True;app.add_url_rule('/','home',lambda:'Home')
        register_landscape(app);self.client=app.test_client()
        self.path='/landscape/simulation-lab/bortezomib-evidence'

    def test_page_export_model_warning_and_navigation_without_database(self):
        r=self.client.get(self.path)
        self.assertEqual(r.status_code,200)
        text=r.get_data(as_text=True)
        self.assertIn('7 of 8',text);self.assertIn('standard deviation',text)
        self.assertIn('All Simulation Lab experiments',text)
        self.assertEqual(text.count('class="nav-item active"'),1)
        self.assertEqual(r.headers['Cache-Control'],'no-store')
        self.assertEqual(self.client.get(self.path+'?format=json').json,review.build_evidence_review())
        model=self.client.get('/landscape/simulation-lab/bortezomib-proteasome').get_data(as_text=True)
        self.assertIn('id="observed-evidence-notice"',model)
        self.assertIn(self.path,model)

    def test_reject_unknown_duplicate_mutating_requests_and_unavailable_evidence(self):
        for query in ['patient_id=1','format=csv','format=json&format=html','concentration_nm=10']:
            self.assertEqual(self.client.get(self.path+'?'+query).status_code,400)
        self.assertEqual(self.client.post(self.path).status_code,405)
        with patch('landscape_ui.bortezomib_evidence_pages.build_evidence_review',side_effect=ValueError('bad')):
            self.assertEqual(self.client.get(self.path).status_code,503)
            self.assertEqual(self.client.get(self.path+'?format=json').status_code,503)


if __name__=='__main__':unittest.main()
