"""Lenalidomide renal source reconciliation: every number recomputes from pinned sources."""
import json
import math
import unittest
from pathlib import Path

from intelligence_store.lenalidomide_label import load_label_extract, load_renal_reconciliation

ROOT = Path(__file__).resolve().parent.parent


class Reconciliation(unittest.TestCase):
    def setUp(self):
        self.r = {i['id']: i for i in load_renal_reconciliation()['items']}

    def test_group_totals_and_label_results_match_ema_table(self):
        label = load_label_extract()['pharmacokinetics']['renal_study']
        self.assertEqual(sum(label['groups_n'].values()), 30)
        ema = json.loads((ROOT / 'landscape_ui/data/renal_pk/renal_pk_group_evidence_v1.json').read_text())
        self.assertEqual(ema['design']['total_study_subjects'], 30)
        self.assertEqual([g['n'] for g in ema['groups']], [7, 5, 6, 6])
        # CL/F and half-life means from EMA Table 4 (PDF page 21); the extract pins the half-lives.
        cl = {'normal': 207, 'moderate': 71, 'severe': 52, 'esrd_off_dialysis': 39}
        comp = self.r['renal_study_group_sizes']['computation']
        for g in ('moderate', 'severe', 'esrd_off_dialysis'):
            self.assertAlmostEqual(comp['cl_decrease_percent'][g], round(100 * (1 - cl[g] / cl['normal']), 1))
        t = {g['group']: g['measurements']['terminal_half_life']['mean'] for g in ema['groups']}
        self.assertAlmostEqual(comp['half_life_fold']['moderate'], round(t['moderate'] / t['normal'], 2))
        lo, hi = label['clearance_decrease_percent_moderate_severe']
        self.assertEqual((lo, hi), (round(comp['cl_decrease_percent']['moderate']), round(comp['cl_decrease_percent']['severe'])))

    def test_v2_adds_the_study_abstract(self):
        from intelligence_store.lenalidomide_label import RECONCILIATION_V1_SHA256, load_renal_reconciliation
        import hashlib
        r = load_renal_reconciliation()
        v2 = json.loads((ROOT / 'intelligence_store/data/lenalidomide_renal_source_reconciliation_v2.json').read_text())
        self.assertEqual(v2['supersedes']['sha256'], RECONCILIATION_V1_SHA256)
        v1 = ROOT / 'intelligence_store/data/lenalidomide_renal_source_reconciliation_v1.json'
        self.assertEqual(hashlib.sha256(v1.read_bytes()).hexdigest(), RECONCILIATION_V1_SHA256)
        self.assertIn('N = 7', r['sources']['study_abstract']['quotes']['stratification'])
        self.assertIn('CLCr < 50 mL/min', r['sources']['study_abstract']['quotes']['conclusion'])
        ema = json.loads((ROOT / 'landscape_ui/data/renal_pk/renal_pk_group_evidence_v1.json').read_text())
        auc = {g['group']: g['measurements']['auc_infinity']['mean'] for g in ema['groups']}
        n = {g['group']: g['n'] for g in ema['groups']}
        pooled = (n['normal'] * auc['normal'] + n['mild'] * auc['mild']) / (n['normal'] + n['mild'])
        comp = self.r['renal_study_group_sizes']['computation']['auc_increase_vs_pooled_normal_mild_percent']
        for g, key in (('moderate', 'moderate'), ('severe', 'severe_without_dialysis')):
            self.assertEqual(comp[g], round(100 * (auc[key] / pooled - 1)))
        self.assertEqual(round(auc['mild'] / auc['normal'], 2), self.r['mild_versus_normal_auc']['computation']['mild_to_normal_arithmetic_mean_ratio'])
        self.assertEqual(self.r['dose_threshold_50_or_60']['status'], 'change_dated_between_2015_and_2017_reason_not_established')

    def test_v3_adds_earlier_labels(self):
        import hashlib
        from intelligence_store.lenalidomide_label import RECONCILIATION_V2_SHA256
        r = load_renal_reconciliation()
        v2 = ROOT / 'intelligence_store/data/lenalidomide_renal_source_reconciliation_v2.json'
        self.assertEqual(hashlib.sha256(v2.read_bytes()).hexdigest(), RECONCILIATION_V2_SHA256)
        self.assertEqual(r['supersedes']['sha256'], RECONCILIATION_V2_SHA256)
        self.assertEqual(r['sources']['label_2015']['quotes']['mm_moderate_range']['quote'], 'CLcr 30-50 mL/min')
        self.assertIn('non-malignant', r['sources']['label_2015']['quotes']['basis']['quote'])
        self.assertIn('30 to 60', r['sources']['label_2017']['quotes']['table']['quote'])
        self.assertEqual(self.r['renal_study_population']['status'], 'established_from_label')

    def test_ema_page_states_measured_clearance(self):
        try:
            from pypdf import PdfReader
        except ImportError:
            self.skipTest('pypdf not installed')
        text = PdfReader(str(ROOT / 'landscape_ui/data/renal_pk/ema_lenalidomide_2008.pdf')).pages[19].extract_text()
        self.assertIn('Measured creatinine clearance', ' '.join(text.split()))

    def test_post_hoc_bounds_follow_the_model_equations(self):
        hughes = json.loads((ROOT / 'intelligence_store/data/hughes_parameter_extract_v1.json').read_text())
        kim = json.loads((ROOT / 'intelligence_store/data/kim_2026_model_extract_v1.json').read_text())
        exp_h = hughes['parameters']['crcl_exponent']['value']
        self.assertAlmostEqual((25 / 40) ** exp_h, 0.90, places=2)
        b = kim['parameters']['cl_egfr_coefficient']['value']
        self.assertEqual([round(math.exp(b * d), 2) for d in (5, 10, 15)], [1.07, 1.14, 1.22])
        self.assertEqual(self.r['creatinine_clearance_method_in_checks']['post_hoc_bound']['status'], 'post_hoc_not_a_rerun')


if __name__ == '__main__':
    unittest.main()
