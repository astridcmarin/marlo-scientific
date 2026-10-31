"""Phase 4.3: lenalidomide dose-optimisation view."""
import json
import math
import unittest

from intelligence_store import dose_optimisation as do
from intelligence_store.patient_state import example_state


def state(scr=80.0, sex='FEMALE', age=65.0, weight=70.0, height=165.0):
    s = example_state()
    for name in s['fields']:
        s['fields'][name].update(value=None, origin='unknown')
    for field, value, unit in (('age_years', age, 'year'), ('weight', weight, 'kg'), ('height', height, 'cm'),
                               ('serum_creatinine', scr, 'umol/L')):
        if value is not None:
            s['fields'][field].update(value=float(value), unit=unit, origin='synthetic_input')
    if sex:
        s['fields']['biological_sex'].update(value=sex, origin='synthetic_input')
    return s


class DoseView(unittest.TestCase):
    def test_dose_levels_come_from_the_models(self):
        self.assertEqual(do.dose_levels(), [2.5, 5.0, 7.5, 10.0, 15.0, 20.0, 25.0])
        self.assertEqual(do.dose_status('lenalidomide_kim_2026', 15.0), 'not_a_study_dose')
        self.assertEqual(do.dose_status('lenalidomide_hughes_2019', 10.0), 'inside_range_not_listed')
        self.assertEqual(do.dose_status('lenalidomide_hughes_2019', 100.0), 'not_a_study_dose')

    def test_aliases_match_the_catalog(self):
        from intelligence_store.drug_aliases import load_alias_catalog
        entry = next(e for e in load_alias_catalog()['entries'] if e['id'] == 'lenalidomide')
        self.assertEqual(tuple(entry['aliases']), do.ALIASES)

    def test_cells_reproduce_from_the_pinned_sources(self):
        from intelligence_store.kim_model import compare_typical_exposure
        from intelligence_store.lenalidomide_relative_odds import load_evidence
        s = state()
        r = do.lenalidomide_dose_view(s, 'MM')
        self.assertFalse(r['clinical_prediction_validated'])
        ref = r['reference']['auc_ng_h_ml']
        cmp = compare_typical_exposure(s, 25.0)['models']
        ev = load_evidence()['odds_ratios_multiple_myeloma']
        for col in r['models']:
            self.assertTrue(col['computed'])
            cl = cmp[col['model']]['typical_total_cl_f_l_h']
            self.assertAlmostEqual(col['typical_total_cl_f_l_h'], cl, places=10)
            for cell in col['cells']:
                if cell['dose_status'] == 'not_a_study_dose':
                    self.assertNotIn('ratio_to_reference', cell)
                    continue
                ratio = 1000.0 * cell['dose_mg'] / cl / ref
                self.assertAlmostEqual(cell['ratio_to_reference'], ratio, places=12)
                for ep, o in cell['relative_odds'].items():
                    self.assertAlmostEqual(o['relative_odds'], ratio ** math.log(ev[ep]['odds_ratio_per_unit_ln_auc']), places=12)
        kim = next(c for c in r['models'] if c['model'] == 'lenalidomide_kim_2026')
        self.assertEqual([c['dose_mg'] for c in kim['cells'] if c['dose_status'] == 'study_dose'], [5.0, 7.5, 10.0])

    def test_no_value_outside_scope(self):
        r = do.lenalidomide_dose_view(state(scr=200.0, sex='MALE', age=70.0, weight=80.0, height=175.0), 'MM')
        hughes = r['models'][0]
        self.assertEqual(hughes['scope']['status'], 'out_of_scope')
        self.assertFalse(hughes['computed'])
        self.assertEqual(hughes['cells'], [])
        unknown = do.lenalidomide_dose_view(state(), 'UNKNOWN')
        self.assertFalse(any(c['computed'] for c in unknown['models']))
        missing = do.lenalidomide_dose_view(state(scr=None), 'MM')
        self.assertFalse(any(c['computed'] for c in missing['models']))

    def test_flag_carries_observed_data(self):
        r = do.lenalidomide_dose_view(state(scr=130.0, sex='MALE', age=70.0, weight=80.0, height=175.0), 'MM')
        hughes = r['models'][0]
        self.assertTrue(hughes['computed'])
        self.assertEqual(hughes['tier'], 'external_check_disagrees')
        self.assertEqual(hughes['scope']['observed'][0]['groups'][0]['group'], 'moderate')

    def test_trials(self):
        t = do.corpus_trials()
        self.assertEqual((t['matched'], t['mention_only_not_matched']), (380, 78))
        self.assertEqual(sum(n for _, n in t['by_phase']), 380)
        self.assertTrue(all({'PHASE1', 'EARLY_PHASE1'} & set(x['phases']) for x in t['phase_1_trials']))

    def test_gaps_and_no_ranking(self):
        r = do.lenalidomide_dose_view(state(), 'MM')
        self.assertEqual({g['id'] for g in r['gaps']},
                         {'exposure_efficacy', 'label_dose_reductions', 'combination_regimens', 'trial_dose_levels'})
        text = json.dumps(r).lower()
        for word in ('recommended dose', 'optimal dose', 'best dose'):
            self.assertNotIn(word, text)


class Page(unittest.TestCase):
    def setUp(self):
        from app.app import app
        self.client = app.test_client()

    def test_page(self):
        url = '/landscape/drugs/lenalidomide/dose-optimisation'
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Not dosing guidance', r.data)
        self.assertIn(b'not a study dose', r.data)
        j = self.client.get(url + '?format=json')
        self.assertEqual(json.loads(j.data)['schema_version'], do.SCHEMA_VERSION)
        self.assertIn(b'outside the model', self.client.get(url + '?disease=MM&sex=MALE&age=70&weight=80&height=175&scr=200').data)
        flagged = self.client.get(url + '?disease=MM&sex=MALE&age=70&weight=80&height=175&scr=130').get_data(as_text=True)
        self.assertIn('Hughes 2019 is flagged for this record', flagged)
        self.assertIn('under-predicted exposure about 2.1-fold', flagged)
        for bad in ('?x=1', '?scr=abc', '?sex=X', '?disease=Y', '?scr=-1', '?scr=1&scr=2'):
            self.assertEqual(self.client.get(url + bad).status_code, 400, bad)
        self.assertIn(url.encode(), self.client.get('/landscape/drugs/lenalidomide/special-populations').data)


if __name__ == '__main__':
    unittest.main()
