"""Digital human 1.0, step 1.4: explorer mode and the observed-data context panel."""
import json
import re
import unittest
from pathlib import Path

from flask import Flask

from intelligence_store.body_map import explorer_map
from intelligence_store.body_map_context import BodyMapContextError, body_map_context, load_ema_2013
from intelligence_store.lenalidomide_label import load_label_extract
from intelligence_store.lenalidomide_renal_pathways import load_evidence
from intelligence_store.run_record import record_for_body_map_explorer
from landscape_ui.body_map_pages import EXPLORER_DEFAULT_CRCL, parse_crcl

URL = '/landscape/patient-lab/body-map'


class ObservedContext(unittest.TestCase):
    def test_observed_values_are_copied_from_the_pinned_extracts(self):
        ema08 = {g['group']: g for g in load_evidence()['groups']}
        t3 = load_ema_2013()['table_3_geometric_means']
        for crcl, band08, band13 in ((110, 'normal', 'normal'), (65, 'mild', 'mild'), (40, 'moderate', 'moderate'),
                                     (20, 'severe_without_dialysis', 'severe')):
            ctx = body_map_context(explorer_map(crcl))
            rows = {r['quantity']: r for r in ctx['comparison']}
            urine = [o['value'] for o in rows['Dose leaving unchanged in urine']['observed']]
            self.assertEqual(urine, [ema08[band08]['fe_percent'], t3['urine_excretion_pct_dose'][band13]['geometric_mean']])
            self.assertEqual(rows['Renal clearance']['observed'][0]['value'], t3['renal_clearance'][band13]['geometric_mean'])
            cl = [o['value'] for o in rows['Total apparent clearance (CL/F)']['observed']]
            self.assertEqual(cl, [ema08[band08]['cl_f_ml_min'][0], t3['cl_f'][band13]['geometric_mean']])
            exposure = rows['Exposure at the same dose, relative to normal function']['observed']
            self.assertAlmostEqual(exposure[0]['value'], ema08[band08]['auc_ng_h_ml'][0] / ema08['normal']['auc_ng_h_ml'][0])
            self.assertTrue(all(o['derived'] for o in exposure))

    def test_model_column_is_the_map_itself(self):
        view = explorer_map(40)
        ctx = body_map_context(view)
        rows = {r['quantity']: r for r in ctx['comparison']}
        self.assertEqual(rows['Renal clearance']['model'], next(f['value'] for f in view['flows'] if f['kind'] == 'renal_excretion'))
        self.assertEqual(rows['Total apparent clearance (CL/F)']['model'], view['totals']['total_ml_min'])
        self.assertEqual(ctx['view_sha256'], view['view_sha256'])
        self.assertEqual(ctx['band_status'], 'check_disagrees')

    def test_ratios_only_where_the_ema_reported_them(self):
        self.assertIsNone(body_map_context(explorer_map(110))['geometric_mean_ratios'])
        self.assertIsNone(body_map_context(explorer_map(65))['geometric_mean_ratios'])
        moderate = body_map_context(explorer_map(40))['geometric_mean_ratios']
        self.assertEqual(moderate['auc_infinity_pct'], {'ratio': 259, 'ci90': [209, 322]})

    def test_regression_is_context_evaluated_at_the_chosen_value(self):
        reg = body_map_context(explorer_map(60))['regression']
        self.assertAlmostEqual(reg['value_at_crcl_ml_min'], -17.35 + 1.89 * 60)
        self.assertIn('cannot check the model', reg['note'])

    def test_label_rows_quoted_and_matched_without_proposing_a_dose(self):
        rows = load_label_extract()['renal_dose_adjustments']['rows']
        for crcl, expected in ((110, None), (61, None), (60, 0), (30, 0), (29.5, 1), (10, 1)):
            ctx = body_map_context(explorer_map(crcl))
            self.assertEqual(ctx['label']['matched_row'], expected, crcl)
            self.assertEqual([r['mm_combination'] for r in ctx['label']['rows']], [r['mm_combination'] for r in rows])
            self.assertIn('proposes no dose', ctx['label']['statement'])
        self.assertFalse(any(r['matches'] for r in body_map_context(explorer_map(20))['label']['rows'] if r['dialysis']))

    def test_flags_stay_false_and_context_is_reproducible(self):
        a, b = body_map_context(explorer_map(40)), body_map_context(explorer_map(40))
        self.assertEqual(a['context_sha256'], b['context_sha256'])
        self.assertFalse(a['clinical_prediction_validated'])
        self.assertFalse(a['ready_for_patient_simulation'])

    def test_no_context_for_a_map_that_was_not_drawn(self):
        with self.assertRaises(BodyMapContextError):
            body_map_context(explorer_map(5))


