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

    def test_study_population_is_shown_with_its_sources(self):
        body = self.client.get(self.path).get_data(as_text=True)
        self.assertIn('Who the subjects were', body)
        self.assertIn('non-malignant conditions', body)
        self.assertIn('healthy subjects of similar age', body)
        self.assertNotIn('disease context are not established', body)
        population = self.client.get(self.path+'?format=json').json['evidence']['population']
        self.assertEqual(population['recorded_in']['item'], 'renal_study_population')

    def test_v2_changes_only_population_records(self):
        import hashlib, json
        v2 = json.loads((pages.DATA/pages.EVIDENCE_FILE).read_text())
        (name, sha), = pages.SUPERSEDED_EVIDENCE.items()
        raw = (pages.DATA/name).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), sha)
        self.assertEqual(v2['supersedes']['sha256'], sha)
        v1 = json.loads(raw)
        for key in ('study_id', 'source', 'related_publication', 'groups'):
            self.assertEqual(v2[key], v1[key], key)
        self.assertEqual({k: v for k, v in v2['design'].items() if k != 'population_disease_context'},
                         {k: v for k, v in v1['design'].items() if k != 'population_disease_context'})
        self.assertEqual(v2['limitations'][:len(v1['limitations'])], v1['limitations'])
        sums = json.loads((pages.DATA/'SHA256SUMS.json').read_text())
        self.assertEqual(sums[pages.EVIDENCE_FILE], pages.PINS[pages.EVIDENCE_FILE])
        self.assertEqual(sums[name], sha)

    def test_population_quotes_match_the_reconciliation_record(self):
        import hashlib, json
        population = json.loads((pages.DATA/pages.EVIDENCE_FILE).read_text())['population']
        root = Path(pages.__file__).resolve().parent.parent
        ref = population['recorded_in']
        raw = (root/ref['file']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), ref['sha256'])
        record = json.loads(raw)
        for key in ('impaired_groups', 'cause', 'normal_group'):
            node = record
            for token in population[key]['pointer'].strip('/').split('/'):
                node = node[token]
            self.assertEqual(node, population[key]['quote'], key)
        self.assertEqual(record['items'][5]['id'], ref['item'])

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
            (root/pages.EVIDENCE_FILE).unlink()
            with patch.object(pages,'DATA',root):
                self.assertEqual(self.client.get(self.path).status_code,503)

    def test_patient_parameters_duplicates_and_mutation_rejected(self):
        for query in ('patient_id=1','revision_id=1','format=json&format=pdf','format=csv','path=../../x'):
            self.assertEqual(self.client.get(self.path+'?'+query).status_code,400)
        self.assertEqual(self.client.post(self.path).status_code,405)


if __name__ == '__main__': unittest.main()
