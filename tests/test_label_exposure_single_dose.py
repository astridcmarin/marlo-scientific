"""Phase 3.1f: single-dose label-based engine and the locked dexamethasone (HEMADY) consistency check."""
import json
import math
from pathlib import Path
import tempfile
import unittest

from intelligence_store import label_exposure_single_dose as sd
from intelligence_store.capability_levels import drug_level


class Inputs(unittest.TestCase):
    def test_plan_and_label_are_pinned(self):
        for loader, path in ((sd.load_plan, sd.PLAN_PATH), (sd.load_label, sd.LABEL_PATH)):
            with tempfile.TemporaryDirectory() as tmp:
                changed = Path(tmp) / path.name
                changed.write_bytes(path.read_bytes() + b' ')
                with self.assertRaises(ValueError):
                    loader(changed)

    def test_parameter_set_follows_the_plan(self):
        p = sd.parameter_set(sd.load_label())
        self.assertEqual(p['cl_f_l_h'], 15.7)
        self.assertAlmostEqual(p['v_f_l'], 15.7 * 4 / math.log(2))


class LockedResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = sd.run_check()

    def test_committed_report_reproduces_exactly(self):
        self.assertEqual(self.report, json.loads(sd.REPORT_PATH.read_text()))

    def test_eligible_with_a_low_peak(self):
        r = self.report
        self.assertIs(r['clinical_prediction_validated'], False)
        self.assertTrue(r['numerical_checks']['passed'])
        self.assertTrue(r['decision']['eligible'])
        c = r['parameter_set']['primary']['checks']
        self.assertAlmostEqual(c['C1_clearance_vs_exposure']['ratio'], 0.998, places=3)
        self.assertAlmostEqual(c['C3_single_dose_cmax']['ratio'], 0.752, places=3)
        self.assertEqual([s['cmax_result'] for s in r['parameter_set']['tmax_sensitivity']], ['pass', 'fail'])
        self.assertIn("'subjects'", r['population_note'])

    def test_shown_only_after_the_outside_check(self):
        # 3.1e rule: a label curve is shown only after an outside check; dexamethasone passed one in 3.1g.
        self.assertEqual(drug_level('Dexamethasone', True)['id'], 'label_based_exposure')


if __name__ == '__main__':
    unittest.main()
