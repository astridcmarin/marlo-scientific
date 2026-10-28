"""Phase 4.1e: scoring rules of the locked accuracy check (synthetic pairs only; the real run is in the report)."""
import unittest

from intelligence_store import eligibility_validation as ev


def v(comp, value, unit, **kw):
    return dict(comparator=comp, value=value, unit=unit, **kw)


def entry(status, *values):
    return {'status': status, 'values': list(values)}


class Matching(unittest.TestCase):
    def test_equivalences_of_the_plan(self):
        self.assertTrue(ev.values_match('anc_min', v('>=', '1.0', 'x 10^9/L'), v('>=', '1000', '/mm3 (= /uL)')))
        self.assertTrue(ev.values_match('anc_min', v('>=', '1000', 'cells/uL'), v('>=', '1000', '/mm3 (= /uL)')))
        self.assertTrue(ev.values_match('hemoglobin_min', v('>=', '80', 'g/L'), v('>=', '8', 'g/dL')))
        self.assertTrue(ev.values_match('creatinine_max', v('<=', '176.8', 'umol/L'), v('<=', '2', 'mg/dL')))
        self.assertTrue(ev.values_match('bilirubin_max', v('<=', '34.2', 'umol/L'), v('<=', '2.0', 'mg/dL')))
        self.assertFalse(ev.values_match('bilirubin_max', v('<=', '26', 'umol/L'), v('<=', '1.5', 'mg/dL')))

    def test_non_equivalences(self):
        self.assertFalse(ev.values_match('creatinine_max', v('<=', '2', 'x ULN'), v('<=', '2', 'mg/dL')))
        self.assertFalse(ev.values_match('kidney_function_min', v('>=', '30', 'mL/min'), v('>=', '30', 'mL/min/1.73 m2')))
        self.assertFalse(ev.values_match('ecog_max', v('<=', '2', 'score'), v('<', '2', 'score')))
        self.assertFalse(ev.values_match('platelets_min', v('>=', '75', 'x 10^9/L'), v('>=', '75000.5', '/mm3 (= /uL)')))
        self.assertTrue(ev.values_match('platelets_min', v('>', '75', 'other'), v('>', '75.0', 'other')))


class Pairs(unittest.TestCase):
    def test_outcomes(self):
        two = v('<=', '2', 'score')
        self.assertEqual(ev.score_pair('ecog_max', entry('stated', two), entry('stated', two))['outcome'], 'tp')
        self.assertEqual(ev.score_pair('ecog_max', entry('not_stated'), entry('not_stated'))['outcome'], 'tn')
        self.assertEqual(ev.score_pair('ecog_max', entry('not_stated'), entry('stated', two))['outcome'], 'fp')
        self.assertEqual(ev.score_pair('ecog_max', entry('stated', two), entry('not_stated'))['outcome'], 'fn')
        self.assertEqual(ev.score_pair('ecog_max', entry('stated', two), entry('stated', v('<=', '1', 'score')))['outcome'], 'fp+fn')
        self.assertEqual(ev.score_pair('ecog_max', entry('stated', two), entry('multiple', two, v('<=', '1', 'score')))['outcome'], 'fp')
        self.assertEqual(ev.score_pair('ecog_max', entry('multiple', two, v('<=', '1', 'score')), entry('stated', two))['outcome'], 'fn')
        self.assertEqual(ev.score_pair('ecog_max', {'status': 'unclear', 'values': []}, entry('stated', two))['outcome'], 'excluded_unclear')

    def test_summary_and_decision(self):
        pairs = [dict(type='ecog_max', annotated_status='stated', outcome='tp', tp=True, fp=False, fn=False) for _ in range(60)]
        s = ev.summarise(pairs)['ecog_max']
        self.assertEqual((s['precision'], s['recall'], s['decision']), (1.0, 1.0, 'pass'))
        self.assertGreater(s['precision_95ci'][0], 0.93)
        pairs += [dict(type='ecog_max', annotated_status='stated', outcome='fn', tp=False, fp=False, fn=True) for _ in range(12)]
        self.assertEqual(ev.summarise(pairs)['ecog_max']['decision'], 'fail')
        few = [dict(type='anc_min', annotated_status='stated', outcome='tp', tp=True, fp=False, fn=False) for _ in range(19)]
        self.assertEqual(ev.summarise(few)['anc_min']['decision'], 'insufficient_data')

    def test_wilson(self):
        lo, hi = ev.wilson(57, 60)
        self.assertAlmostEqual(lo, 0.8628, places=3)
        self.assertAlmostEqual(hi, 0.9829, places=3)


class Pins(unittest.TestCase):
    def test_inputs_are_pinned(self):
        ev.load_plan()
        ev.check_extractor_frozen()
        a = ev.load_annotations()
        self.assertEqual(len(a['annotations']), 120)


if __name__ == '__main__':
    unittest.main()
