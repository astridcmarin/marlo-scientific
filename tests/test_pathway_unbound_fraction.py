"""Body map 1.1: the unbound-fraction decision record is pinned, its sources match, and the claim that exposure
does not depend on fu (reading A) holds in the pathway model itself."""
import hashlib
import json
import unittest
from pathlib import Path

from intelligence_store.lenalidomide_renal_pathways import calibrate, load_evidence, pathways

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / 'intelligence_store' / 'data' / 'lenalidomide_pathway_unbound_fraction_assessment_v1.json'
RECORD_SHA256 = '8796799193207c3fffb9001e6a6d1cd6ad45f165c94a5986c944cf47a2faa7df'


def resolve(doc, pointer):
    for token in pointer.strip('/').split('/'):
        doc = doc[int(token)] if isinstance(doc, list) else doc[token]
    return doc


class UnboundFraction(unittest.TestCase):
    def setUp(self):
        raw = RECORD.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), RECORD_SHA256, 'record changed; a change needs a new version')
        self.r = json.loads(raw)
        self.fus = [v['fu'] for v in self.r['values']]

    def test_sources_and_derivations(self):
        docs = {k: json.loads((ROOT / v['file']).read_bytes()) for k, v in self.r['sources'].items()}
        for k, v in self.r['sources'].items():
            self.assertEqual(hashlib.sha256((ROOT / v['file']).read_bytes()).hexdigest(), v['sha256'], k)
        in_vitro, ex_vivo = self.r['values']
        bound = resolve(docs['pathway_evidence'], in_vitro['source']['pointer'])
        self.assertEqual(bound, in_vitro['source']['value'])
        self.assertAlmostEqual(in_vitro['fu'], 1 - bound / 100, places=6)
        self.assertIn('40.2%', resolve(docs['reconciliation'], ex_vivo['source']['pointer']))
        self.assertAlmostEqual(ex_vivo['fu'], 1 - 0.402, places=6)

    def test_exposure_and_urine_fraction_do_not_depend_on_fu(self):
        evidence = load_evidence()
        crcl_cal = self.r['split_at_calibration']['crcl_ml_min']
        cals = [calibrate(evidence, crcl_cal, fu) for fu in self.fus]
        for crcl in (10, 18, 37, 74, 110, 140):
            a, b = (pathways(c, crcl, 'A_intact_nephron') for c in cals)
            self.assertAlmostEqual(a['total_ml_min'], b['total_ml_min'], places=9)
            self.assertAlmostEqual(a['fe'], b['fe'], places=12)
            self.assertNotAlmostEqual(a['filtration_ml_min'], b['filtration_ml_min'], places=3)
            self.assertGreater(b['secretion_ml_min'], 0)

    def test_recorded_split_matches_the_model(self):
        evidence = load_evidence()
        split = self.r['split_at_calibration']
        for fu in self.fus:
            c = calibrate(evidence, split['crcl_ml_min'], fu)
            self.assertAlmostEqual(c['filtration_ml_min'], split[f'fu_{fu}']['filtration_ml_min'], delta=0.06)
            self.assertAlmostEqual(c['secretion_ml_min'], split[f'fu_{fu}']['secretion_ml_min'], delta=0.06)
            self.assertAlmostEqual(c['renal_ml_min'], split['renal_ml_min'], delta=0.06)
        self.assertFalse(self.r['changes_any_calculation'])


if __name__ == '__main__':
    unittest.main()
