"""Digital human 1.1e: the body map's timeline (one dose, time-course model v1, with its locked check beside it)."""
import json
import unittest

from flask import Flask

from intelligence_store.body_map_time_course import REPORT_V1_SHA256, timeline

URL = '/landscape/patient-lab/body-map'


class Timeline(unittest.TestCase):
    def test_amounts_sum_to_the_dose_and_end_in_urine_and_other_routes(self):
        for crcl, band in ((110, 'normal'), (65, 'mild'), (40, 'moderate'), (20, 'severe')):
            tl = timeline(crcl, band)
            self.assertEqual(len(tl['rows']), 193)
            for r in tl['rows']:
                self.assertAlmostEqual(sum(r['pct_dose'].values()), 100.0, places=9)
            last = tl['rows'][-1]['pct_dose']
            self.assertAlmostEqual(last['urine'] / (last['urine'] + last['non_renal']), tl['summary']['fraction_excreted_unchanged'], places=9)
            self.assertEqual(tl['rows'][0]['pct_dose']['gut'], 100.0)

    def test_check_rows_come_from_the_pinned_v1_report_for_the_band_group(self):
        tl = timeline(40, 'moderate')
        self.assertEqual(tl['check_report']['sha256'], REPORT_V1_SHA256)
        self.assertEqual(tl['study_group_checked'], 'moderate')
        peak = next(c for c in tl['check'] if c['endpoint'] == 'Peak concentration')
        self.assertEqual((peak['observed_gm'], peak['text']), (568, 'too low'))
        self.assertIn('Peak too low', tl['warning'])
        self.assertTrue(any('F = 1' in item for item in tl['limits']))
        self.assertFalse(tl['clinical_prediction_validated'])

    def test_observed_urine_share_is_shown_and_not_called_checked(self):
        tl = timeline(40, 'moderate')
        u = tl['observed_urine']
        self.assertEqual((u['group'], u['observed_gm_pct'], u['observed_cv_pct'], u['checked']), ('moderate', 38, 48, False))
        self.assertAlmostEqual(u['model_pct'], 100 * tl['summary']['fraction_excreted_unchanged'])
        self.assertIn('not a check endpoint', tl['warning'])
        self.assertTrue(any('model construct' in item for item in tl['limits']))

    def test_reproducible(self):
        self.assertEqual(timeline(55, 'mild')['timeline_sha256'], timeline(55, 'mild')['timeline_sha256'])


class Page(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(TESTING=True)
        app.add_url_rule('/', 'home', lambda: 'Home')
        from landscape_ui import register_landscape
        register_landscape(app)
        self.client = app.test_client()

    def test_explorer_shows_the_timeline_with_slider_and_check(self):
        html = self.client.get(f'{URL}?crcl=40').get_data(as_text=True)
        for text in ('Over time after one 25 mg dose', 'id="bm-tl-slider"', 'body-map-timeline.js', 'Peak too low',
                     'What the locked check found for the moderate group', '568 (436–740)', 'bm-timeline-data'):
            self.assertIn(text, html)
        rows = json.loads(html.split('<script id="bm-timeline-data" type="application/json">')[1].split('</script>')[0])
        self.assertEqual(len(rows), 193)
        self.assertEqual(rows[0]['p']['gut'], 100.0)

    def test_json_carries_the_time_course(self):
        body = json.loads(self.client.get(f'{URL}?crcl=65&format=json').get_data(as_text=True))
        self.assertEqual(body['time_course']['band'], 'mild')

    def test_no_timeline_when_no_map(self):
        html = self.client.get(f'{URL}?crcl=5').get_data(as_text=True)
        self.assertNotIn('bm-timeline', html)

    def test_slider_script_never_moves_on_its_own(self):
        from pathlib import Path
        script = (Path(__file__).resolve().parents[1] / 'landscape_ui/static/body-map/body-map-timeline.js').read_text()
        for word in ('setInterval', 'setTimeout', 'requestAnimationFrame', 'http'):
            self.assertNotIn(word, script)


if __name__ == '__main__':
    unittest.main()
