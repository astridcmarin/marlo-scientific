"""Phase 2.5: enforceable model scope, piloted with ixazomib (Gupta 2017)."""
import copy
import hashlib
import json
import math
import unittest
from pathlib import Path

from intelligence_store import ixazomib_exposure as x
from intelligence_store import ixazomib_pk_gupta as model
from intelligence_store import model_scope as ms
from intelligence_store.patient_state import example_state

ROOT = Path(__file__).resolve().parent.parent
REQUEST = {'disease_code': 'MM', 'route': 'oral', 'dose_mg': 3.0, 'bilirubin_uln_umol_l': 21.0}


def state(**values):
    s = example_state()
    defaults = {'creatinine_clearance': 95.0, 'total_bilirubin': 8.0}
    defaults.update(values)
    for name, value in defaults.items():
        s['fields'][name].update(value=value, origin='unknown' if value is None else 'synthetic_input')
    return s


class Scope(unittest.TestCase):
    def test_pinned_and_evidence_checksums_match(self):
        scope = x.load_ixazomib_scope()
        for ref in scope['evidence'].values():
            self.assertEqual(hashlib.sha256((ROOT / ref['file']).read_bytes()).hexdigest(), ref['sha256'], ref['file'])
        with self.assertRaises(ms.ScopeError):
            ms.load_scope(x.SCOPE_PATH, '0' * 64)

    def test_every_rule_cites_a_basis_or_tier(self):
        scope = x.load_ixazomib_scope()
        for rule in scope['request_rules'] + scope['state_rules']:
            self.assertTrue(rule.get('tier') or rule.get('tier_by_band'), rule['id'])
            self.assertTrue(rule.get('outside_reason'), rule['id'])
        self.assertIn('cmax', [o['id'] for o in scope['outputs']['not_supported']])

    def test_bsa_du_bois(self):
        self.assertAlmostEqual(ms.bsa_du_bois(70, 165), 1.7710, places=3)


class Evaluate(unittest.TestCase):
    def setUp(self):
        self.scope = x.load_ixazomib_scope()

    def rule(self, result, rid):
        return next(r for r in result['rules'] if r['id'] == rid)

    def test_in_scope_and_weakest_tier(self):
        r = ms.evaluate(self.scope, state(), REQUEST)
        self.assertEqual(r['status'], 'in_scope')
        self.assertEqual(self.rule(r, 'creatinine_clearance')['tier'], 'externally_checked')
        self.assertEqual(r['weakest_rule_tier'], 'inside_model_data')          # bilirubin, BSA and age rules
        r = ms.evaluate(self.scope, state(creatinine_clearance=60.0), REQUEST)
        self.assertEqual(self.rule(r, 'creatinine_clearance')['tier'], 'inside_model_data')

    def test_out_of_scope_reasons(self):
        r = ms.evaluate(self.scope, state(creatinine_clearance=25.0), REQUEST)
        self.assertEqual(r['status'], 'out_of_scope')
        self.assertEqual(self.rule(r, 'creatinine_clearance')['side'], 'below')
        self.assertIn('observed', self.rule(r, 'creatinine_clearance'))
        r = ms.evaluate(self.scope, state(total_bilirubin=40.0), REQUEST)          # 1.9 x ULN: moderate
        self.assertEqual(self.rule(r, 'total_bilirubin_ratio')['status'], 'out_of_scope')
        r = ms.evaluate(self.scope, state(), dict(REQUEST, disease_code='SOLID_TUMOUR'))
        self.assertIn('1.4-fold', self.rule(r, 'disease')['reason'])
        r = ms.evaluate(self.scope, state(), dict(REQUEST, dose_mg=8.0))
        self.assertEqual(self.rule(r, 'dose')['status'], 'out_of_scope')
        self.assertNotIn('outputs_supported', r)

    def test_unknown_stays_unknown(self):
        r = ms.evaluate(self.scope, state(total_bilirubin=None), REQUEST)
        self.assertEqual(r['status'], 'cannot_determine')
        r = ms.evaluate(self.scope, state(), {k: v for k, v in REQUEST.items() if k != 'bilirubin_uln_umol_l'})
        self.assertEqual(r['status'], 'cannot_determine')
        r = ms.evaluate(self.scope, state(), dict(REQUEST, disease_code='UNKNOWN'))
        self.assertEqual(r['status'], 'cannot_determine')
        # out of scope wins over unknown
        r = ms.evaluate(self.scope, state(creatinine_clearance=10.0, total_bilirubin=None), REQUEST)
        self.assertEqual(r['status'], 'out_of_scope')

    def test_no_silent_unit_conversion(self):
        s = state()
        s['fields']['creatinine_clearance']['unit'] = 'mL/s'
        with self.assertRaises(ms.ScopeError):
            ms.evaluate(self.scope, s, REQUEST)

    def test_bad_reference_value(self):
        with self.assertRaises(ms.ScopeError):
            ms.evaluate(self.scope, state(), dict(REQUEST, bilirubin_uln_umol_l=0))


