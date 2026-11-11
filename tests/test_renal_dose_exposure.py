"""Reviewer's checklist R9: label kidney doses and exposure, descriptive, from pinned sources."""
import unittest

from flask import Flask

from intelligence_store import renal_dose_exposure as rde
from intelligence_store.lenalidomide_bridoux_check import DESIGN_SHA256
from intelligence_store.body_map_context import EMA_2013_SHA256
from intelligence_store.lenalidomide_label import EXTRACT_SHA256


class View(unittest.TestCase):
    def setUp(self):
        self.v = rde.build()
        self.b = {b['band']: b for b in self.v['bands']}

    def test_pins_match_the_owning_modules(self):
        self.assertEqual(rde.SOURCES['bridoux_design'][1], DESIGN_SHA256)
        self.assertEqual(rde.SOURCES['ema_2013'][1], EMA_2013_SHA256)
        self.assertEqual(rde.SOURCES['label'][1], EXTRACT_SHA256)

    def test_bridoux_ratios(self):
        self.assertAlmostEqual(self.b['moderate']['bridoux']['ratio_to_normal'], 1800 / 1747)
        self.assertAlmostEqual(self.b['severe']['bridoux']['ratio_to_normal'], 2329 / 1747)
        self.assertAlmostEqual(self.b['dialysis']['bridoux']['ratio_to_normal'], 2020 / 1747)
        self.assertTrue(all(b['bridoux']['same_dose_as_label'] for b in self.v['bands']))
        self.assertAlmostEqual(self.v['mild_bridoux']['ratio_to_normal'], 2605 / 1747)

    def test_bridoux_intervals_are_derived_from_gcv_and_n(self):
        import math
        c = self.b['moderate']['bridoux']['ratio_ci90']
        s2a, s2b = math.log(1 + 0.135 ** 2), math.log(1 + 0.268 ** 2)
        se = math.sqrt(s2a / 7 + s2b / 10)
        self.assertAlmostEqual(math.log(c['upper'] / (1800 / 1747)), math.log((1800 / 1747) / c['lower']))
        self.assertAlmostEqual(math.log(c['upper'] / (1800 / 1747)) / se, 1.761, places=2)
        self.assertEqual([round(x, 2) for x in (c['lower'], c['upper'])], [0.87, 1.22])
        self.assertIn('derived by the platform', self.v['notes']['interval'])

    def test_cc5013_scaled_by_dose(self):
        self.assertAlmostEqual(self.b['moderate']['cc5013']['scaled_ratio'], 2.59 * 10 / 25)
        self.assertAlmostEqual(self.b['severe']['cc5013']['scaled_ratio'], 3.52 * 7.5 / 25)
        self.assertAlmostEqual(self.b['dialysis']['cc5013']['scaled_ratio'], 4.77 * 5 / 25)
        self.assertEqual([round(x, 4) for x in self.b['moderate']['cc5013']['scaled_ci90']], [round(2.09 * 0.4, 4), round(3.22 * 0.4, 4)])

    def test_sponsor_rows_are_myeloma_regimens_only(self):
        self.assertEqual([s['regimen'] for s in self.b['severe']['sponsor']], ['15 mg q48h (MM)', '7.5 mg q24h (MM)'])
        self.assertAlmostEqual(self.b['severe']['sponsor'][0]['ratio'], 2507 / 2392)
        self.assertIsNone(self.b['moderate']['sponsor'])

    def test_no_threshold_no_dose(self):
        self.assertIn('sets no threshold', self.v['notes']['no_threshold'])
        self.assertIn('proposes no dose', self.v['notes']['no_threshold'])
        self.assertFalse(self.v['clinical_prediction_validated'])

    def test_changed_source_is_refused(self):
        path, sha, title = rde.SOURCES['bridoux']
        try:
            rde.SOURCES['bridoux'] = (path, '0' * 64, title)
            with self.assertRaises(rde.RenalDoseExposureError):
                rde.build()
        finally:
            rde.SOURCES['bridoux'] = (path, sha, title)


class Page(unittest.TestCase):
    def test_lenalidomide_page_shows_it(self):
        app = Flask(__name__)
        app.config.update(TESTING=True)
        app.add_url_rule('/', 'home', lambda: 'Home')
        from landscape_ui import register_landscape
        register_landscape(app)
        client = app.test_client()
        html = client.get('/landscape/drugs/lenalidomide/special-populations').get_data(as_text=True)
        for text in ('not a judgement of the label', 'The platform sets no threshold and proposes no dose', '1.03', '1.33', '1.04</strong> (0.84–1.29)', '(0.87–1.22, derived)',
                     'sets no threshold', 'first dose reduction was at 50 mL/min'):
            self.assertIn(text, html)
        self.assertNotIn('sp-renal-dose-exposure', client.get('/landscape/drugs/ixazomib/special-populations').get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