class ExplorerRunRecord(unittest.TestCase):
    def test_record_has_no_patient_and_names_the_entered_value(self):
        view = explorer_map(40)
        record = record_for_body_map_explorer(view, body_map_context(view))
        self.assertIsNone(record['patient_record']['revision_id'])
        self.assertEqual(record['inputs_from_record'][0]['value'], 40.0)
        labels = [c['label'] for c in record['checksums']]
        self.assertIn('Body map view', labels)
        self.assertIn('Observed-data context', labels)
        self.assertEqual(record['warnings'], [view['band']['status_text']])
        self.assertFalse(record['validation']['clinical_prediction_validated'])

    def test_calibration_point_has_no_warning(self):
        self.assertEqual(record_for_body_map_explorer(explorer_map(110))['warnings'], [])


class ExplorerPage(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(TESTING=True)
        app.add_url_rule('/', 'home', lambda: 'Home')
        from landscape_ui import register_landscape
        register_landscape(app)
        self.client = app.test_client()

    def test_default_is_the_calibration_point(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn(f'value="{EXPLORER_DEFAULT_CRCL}"', html)
        self.assertIn('No patient record', html)
        self.assertNotIn('Synthetic patient record', html)

    def test_page_shows_map_context_and_record(self):
        html = self.client.get(f'{URL}?crcl=40').get_data(as_text=True)
        for text in ('body-map-viewer', 'Outside check disagrees', 'What the renal-impairment study observed',
                     'In two studies of myeloma patients never used to fit it', 'not a blind test',
                     'Exposure ratios reported by the EMA', 'context, not a check', 'proposes no dose',
                     'row containing this value', 'Run record', 'Flow diagram', 'body-map-explorer.js',
                     'leaves in urine in one pass', 'returns by the renal veins'):
            self.assertIn(text, html)
        config = json.loads(re.search(r'<script id="body-map-config" type="application/json">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(config['flows']['band']['id'], 'moderate')

    def test_reloading_controls_keep_the_scroll_position(self):
        html = self.client.get(f'{URL}?crcl=40').get_data(as_text=True)
        self.assertIn('marlo-scroll.js', html)
        root = Path(__file__).resolve().parents[1] / 'landscape_ui' / 'static'
        self.assertIn('form.requestSubmit', (root / 'body-map' / 'body-map-explorer.js').read_text())
        script = (root / 'marlo-scroll.js').read_text()
        self.assertIn('sessionStorage', script)
        self.assertNotIn('http', script.replace('location.href', ''))

    def test_json_has_view_and_context(self):
        response = self.client.get(f'{URL}?crcl=65&format=json')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.get_data(as_text=True))
        self.assertEqual(body['body_map_view']['mode'], 'explorer')
        self.assertEqual(body['observed_context']['band'], 'mild')
        self.assertEqual(body['observed_context']['view_sha256'], body['body_map_view']['view_sha256'])

    def test_outside_range_draws_nothing(self):
        for value in ('5', '141', '0'):
            response = self.client.get(f'{URL}?crcl={value}')
            self.assertEqual(response.status_code, 200)
            html = response.get_data(as_text=True)
            self.assertIn('Map not drawn', html)
            self.assertNotIn('body-map-config', html)
            self.assertNotIn('What the renal-impairment study observed', html)

    def test_bad_requests(self):
        for query in ('crcl=abc', 'crcl=nan', 'crcl=inf', 'crcl=', 'crcl=40&crcl=50', 'crcl=40&x=1', 'format=xml',
                      'crcl=1234567890123'):
            self.assertEqual(self.client.get(f'{URL}?{query}').status_code, 400, query)

    def test_parse_crcl(self):
        self.assertIsNone(parse_crcl(None))
        self.assertEqual(parse_crcl(' 42.5 '), 42.5)
        for bad in ('', 'x', 'nan', '-inf'):
            with self.assertRaises(ValueError):
                parse_crcl(bad)