class Exposure(unittest.TestCase):
    def test_in_scope_outputs_match_the_model_and_the_check(self):
        r = x.ixazomib_exposure(state(), REQUEST)
        out = r['model_outputs']
        p = model.typical_parameters(model.load_extract(), out['bsa_m2_du_bois'])
        self.assertAlmostEqual(out['typical_total_auc_tau_steady_state']['value'], 0.58 * 3000 / 1.86)
        self.assertAlmostEqual(model.auc_to(1e6, 3.0, p), model.auc_infinity(3.0, p), places=6)
        # AUC0-336 at the reference BSA equals the locked check's typical-patient value (its LLOQ-truncated
        # trapezoid differs slightly from the exact integral).
        ref = json.loads((ROOT / 'docs/verification/ixazomib_pk_gupta_check_v1.json').read_text())
        typical = ref['descriptive']['typical_patient_3_mg']['auc_last_ng_h_ml']
        exact = model.auc_to(336.0, 3.0, model.typical_parameters(model.load_extract()))
        self.assertLess(abs(exact / typical - 1), 0.02)
        self.assertEqual(r['observed_instead'], [])

    def test_never_outputs_peaks_or_curves(self):
        text = json.dumps(x.ixazomib_exposure(state(), REQUEST)['model_outputs'])
        self.assertNotIn('cmax', text.lower())
        self.assertNotIn('concentration', text.lower())

    def test_out_of_scope_shows_observed_groups_not_model_values(self):
        r = x.ixazomib_exposure(state(creatinine_clearance=20.0), REQUEST)
        self.assertIsNone(r['model_outputs'])
        obs = r['observed_instead'][0]
        self.assertEqual([g['group'] for g in obs['groups']], ['severe_ri', 'esrd'])
        self.assertAlmostEqual(obs['groups'][0]['ratio_to_reference_dose_normalised'], 813 / 575)
        r = x.ixazomib_exposure(state(total_bilirubin=70.0), REQUEST)               # 3.3 x ULN: severe
        groups = r['observed_instead'][0]['groups']
        self.assertAlmostEqual(groups[0]['ratio_to_reference_dose_normalised'], (846 / 2.3) / (1160 / 4))
        r = x.ixazomib_exposure(state(), dict(REQUEST, disease_code='SOLID_TUMOUR'))
        self.assertIsNone(r['model_outputs'])
        self.assertEqual(r['observed_instead'], [])

    def test_result_is_hashed_and_not_validated(self):
        r = x.ixazomib_exposure(state(), REQUEST)
        body = copy.deepcopy(r)
        claimed = body.pop('result_sha256')
        from intelligence_store.patient_state import digest
        self.assertEqual(digest(body), claimed)
        self.assertFalse(r['clinical_prediction_validated'])
        self.assertFalse(r['scope_evaluation']['clinical_prediction_validated'])


if __name__ == '__main__':
    unittest.main()


class Page(unittest.TestCase):
    def setUp(self):
        from app.app import app
        self.client = app.test_client()
        self.url = '/landscape/patient-lab/ixazomib-exposure'

    def test_default_is_in_scope_with_auc_and_no_peak(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Typical total exposure', r.data)
        self.assertNotIn(b'Observed in a dedicated study', r.data)

    def test_out_of_scope_shows_observed_and_no_model_value(self):
        r = self.client.get(self.url + '?disease=MM&dose=3&weight=70&height=165&age=65&crcl=20&bilirubin=8&bilirubin_uln=21')
        self.assertIn(b'Outside the model', r.data)
        self.assertIn(b'Observed in a dedicated study', r.data)
        self.assertNotIn(b'Typical total exposure</h2>', r.data)

    def test_empty_field_is_unknown(self):
        r = self.client.get(self.url + '?disease=MM&dose=3&weight=70&height=165&age=65&crcl=60&bilirubin=&bilirubin_uln=21')
        self.assertIn(b'Cannot determine', r.data)

    def test_bad_input_and_json(self):
        self.assertEqual(self.client.get(self.url + '?dose=abc').status_code, 400)
        self.assertEqual(self.client.get(self.url + '?unexpected=1').status_code, 400)
        self.assertEqual(self.client.get(self.url + '?disease=XYZ').status_code, 400)
        j = self.client.get(self.url + '?format=json')
        self.assertEqual(json.loads(j.data)['scope_evaluation']['status'], 'in_scope')
