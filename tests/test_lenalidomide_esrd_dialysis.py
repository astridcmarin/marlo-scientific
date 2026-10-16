"""Simulation 2.0c: end-stage renal disease and haemodialysis against the 2.0a pathway model."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from intelligence_store import lenalidomide_esrd_dialysis as ed
from intelligence_store.lenalidomide_renal_pathways import calibrate, load_evidence


class Pinned(unittest.TestCase):
    def test_plan_and_evidence_pinned(self):
        for path, pin, loader in ((ed.PLAN_PATH, ed.PLAN_SHA256, ed.load_plan), (ed.EVIDENCE_PATH, ed.EVIDENCE_SHA256, ed.load_evidence)):
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), pin)
            with tempfile.TemporaryDirectory() as tmp:
                changed = Path(tmp) / path.name
                changed.write_bytes(path.read_bytes() + b' ')
                with self.assertRaises(ValueError):
                    loader(changed)

    def test_values_match_quoted_rows(self):
        e = ed.load_evidence()
        auc = e['row_quotes']['auc'].split()
        self.assertEqual(int(auc[-4]), e['groups'][0]['auc_ng_h_ml'][0])
        self.assertEqual(int(auc[-2]), e['groups'][1]['auc_ng_h_ml'][0])
        cl = e['row_quotes']['cl'].split()
        self.assertEqual(int(cl[-4]), e['groups'][0]['cl_f_ml_min'][0])
        self.assertEqual(int(cl[-2]), e['groups'][1]['cl_f_ml_min'][0])


class Model(unittest.TestCase):
    def test_zero_residual_leaves_only_non_renal(self):
        cal = calibrate(load_evidence(), 110.0, 0.77)
        p = ed.predicted_auc(cal, 0.0, 25)
        self.assertEqual(p['renal_ml_min'], 0.0)
        self.assertAlmostEqual(p['auc_ng_h_ml'], 25e6 / (cal['non_renal_ml_min'] * 60), places=6)
        with self.assertRaises(ValueError):
            ed.predicted_auc(cal, -1.0, 25)

    def test_dialysis_mass_balance(self):
        d = ed.run_check()['descriptive']['dialysis']
        self.assertAlmostEqual(d['eliminated_by_own_routes_mg'] + d['removed_by_dialysis_mg'], 25.0, places=9)
        self.assertAlmostEqual(d['removed_fraction_of_dose'], 1 - 6830 / 11121, places=9)


class LockedCheck(unittest.TestCase):
    def test_committed_report_reproduces_exactly(self):
        self.assertEqual(ed.run_check(), json.loads(ed.REPORT_PATH.read_text()))

    def test_decision_is_inconclusive_as_recorded(self):
        r = ed.run_check()
        self.assertEqual([s['classification'] for s in r['primary']['scenarios']],
                         ['model_over_predicts', 'consistent', 'consistent'])
        self.assertFalse(r['decision']['constant_non_renal_consistent_at_zero_residual'])
        self.assertFalse(r['decision']['finding_esrd_elimination_exceeds_normal_non_renal'])
        self.assertIs(r['clinical_prediction_validated'], False)


if __name__ == '__main__':
    unittest.main()
