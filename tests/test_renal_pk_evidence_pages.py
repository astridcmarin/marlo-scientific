import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
from landscape_ui import register_landscape
from landscape_ui import renal_pk_evidence_pages as pages


class RenalEvidencePagesTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.add_url_rule('/', 'home', lambda: 'Home')
        register_landscape(app)
        self.client = app.test_client()
        self.path = '/landscape/patient-lab/published-renal-pk'

    def test_reference_renders_without_database_or_network(self):
        with patch('requests.get', side_effect=AssertionError('no network')):
            response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        for text in ('2181 (703)', '6021 (847)', '2.761', 'Independent human review remains pending',
                     'Why there is no patient overlay', 'Clinical prediction validated: <strong>false</strong>'):
            self.assertIn(text, body)
        self.assertEqual(body.count('class="nav-item active"'), 1)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_export_retains_unknowns_and_source_and_correct_ratio(self):
        response = self.client.get(self.path+'?format=json')
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertAlmostEqual(data['derived_auc_mean_ratios']['moderate'],6021/2181)
        self.assertFalse(data['individual_model_comparison_performed'])
        for group in data['evidence']['groups']:
            self.assertIsNone(group['representative_crcl'])
        self.assertEqual(data['evidence']['source']['sha256'],pages.PINS['ema_lenalidomide_2008.pdf'])

    def test_source_download_is_exact_pinned_pdf(self):
        response = self.client.get(self.path+'?format=pdf')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.mimetype,'application/pdf')
        self.assertEqual(response.data,(pages.DATA/'ema_lenalidomide_2008.pdf').read_bytes())

    def test_corrupt_or_missing_bundle_withholds_all_formats(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in pages.PINS:
                (root/name).write_bytes(b'corrupt')
            with patch.object(pages,'DATA',root):
                for fmt in ('html','json','pdf'):
                    self.assertEqual(self.client.get(self.path+'?format='+fmt).status_code,503)
            (root/'renal_pk_group_evidence_v1.json').unlink()
            with patch.object(pages,'DATA',root):
                self.assertEqual(self.client.get(self.path).status_code,503)

    def test_patient_parameters_duplicates_and_mutation_rejected(self):
        for query in ('patient_id=1','revision_id=1','format=json&format=pdf','format=csv','path=../../x'):
            self.assertEqual(self.client.get(self.path+'?'+query).status_code,400)
        self.assertEqual(self.client.post(self.path).status_code,405)


if __name__ == '__main__': unittest.main()
