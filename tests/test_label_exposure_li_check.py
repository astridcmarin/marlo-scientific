"""Phase 3.1d: the label-based pomalidomide curve against the Li 2017 population PK model."""
import json
from pathlib import Path
import tempfile
import unittest

from intelligence_store import label_exposure as le
from intelligence_store import label_exposure_li_check as chk


class Inputs(unittest.TestCase):
    def test_plan_and_li_extract_are_pinned_and_locked(self):
        for loader, path in ((chk.load_plan, chk.PLAN_PATH), (chk.load_li, chk.LI_PATH)):
            with tempfile.TemporaryDirectory() as tmp:
                changed = Path(tmp) / path.name
                changed.write_bytes(path.read_bytes() + b' ')
                with self.assertRaises(ValueError):
                    loader(changed)
        self.assertEqual(chk.load_plan()['status'], 'locked_before_computation')
        self.assertEqual(chk.load_plan()['inputs']['li_extract']['sha256'], chk.LI_SHA256)


class LiCurve(unittest.TestCase):
    def test_lag_shifts_the_curve_and_keeps_the_exposure(self):
        p = chk.li_typical(chk.load_li())
        no_lag = dict(p, tlag_h=0.0)
        self.assertAlmostEqual(chk.li_steady_state_ng_ml(5.0 + p['tlag_h'], p), chk.li_steady_state_ng_ml(5.0, no_lag), places=10)
        self.assertAlmostEqual(chk.li_steady_state_ng_ml(0.0, p), chk.li_steady_state_ng_ml(24.0 - p['tlag_h'], no_lag), places=10)
        s = chk._summary(lambda t: chk.li_steady_state_ng_ml(t, p))
        self.assertAlmostEqual(s['auc_0_24_ng_h_ml'] / (4000 / p['cl_f_l_h']), 1.0, places=5)


class LockedResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = chk.run_check()

    def test_committed_report_reproduces_exactly(self):
        self.assertEqual(self.report, json.loads(chk.REPORT_PATH.read_text()))

    def test_uses_the_set_selected_in_3_1c(self):
        selected = json.loads(le.REPORT_PATH.read_text())['decision']['selected_set']
        self.assertEqual(selected, 'A_exposure_derived_mm')
        self.assertAlmostEqual(self.report['label_engine_parameters']['cl_f_l_h'], 4000 / 860)

    def test_findings(self):
        r = self.report
        self.assertIs(r['clinical_prediction_validated'], False)
        self.assertEqual(r['primary']['classification'], 'consistent')
        self.assertTrue(all(v['result'] == 'pass' for v in r['typical_curve_ratios'].values()))
        self.assertAlmostEqual(r['typical_curve_ratios']['cmax']['ratio'], 1.205, places=3)
        self.assertEqual(r['dialysis_scenario']['classification'], 'consistent')
        self.assertTrue(r['decision']['curve_consistent_with_li_2017'])
        # Descriptive: the label volume is just below Li's interval, and ka from Tmax 2 h would push Cmax past 1.25.
        self.assertFalse(r['descriptive']['parameters_against_li_intervals']['v_f_l']['inside_li_interval'])
        self.assertGreater(r['descriptive']['ka_sensitivity'][0]['cmax_ratio_to_li'], 1.25)


if __name__ == '__main__':
    unittest.main()
