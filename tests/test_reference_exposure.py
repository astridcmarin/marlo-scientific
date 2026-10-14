"""Patient Lab 2.1e: measured reference exposure and the ratio shown against it."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from intelligence_store.covariate_estimation import CovariateEstimationError
from intelligence_store.reference_exposure import average_daily_dose, compare_to_reference, load_reference_exposure

ROOT = Path(__file__).resolve().parents[1]


class ReferenceExposure(unittest.TestCase):
    def test_reference_matches_the_evidence_file_it_cites(self):
        ref = load_reference_exposure()['reference']
        source = ROOT / ref['source_file']
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), ref['source_file_sha256'])
        evidence = json.loads(source.read_text())
        group = next(g for g in evidence['groups'] if g['group'] == ref['source_group'])
        auc = group['measurements']['auc_infinity']
        self.assertEqual((ref['value'], ref['sd'], ref['n'], ref['dose_mg']),
                         (auc['mean'], auc['sd'], group['n'], evidence['design']['dose_mg']))

    def test_ratio_arithmetic_and_no_band(self):
        result = compare_to_reference(25.0, 1000.0 * 25.0 / 2181)
        self.assertAlmostEqual(result['ratio_to_reference'], 1.0, places=12)
        self.assertAlmostEqual(compare_to_reference(10.0, 5.0)['typical_daily_auc_ng_h_ml'], 2000.0)
        self.assertFalse({'limit', 'target', 'band', 'classification'} & set(result))
        for bad in ((0, 5.0), (10.0, 0), (float('nan'), 5.0)):
            with self.assertRaises(ValueError):
                compare_to_reference(*bad)

    def test_average_daily_dose(self):
        request = {'events': [{'amount': {'value': 5.0}}, {'amount': {'value': 10.0}}]}
        self.assertEqual(average_daily_dose(request), 7.5)

    def test_changed_reference_is_refused(self):
        original = ROOT / 'intelligence_store' / 'data' / 'lenalidomide_reference_exposure_v1.json'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'ref.json'
            path.write_bytes(original.read_bytes() + b' ')
            with self.assertRaises(CovariateEstimationError):
                load_reference_exposure(path)


if __name__ == '__main__':
    unittest.main()
