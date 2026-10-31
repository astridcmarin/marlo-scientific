"""EMA 2013 re-analysis of CC-5013-PK-001 (variation II/0056): pinned extract and internal-consistency checks.

The tables are images in the source, so they were transcribed by eye; these checks catch transcription slips
by testing relations the published numbers must satisfy, and agreement with the pinned EMA 2008 extract.
"""
import hashlib
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTRACT = ROOT / 'intelligence_store' / 'data' / 'lenalidomide_renal_pk_ema_2013_v1.json'
EXTRACT_SHA256 = '04f2e629ded43713062e0d68d668939a4a2cecd5a9db7ce349874e81529f6501'
EMA_2008 = ROOT / 'landscape_ui' / 'data' / 'renal_pk' / 'renal_pk_group_evidence_v2.json'
GROUPS = ('normal', 'mild', 'moderate', 'severe')


class EmaRenal2013(unittest.TestCase):
    def setUp(self):
        raw = EXTRACT.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), EXTRACT_SHA256, 'extract changed; a change needs a new version')
        self.d = json.loads(raw)
        self.t3 = self.d['table_3_geometric_means']

    def test_cl_f_equals_dose_over_auc(self):
        # CL/F (mL/min) = 25 mg / AUCinf (ng*h/mL), for every group including both ESRD days
        for g, cell in self.t3['auc_infinity'].items():
            if g == 'unit':
                continue
            expected = 25e6 / cell['geometric_mean'] / 60
            self.assertAlmostEqual(self.t3['cl_f'][g]['geometric_mean'], expected, delta=1.0, msg=g)

    def test_auc_cv_matches_cl_cv(self):
        # CL/F is dose / AUC, so its geometric CV equals AUCinf's
        for g in GROUPS + ('esrd_off_dialysis', 'esrd_on_dialysis'):
            self.assertEqual(self.t3['cl_f'][g]['cv_pct'], self.t3['auc_infinity'][g]['cv_pct'], g)

    def test_geometric_mean_ratios_follow_from_table_3(self):
        n = {g: self.d['groups'][g]['n'] for g in self.d['groups']}
        gm = {g: self.t3['auc_infinity'][g]['geometric_mean'] for g in n}
        ref = math.exp((n['normal'] * math.log(gm['normal']) + n['mild'] * math.log(gm['mild'])) / (n['normal'] + n['mild']))
        for g, key in (('moderate', 'moderate'), ('severe', 'severe'), ('esrd_off_dialysis', 'esrd_off_dialysis')):
            point, lo, hi = self.d['table_4_geometric_mean_ratios']['auc_infinity'][key]
            self.assertLess(lo, point)
            self.assertLess(point, hi)
            self.assertAlmostEqual(100 * gm[g] / ref, point, delta=0.02 * point, msg=g)

    def test_same_subjects_as_the_2008_extract(self):
        ema = {g['group']: g for g in json.loads(EMA_2008.read_text())['groups']}
        names = {'normal': 'normal', 'mild': 'mild', 'moderate': 'moderate', 'severe': 'severe_without_dialysis'}
        for g, name in names.items():
            self.assertEqual(self.d['groups'][g]['n'], ema[name]['n'], g)
            arithmetic = ema[name]['measurements']['auc_infinity']['mean']
            geo = self.t3['auc_infinity'][g]['geometric_mean']
            cv = self.t3['auc_infinity'][g]['cv_pct'] / 100
            self.assertLessEqual(geo, arithmetic, g)                       # a geometric mean never exceeds the arithmetic mean
            self.assertAlmostEqual(geo * math.sqrt(1 + cv ** 2), arithmetic, delta=0.05 * arithmetic, msg=g)   # log-normal link

    def test_enantiomer_fractions_add_up(self):
        for metric in ('auc_infinity', 'auc_t'):
            for g, r in self.d['table_5_enantiomers'][metric].items():
                self.assertAlmostEqual(r['S/T'][0] + r['R/T'][0], 1.0, delta=0.025, msg=(metric, g))   # printed values sum to 0.99-1.02 (rounding; ESRD on dialysis AUCt 0.60 + 0.42)
                self.assertAlmostEqual(r['S/T'][0] / r['R/T'][0], r['S/R'][0], delta=0.06, msg=(metric, g))

    def test_flags_and_simulation_label(self):
        self.assertFalse(self.d['clinical_prediction_validated'])
        self.assertEqual(self.d['sponsor_simulation_table_7']['kind'], 'model_predictions_not_observations')


if __name__ == '__main__':
    unittest.main()
