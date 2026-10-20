"""Phase 3.1b: pinned pomalidomide label and Li 2017 extracts, and the locked label-consistency plan."""
import hashlib
import json
from pathlib import Path
import unittest

DATA = Path(__file__).resolve().parent.parent / 'intelligence_store' / 'data'
PINS = {
    'label_pk_pomalidomide_v1.json': 'ce4b9afa97e1ba84b9e7cf802c5da80b8927e5db51c8506dddb0c993d6398417',
    'pomalidomide_popk_li_2017_extract_v1.json': '4d9c9d27608f4ae91b5f5ee3dde3ea41019cf7b4d1a4ed918d51970e05e34f1b',
    'label_exposure_consistency_plan_v1.json': '146854b3471dacf4c5c578143ec99dec2e35e55a589961e5773580fc40bceb54',
    'label_pk_melphalan_evomela_v1.json': '0d09f06e1e9d7d9feb887d815074dbd5e1589e449067f32078f1aa8f9dd2d968',
    'label_exposure_consistency_plan_melphalan_v1.json': 'c59e3a523a3211a319388e3a4839f9fce777f6df2d0c8496a16882638f4530f9',
}


def load(name):
    return json.loads((DATA / name).read_text(encoding='utf-8'))


class Pins(unittest.TestCase):
    def test_files_are_unchanged(self):
        for name, pin in PINS.items():
            self.assertEqual(hashlib.sha256((DATA / name).read_bytes()).hexdigest(), pin, name)

    def test_plan_is_locked_and_cites_the_label_extract_pin(self):
        plan = load('label_exposure_consistency_plan_v1.json')
        self.assertEqual(plan['status'], 'locked_before_computation')
        self.assertEqual(plan['inputs']['label_extract']['sha256'], PINS['label_pk_pomalidomide_v1.json'])
        self.assertEqual(plan['parameter_sets']['order_of_preference'], ['A_exposure_derived_mm', 'B_stated_pooled'])
        self.assertEqual(plan['tolerance']['rule'][:60], 'A pass-or-fail check passes if model / label is within 0.67 ')


class LabelExtract(unittest.TestCase):
    def setUp(self):
        self.label = load('label_pk_pomalidomide_v1.json')

    def test_every_value_and_scenario_carries_a_quote(self):
        for group in ('values', 'scenarios'):
            for key, entry in self.label[group].items():
                self.assertTrue(entry.get('quote'), key)
        self.assertIn('860 (37%)', self.label['values']['auc_tau_ss_mm_4mg_ng_h_ml']['quote'])

    def test_pooled_values_are_marked_as_pooled(self):
        for key in ('cl_f_l_h', 'vd_f_l', 'half_life_h_patients'):
            self.assertIn('MM or KS', self.label['values'][key]['population'])
            self.assertIn('MM or KS', self.label['values'][key]['quote'])

    def test_the_mismatch_the_plan_was_written_around(self):
        v = self.label['values']
        cl_from_exposure = 4000 / v['auc_tau_ss_mm_4mg_ng_h_ml']['value']
        self.assertAlmostEqual(cl_from_exposure, 4.651, places=3)
        self.assertLess(cl_from_exposure / v['cl_f_l_h']['range'][0], 0.67)

    def test_scenario_folds_match_their_quotes(self):
        s = self.label['scenarios']
        self.assertIn('38%', s['renal_severe_requiring_dialysis']['quote'])
        self.assertEqual(s['renal_severe_requiring_dialysis']['auc_fold'], 1.38)
        self.assertIn('125%', s['fluvoxamine_strong_cyp1a2_inhibitor']['quote'])
        self.assertEqual(s['fluvoxamine_strong_cyp1a2_inhibitor']['auc_fold'], 2.25)
        self.assertIn('healthy', s['fluvoxamine_strong_cyp1a2_inhibitor']['study_population'])


class MelphalanInputs(unittest.TestCase):
    def test_plan_cites_the_extract_and_every_value_has_a_quote(self):
        plan = load('label_exposure_consistency_plan_melphalan_v1.json')
        self.assertEqual(plan['status'], 'locked_before_computation')
        self.assertEqual(plan['inputs']['label_extract']['sha256'], PINS['label_pk_melphalan_evomela_v1.json'])
        label = load('label_pk_melphalan_evomela_v1.json')
        for group in ('values', 'scenarios'):
            for key, entry in label[group].items():
                self.assertTrue(entry.get('quote'), key)
        self.assertIn('5.8 ± 1.5 mcg/mL and 451', label['values']['cmax_single_100_mg_m2_ug_ml']['quote'])


class LiExtract(unittest.TestCase):
    def test_table3_typical_values(self):
        t3 = load('pomalidomide_popk_li_2017_extract_v1.json')['table3_categorical_renal']
        self.assertEqual((t3['ka_per_h']['estimate'], t3['v_f_l']['estimate'], t3['cl_f_normal_renal_l_h']['estimate'],
                          t3['tlag_h']['estimate']), (0.724, 58.3, 5.13, 0.154))


if __name__ == '__main__':
    unittest.main()
