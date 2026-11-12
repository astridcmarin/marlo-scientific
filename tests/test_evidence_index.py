"""The evidence index (plan docs/EVIDENCE_CONNECTIONS_PLAN.md, update 2): computed, read-only connections."""
import unittest

from intelligence_store import evidence_index as ei

DATA = 'intelligence_store/data/'


class Index(unittest.TestCase):
    def setUp(self):
        self.index = ei.build()

    def test_every_repository_reference_resolves_with_a_matching_checksum(self):
        self.assertEqual(self.index['findings'], [], 'A pinned file refers to a missing file or a changed checksum')
        for e in self.index['edges']:
            if e['type'] in ('cites', 'supersedes') and e['to'] in self.index['files']:
                self.assertEqual(self.index['files'][e['to']]['sha256'], e['sha256'], e)

    def test_every_connection_says_where_it_was_read(self):
        for e in self.index['edges']:
            self.assertTrue(e['field'], e)
            self.assertIn(e['type'], {'cites', 'supersedes', 'extracted_from', 'model_uses', 'model_plan', 'model_depends_on',
                                      'checks_model', 'pinned_by_code', 'read_by_code', 'imports', 'implemented_by'}
                          | {u for x in self.index['edges'] for u in [x['type']] if u.startswith('dataset_') or u in
                             ('built_from', 'tuned_on', 'reproduction', 'checked_blind', 'checked_blind_with_deviation',
                              'checked_not_blind', 'compared_model_to_model', 'reserved_for_blind_check')})

    def test_which_models_use_the_hughes_precision(self):
        v = ei.view(DATA + 'hughes_parameter_precision_v2.json')
        self.assertIn('lenalidomide_hughes_2019', v['depends_on_it']['models'])
        self.assertIn('model:lenalidomide_hughes_2019', [e['from'] for e in v['used_by']])
        self.assertEqual([e['from'] for e in v['supersedes']], [DATA + 'hughes_parameter_precision_v2.json'])

    def test_what_depends_on_the_hughes_weight_basis(self):
        v = ei.view(DATA + 'hughes_weight_basis_assessment_v1.json')
        self.assertIn('lenalidomide_hughes_2019', v['depends_on_it']['models'])
        self.assertIn('intelligence_store/covariate_estimation.py', v['depends_on_it']['code'])

    def test_supersession_is_read_from_the_files(self):
        v = ei.view(DATA + 'lenalidomide_kim_scope_v4.json')
        self.assertEqual([e['from'] for e in v['superseded_by']], [DATA + 'lenalidomide_kim_scope_v5.json'])
        self.assertTrue(any(f['superseded'] for f in ei.view(DATA + 'kim_applicability_findings_v3.json')['depends_on_it']['files']))

    def test_check_reports_link_to_their_models(self):
        report = 'docs/verification/lenalidomide_bridoux_check_v1.json'
        checked = {e['to'] for e in self.index['edges'] if e['from'] == report and e['type'] == 'checks_model'}
        self.assertEqual(checked, {'model:lenalidomide_hughes_2019', 'model:lenalidomide_kim_2026'})

    def test_unknown_file_is_refused(self):
        with self.assertRaises(KeyError):
            ei.view(DATA + 'no_such_file.json')


class Pages(unittest.TestCase):
    def setUp(self):
        from app.app import app
        self.client = app.test_client()

    def test_index_and_file_pages(self):
        page = self.client.get('/models/evidence')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'0 unresolved references', page.data)
        page = self.client.get('/models/evidence/' + DATA + 'hughes_parameter_precision_v2.json')
        self.assertEqual(page.status_code, 200)
        for text in (b'lenalidomide_hughes_2019', b'Supersedes', b'not whether it is right'):
            self.assertIn(text, page.data)
        self.assertEqual(self.client.get('/models/evidence/' + DATA + 'nope.json').status_code, 404)


if __name__ == '__main__':
    unittest.main()
