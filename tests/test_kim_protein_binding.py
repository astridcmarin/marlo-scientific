"""Kim 2026 protein binding: the assessment record is pinned and every value it cites matches its source."""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSESSMENT = ROOT / 'intelligence_store' / 'data' / 'kim_protein_binding_assessment_v1.json'
ASSESSMENT_SHA256 = 'be560ba9b8627c78854a5f3e29fa39a4fd59af11e307a114b160e83c151c7c19'


def resolve(document, pointer):
    node = document
    for token in pointer.strip('/').split('/'):
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


class KimProteinBinding(unittest.TestCase):
    def setUp(self):
        raw = ASSESSMENT.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), ASSESSMENT_SHA256, 'assessment changed without a new version')
        self.a = json.loads(raw)

    def test_cited_values_match_their_pinned_sources(self):
        docs = {}
        for ref, src in self.a['sources'].items():
            raw = (ROOT / src['file']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), src['sha256'], src['file'])
            docs[ref] = json.loads(raw)
        for v in self.a['values']:
            self.assertEqual(resolve(docs[v['source']['ref']], v['source']['pointer']), v['value'], v['id'])

    def test_model_still_uses_the_assessed_value_and_nothing_changes(self):
        from intelligence_store.kim_model import load_extract
        self.assertEqual(load_extract()['parameters']['fraction_unbound']['value'], 0.614)
        self.assertEqual(self.a['status'], 'assessed_no_change')
        self.assertFalse(self.a['changes_any_calculation'])
        self.assertFalse(self.a['clinical_prediction_validated'])

    def test_hypoalbuminaemia_limit_is_enforced_by_the_kim_scope(self):
        from intelligence_store.lenalidomide_scope import load_kim_scope
        albumin = next(r for r in load_kim_scope()['state_rules'] if r['id'] == 'albumin')
        self.assertEqual((albumin['range'][0], albumin['unit'], albumin.get('optional')), (30, 'g/L', True))


if __name__ == '__main__':
    unittest.main()
