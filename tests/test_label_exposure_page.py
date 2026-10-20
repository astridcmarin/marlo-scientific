"""Phase 3.1e: the label-based exposure page, its scenarios, and withholding when a source or check changes."""
import json
import unittest
from unittest import mock

from flask import Flask

from intelligence_store import capability_levels as cl
from intelligence_store import label_exposure_view as lv
from landscape_ui import register_landscape

URL = '/landscape/patient-lab/label-exposure/pomalidomide'


def client():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.add_url_rule('/', 'home', lambda: 'Home')
    register_landscape(app)
    return app.test_client()


class View(unittest.TestCase):
    def test_shown_only_with_intact_sources_and_passing_checks(self):
        self.assertEqual(lv.available(), {'pomalidomide': 'Pomalidomide'})
        v = lv.view('pomalidomide')
        self.assertIs(v['clinical_prediction_validated'], False)
        self.assertEqual(v['selected_set'], 'A_exposure_derived_mm')
        self.assertAlmostEqual(v['steady_state']['auc_tau_ng_h_ml_exact'], 860.0, places=6)

    def test_a_changed_report_withholds_the_curve_and_the_level(self):
        broken = dict(lv.REGISTRY['pomalidomide'], outside_report=(lv.REGISTRY['pomalidomide']['outside_report'][0], '0' * 64))
        with mock.patch.dict(lv.REGISTRY, {'pomalidomide': broken}):
            self.assertEqual(lv.available(), {})
            with self.assertRaises(ValueError):
                lv.view('pomalidomide')
            self.assertEqual(cl.drug_level('Pomalidomide', True)['id'], 'knowledge_only')
            self.assertEqual(client().get(URL).status_code, 503)

    def test_scenario_scales_clearance_by_the_label_fold_only(self):
        base = lv.view('pomalidomide')
        dial = lv.view('pomalidomide', 'renal_severe_requiring_dialysis')
        self.assertAlmostEqual(dial['scenario_steady_state']['auc_tau_ng_h_ml_exact'] / base['steady_state']['auc_tau_ng_h_ml_exact'], 1.38)
        self.assertIn('38%', dial['scenario']['quote'])
        hep = lv.view('pomalidomide', 'hepatic_child_pugh_c')
        self.assertTrue(hep['scenario']['not_myeloma_patients'])
        self.assertIn('72%', hep['scenario']['quote'])
        with self.assertRaises(KeyError):
            lv.view('pomalidomide', 'high_fat_meal')     # single-dose food effect is text only
        with self.assertRaises(KeyError):
            lv.view('lenalidomide')


class Page(unittest.TestCase):
    def setUp(self):
        self.client = client()

    def test_page_states_what_it_is_and_what_was_checked(self):
        page = self.client.get(URL).get_data(as_text=True)
        for text in ('not a population model, not a prediction for any patient', 'Clinical prediction validated: <strong>false</strong>',
                     'Weakest point: the peak', 'Li 2017 population model', 'Why not the label', 'doi:10.2147/CPAA.S144606',
                     'f5b91ce96404f0fc9f39eb83c531f7fef8e6385e0cdb00211cb7c31de5288711'):
            self.assertIn(text, page)

    def test_scenarios_and_bad_requests(self):
        page = self.client.get(URL + '?scenario=fluvoxamine_strong_cyp1a2_inhibitor').get_data(as_text=True)
        self.assertIn('Not studied in myeloma patients', page)
        self.assertIn('125%', page)
        self.assertEqual(self.client.get(URL + '?scenario=high_fat_meal').status_code, 400)
        self.assertEqual(self.client.get(URL + '?scenario=made_up').status_code, 400)
        self.assertEqual(self.client.get(URL + '?other=1').status_code, 400)
        self.assertEqual(self.client.get('/landscape/patient-lab/label-exposure/lenalidomide').status_code, 404)

    def test_json_download_carries_quotes_and_pins(self):
        data = json.loads(self.client.get(URL + '?scenario=renal_severe_requiring_dialysis&format=json').data)
        self.assertEqual(data['scenario']['id'], 'renal_severe_requiring_dialysis')
        self.assertEqual(data['label_source']['dailymed_set_id'], '2b25ef01-5c9e-11e1-b86c-0800200c9a66')
        self.assertIs(data['clinical_prediction_validated'], False)


if __name__ == '__main__':
    unittest.main()
