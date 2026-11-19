"""FDA guidance extracts after the owner's Track B review (19 November 2026): liver v2, kidney v3."""
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / 'intelligence_store' / 'data'


def load(name):
    return json.loads((D / name).read_text())


class Liver(unittest.TestCase):
    def setUp(self):
        self.v1 = load('fda_hepatic_impairment_guidance_2026_draft_v1.json')
        self.v2 = load('fda_hepatic_impairment_guidance_2026_draft_v2.json')

    def test_only_locations_and_the_table_reading_change(self):
        for k, q in self.v1['recommendations'].items():
            self.assertEqual(q['quote'], self.v2['recommendations'][k]['quote'], k)
        for t in ('child_pugh_table_1', 'nci_odwg_table_2'):
            self.assertEqual(self.v1[t]['groups'], self.v2[t]['groups'], t)
        self.assertEqual(self.v2['supersedes']['sha256'],
                         hashlib.sha256((D / 'fda_hepatic_impairment_guidance_2026_draft_v1.json').read_bytes()).hexdigest())

    def test_who_found_each_location(self):
        found = [c['found_by'] for c in self.v2['supersedes']['corrections']]
        self.assertEqual(found.count('owner review'), 3)        # three fields: two quotes and the table
        self.assertEqual(found.count('assistant, by script'), 4)
        self.assertEqual(self.v2['recommendations']['child_pugh']['location'], 'page 4, section IV.A, line 145')
        self.assertEqual(self.v2['recommendations']['cp_groups']['location'], 'page 5, section IV.A.1, lines 164-165')
        self.assertEqual(self.v2['child_pugh_table_1']['location'], 'page 5, Table 1')
        self.assertEqual(self.v2['source']['local_file_sha256'],
                         '414cb3609f8ad887be5a19b352df506b7a56625986b696447f9afc96e7e3298f')


class Kidney(unittest.TestCase):
    def test_v3_changes_only_the_source_record(self):
        v2, v3 = load('fda_renal_impairment_guidance_2024_v2.json'), load('fda_renal_impairment_guidance_2024_v3.json')
        self.assertEqual({k for k in v3 if v3[k] != v2.get(k)}, {'extract_version', 'source', 'supersedes'})
        self.assertIn('and expressed in units of', v3['renal_function_measure']['indexed_egfr']['quote'])
        self.assertIn('estimate of renal function than', v3['renal_function_measure']['cockcroft_gault_weight']['quote'])
        self.assertEqual(v3['source']['local_file_sha256'], v2['supersedes']['source']['sha256'])


class Script(unittest.TestCase):
    def test_rebuilds_both_files_byte_for_byte(self):
        spec = importlib.util.spec_from_file_location('b', ROOT / 'scripts' / 'build_fda_guidance_corrections_2026_11.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        before = {n: (D / n).read_bytes() for n in ('fda_hepatic_impairment_guidance_2026_draft_v2.json',
                                                     'fda_renal_impairment_guidance_2024_v3.json')}
        mod.hepatic(); mod.renal()
        for n, raw in before.items():
            self.assertEqual((D / n).read_bytes(), raw, n)


if __name__ == '__main__':
    unittest.main()
