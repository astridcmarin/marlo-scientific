"""Phase 2.5b: Hughes 2019 and Kim 2026 model scopes."""
import hashlib
import unittest
from pathlib import Path

from intelligence_store import lenalidomide_scope as L
from intelligence_store import model_scope as ms
from intelligence_store.covariate_estimation import primary_weight_basis_hughes
from intelligence_store.patient_state import example_state

ROOT = Path(__file__).resolve().parent.parent
BASIS = primary_weight_basis_hughes()


def state(scr=80.0, **values):
    s = example_state()
    s['fields']['serum_creatinine'].update(value=scr, origin='unknown' if scr is None else 'synthetic_input')
    for name, value in values.items():
        s['fields'][name].update(value=value, origin='unknown' if value is None else 'synthetic_input')
    return s


def rule(result, rid):
    return next(r for r in result['scope_evaluation']['rules'] if r['id'] == rid)


class Files(unittest.TestCase):
    def test_pinned_and_evidence_matches(self):
        for scope in (L.load_hughes_scope(), L.load_kim_scope()):
            for ref in scope['evidence'].values():
                self.assertEqual(hashlib.sha256((ROOT / ref['file']).read_bytes()).hexdigest(), ref['sha256'], ref['file'])
            self.assertFalse(scope['clinical_prediction_validated'])

    def test_bands_follow_the_locked_primary_results(self):
        import json
        hughes = json.loads((ROOT / 'docs/verification/hughes_renal_group_check_v1.json').read_text())
        kim = json.loads((ROOT / 'docs/verification/kim_renal_group_check_v1.json').read_text())
        self.assertEqual(hughes['primary_endpoint_by_group'], {'mild': 'consistent', 'moderate': 'model_under_predicts', 'severe': 'model_under_predicts'})
        self.assertEqual(kim['classification_across_scenarios']['mild'], ['consistent'])
        self.assertEqual(kim['primary_endpoint_by_group']['severe'], 'model_under_predicts')
        self.assertGreater(len(kim['classification_across_scenarios']['moderate']), 1)      # v1: not robust
        recheck = json.loads((ROOT / 'docs/verification/lenalidomide_renal_recheck_v1.json').read_text())
        self.assertEqual(recheck['result_by_model']['lenalidomide_kim_2026']['across_scenarios']['moderate'], ['model_under_predicts'])
        bands = [(b['range'], b['tier']) for b in L.load_kim_scope()['state_rules'][0]['tier_by_band']]
        self.assertEqual(bands, [([50, 94.7], 'externally_checked'), ([30, 50], 'external_check_disagrees'),
                                 ([11.1, 30], 'external_check_disagrees')])

    def test_superseded_scopes_kept_unchanged(self):
        for name, sha in L.SUPERSEDED_SCOPES.items():
            self.assertEqual(hashlib.sha256((L.DATA / name).read_bytes()).hexdigest(), sha, name)
        self.assertEqual(L.load_kim_scope()['supersedes']['sha256'], L.SUPERSEDED_SCOPES['lenalidomide_kim_scope_v2.json'])
        self.assertEqual(L.load_hughes_scope()['supersedes']['sha256'], L.SUPERSEDED_SCOPES['lenalidomide_hughes_scope_v1.json'])

    def test_only_population_wording_and_evidence_changed(self):
        import json
        pairs = (('lenalidomide_hughes_scope_v1.json', L.load_hughes_scope()), ('lenalidomide_kim_scope_v2.json', L.load_kim_scope()))
        for name, current in pairs:
            old = json.loads((L.DATA / name).read_text())
            self.assertEqual(current['state_rules'], old['state_rules'], name)
            self.assertEqual(current['outputs'], old['outputs'], name)
            self.assertEqual(current['request_rules'][0]['in_scope'], old['request_rules'][0]['in_scope'], name)
            self.assertNotIn('not established', current['request_rules'][0]['basis'])
            self.assertIn('non-malignant', current['request_rules'][0]['basis'])
            self.assertEqual(current['evidence']['observed']['file'], 'landscape_ui/data/renal_pk/renal_pk_group_evidence_v2.json')

    def test_observed_data_names_the_study_population(self):
        r = L.hughes_scope(state(115.0), BASIS, 'MM')
        self.assertIn('non-malignant', r['observed'][0]['population'])


