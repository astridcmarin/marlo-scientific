import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from intelligence_store import bortezomib_figure_review as review

class FigureTests(unittest.TestCase):
    def test_axes_and_conversion(self):
        s=review.build_figure_review()['source']
        for k in ['pk','pd']:
            for point in s['figures'][k]['y_calibration']:
                self.assertAlmostEqual(review.pixel_value(point['pixel_y'],s['figures'][k]),point['value'])
        self.assertAlmostEqual(review.pixel_value((467+126)/2,s['figures']['pk']),10**0.5)
        for r in review.build_figure_review()['rows']:
            self.assertAlmostEqual(r['approximate_concentration_nm'],r['approximate_concentration_ng_ml']*1000/384.24)
    def test_independent_equation_and_interval_enclosure(self):
        for r in review.build_figure_review()['rows']:
            c=r['approximate_concentration_nm']
            expected=100-71.1*c**1.47/(1.79**1.47+c**1.47)
            self.assertAlmostEqual(expected,r['equation_activity_at_mean_concentration_percent'])
            for bounds,value in [('difference_reading_range','descriptive_difference_percentage_points'),('concentration_reading_range_ng_ml','approximate_concentration_ng_ml'),('activity_reading_range','approximate_observed_activity_percent')]:
                self.assertLess(r[bounds][0],r[value]);self.assertGreater(r[bounds][1],r[value])
    def test_limits_and_deterministic_hash(self):
        r=review.build_figure_review()
        self.assertEqual(r['status'],'review_required');self.assertEqual(r['individual_matched_pairs'],0)
        self.assertIsNone(r['rmse']);self.assertIsNone(r['mae'])
        for k in ['independent_validation','clinical_prediction_validated','ready_for_patient_simulation','refitting_performed']:self.assertFalse(r[k])
        self.assertIn('overlap',r['rows'][0]['marker_review'])
        digest=r.pop('report_sha256')
        self.assertEqual(digest,hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest())
    def test_missing_or_changed_source(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source.json'
            with patch.object(review,'DATA_PATH',p):
                with self.assertRaises(ValueError):review.build_figure_review()
                p.write_text('{}')
                with self.assertRaises(ValueError):review.build_figure_review()

class PageTests(unittest.TestCase):
    def setUp(self):
        from flask import Flask
        from landscape_ui import register_landscape
        app=Flask(__name__);app.config['TESTING']=True;app.add_url_rule('/','home',lambda:'Home')
        register_landscape(app);self.client=app.test_client();self.path='/landscape/simulation-lab/bortezomib-figure-review'
    def test_page_export_and_navigation(self):
        r=self.client.get(self.path);self.assertEqual(r.status_code,200)
        self.assertIn('markers overlap',r.get_data(as_text=True));self.assertEqual(r.headers['Cache-Control'],'no-store')
        self.assertEqual(r.get_data(as_text=True).count('class="nav-item active"'),1)
        self.assertEqual(self.client.get(self.path+'?format=json').json,review.build_figure_review())
        self.assertIn(self.path,self.client.get('/landscape/simulation-lab/bortezomib-evidence').get_data(as_text=True))
    def test_requests_and_fail_closed(self):
        for q in ['patient_id=1','format=csv','format=json&format=html']:
            self.assertEqual(self.client.get(self.path+'?'+q).status_code,400)
        self.assertEqual(self.client.post(self.path).status_code,405)
        with patch('landscape_ui.bortezomib_figure_pages.build_figure_review',side_effect=ValueError()):
            self.assertEqual(self.client.get(self.path).status_code,503)
if __name__=='__main__':unittest.main()
