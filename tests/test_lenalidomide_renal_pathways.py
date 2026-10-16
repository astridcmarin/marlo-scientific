"""Simulation 2.0a: lenalidomide clearance split into filtration, secretion and non-renal pathways."""
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest

from intelligence_store import lenalidomide_renal_pathways as rp


class Pinned(unittest.TestCase):
    def test_plan_and_evidence_pinned(self):
        for path, pin, loader in ((rp.PLAN_PATH, rp.PLAN_SHA256, rp.load_plan),
                                  (rp.EVIDENCE_PATH, rp.EVIDENCE_SHA256, rp.load_evidence)):
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), pin)
            with tempfile.TemporaryDirectory() as tmp:
                changed = Path(tmp) / path.name
                changed.write_bytes(path.read_bytes() + b' ')
                with self.assertRaises(ValueError):
                    loader(changed)
        self.assertEqual(rp.load_plan()['status'], 'locked_before_computation')

    def test_group_values_match_the_quoted_table_and_text(self):
        e = rp.load_evidence()
        cl = [int(x) for x in re.findall(r'(\d+) \(\d+\)', e['group_quotes']['cl_f_row'])[:4]]
        auc = [int(x) for x in re.findall(r'(\d+) \(\d+\)', e['group_quotes']['auc_row'])[:4]]
        fe = [int(x) for x in re.findall(r'\((\d+)%\)', e['group_quotes']['fe'])]
        self.assertEqual([g['cl_f_ml_min'][0] for g in e['groups']], cl)
        self.assertEqual([g['auc_ng_h_ml'][0] for g in e['groups']], auc)
        self.assertEqual([g['fe_percent'] for g in e['groups']], fe)

    def test_evidence_source_pdf_unchanged(self):
        e = rp.load_evidence()
        pdf = Path(rp.__file__).resolve().parents[1] / e['source']['local_file']
        self.assertEqual(hashlib.sha256(pdf.read_bytes()).hexdigest(), e['source']['sha256'])


class Model(unittest.TestCase):
    def setUp(self):
        self.cal = rp.calibrate(rp.load_evidence(), 110.0, 0.77)

    def test_calibration_arithmetic(self):
        self.assertAlmostEqual(self.cal['total_ml_min'], 25e6 / 2181 / 60, places=9)
        self.assertAlmostEqual(self.cal['renal_ml_min'], 0.85 * self.cal['total_ml_min'], places=9)
        self.assertAlmostEqual(self.cal['filtration_ml_min'] + self.cal['secretion_ml_min'], self.cal['renal_ml_min'], places=9)
        self.assertGreater(self.cal['secretion_ml_min'], 0)

    def test_both_readings_reproduce_the_calibration_group(self):
        for reading in rp.READINGS:
            p = rp.pathways(self.cal, 110.0, reading)
            self.assertAlmostEqual(p['total_ml_min'], self.cal['total_ml_min'], places=9)
            self.assertAlmostEqual(p['fe'], 0.85, places=9)

    def test_reading_behaviour(self):
        a = rp.pathways(self.cal, 55.0, 'A_intact_nephron')
        b = rp.pathways(self.cal, 55.0, 'B_secretion_preserved')
        self.assertAlmostEqual(a['renal_ml_min'], self.cal['renal_ml_min'] / 2, places=9)
        self.assertAlmostEqual(b['secretion_ml_min'], self.cal['secretion_ml_min'], places=9)
        self.assertEqual(a['non_renal_ml_min'], b['non_renal_ml_min'])
        with self.assertRaises(ValueError):
            rp.pathways(self.cal, 0.0, 'A_intact_nephron')


class LockedCheck(unittest.TestCase):
    def test_committed_report_reproduces_exactly(self):
        self.assertEqual(rp.run_check(), json.loads(rp.REPORT_PATH.read_text()))

    def test_decision(self):
        r = rp.run_check()
        self.assertEqual(r['decision']['supported_readings_primary'], [])
        self.assertTrue(r['decision']['finding_renal_elimination_falls_faster_than_proportional'])
        for scenario in r['scenarios']:
            for g in scenario['groups']:
                if g['group'] != 'mild':
                    self.assertEqual(g['readings']['B_secretion_preserved']['classification'], 'model_under_predicts')
        self.assertIs(r['clinical_prediction_validated'], False)


if __name__ == '__main__':
    unittest.main()