class Hughes(unittest.TestCase):
    def test_normal_kidney_function_checked(self):
        r = L.hughes_scope(state(80.0), BASIS, 'MM')
        self.assertEqual(r['scope_evaluation']['status'], 'in_scope')
        self.assertEqual(rule(r, 'creatinine_clearance')['tier'], 'externally_checked')
        self.assertEqual(r['observed'], [])

    def test_moderate_band_is_computed_but_flagged_with_observed(self):
        r = L.hughes_scope(state(115.0), BASIS, 'MM')
        crcl = rule(r, 'creatinine_clearance')
        self.assertTrue(36 <= crcl['value'] < 50, crcl['value'])
        self.assertEqual(r['scope_evaluation']['status'], 'in_scope')
        self.assertEqual(r['scope_evaluation']['flags'], ['creatinine_clearance'])
        self.assertEqual(r['scope_evaluation']['weakest_rule_tier'], 'external_check_disagrees')
        self.assertEqual(r['observed'][0]['groups'][0]['group'], 'moderate')
        self.assertAlmostEqual(r['observed'][0]['groups'][0]['ratio_to_reference_mean'], 6021 / 2181)

    def test_beyond_model_data_is_refused_with_observed(self):
        r = L.hughes_scope(state(300.0), BASIS, 'MM')
        self.assertEqual(r['scope_evaluation']['status'], 'out_of_scope')
        self.assertEqual([g['group'] for g in r['observed'][0]['groups']], ['moderate', 'severe_without_dialysis'])
        r = L.hughes_scope(state(80.0, age_years=85.0), BASIS, 'MM')
        self.assertEqual(rule(r, 'age')['status'], 'out_of_scope')

    def test_disease_and_unknowns(self):
        self.assertEqual(L.hughes_scope(state(), BASIS, 'CLL')['scope_evaluation']['status'], 'in_scope')
        self.assertEqual(L.hughes_scope(state(), BASIS, 'OTHER')['scope_evaluation']['status'], 'out_of_scope')
        self.assertEqual(L.hughes_scope(state(), BASIS, 'UNKNOWN')['scope_evaluation']['status'], 'cannot_determine')
        self.assertEqual(L.hughes_scope(state(None), BASIS, 'MM')['scope_evaluation']['status'], 'cannot_determine')


class Kim(unittest.TestCase):
    def test_bands(self):
        self.assertEqual(rule(L.kim_scope(state(80.0), 'MM'), 'egfr')['tier'], 'externally_checked')
        moderate = L.kim_scope(state(150.0), 'MM')
        egfr = rule(moderate, 'egfr')
        self.assertTrue(30 <= egfr['value'] <= 50, egfr['value'])
        self.assertEqual(moderate['scope_evaluation']['status'], 'in_scope')     # computed, flagged (31 October)
        self.assertEqual(egfr['tier'], 'external_check_disagrees')
        self.assertEqual(moderate['scope_evaluation']['flags'], ['egfr'])
        self.assertEqual(moderate['observed'][0]['groups'][0]['group'], 'moderate')
        severe = L.kim_scope(state(300.0), 'MM')
        self.assertEqual(severe['scope_evaluation']['status'], 'in_scope')        # computed (14 October decision kept)
        self.assertEqual(rule(severe, 'egfr')['tier'], 'external_check_disagrees')
        self.assertEqual(severe['observed'][0]['groups'][0]['group'], 'severe_without_dialysis')

    def test_beyond_kim_data_is_refused(self):
        self.assertEqual(L.kim_scope(state(500.0), 'MM')['scope_evaluation']['status'], 'out_of_scope')
        high = L.kim_scope(state(50.0), 'MM')                                   # eGFR above 94.7
        self.assertEqual(rule(high, 'egfr')['side'], 'above')
        self.assertEqual(L.kim_scope(state(80.0), 'CLL')['scope_evaluation']['status'], 'out_of_scope')

    def test_albumin_is_optional(self):
        self.assertEqual(rule(L.kim_scope(state(80.0), 'MM'), 'albumin')['status'], 'not_assessed')
        self.assertEqual(rule(L.kim_scope(state(80.0, albumin=25.0), 'MM'), 'albumin')['status'], 'out_of_scope')


if __name__ == '__main__':
    unittest.main()
