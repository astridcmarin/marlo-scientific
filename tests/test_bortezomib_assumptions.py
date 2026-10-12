import unittest,hashlib,json
from unittest.mock import patch
from intelligence_store.bortezomib_timecourse import build_timecourse
from intelligence_store.bortezomib_assumption_sensitivity import build_assumption_sensitivity

class AssumptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.r=build_assumption_sensitivity()
    def test_original_default_output_unchanged(self):
        self.assertEqual(build_timecourse()['report_sha256'],'bcede5baa139f2322c81c7011a9583f00e5fcdb765b893e67b5ec6b65e176735')
    def test_override_provenance_and_constant_regimen(self):
        for s in self.r['scenarios']:
            r=s['run'];rate=s['assumed_relaxation_rate_per_h']
            self.assertEqual(r['reference']['assumed_relaxation_rate_per_h'],1)
            self.assertEqual(r['dose_mg'],2.327)
            self.assertLess(r['maximum_mass_balance_error_mg'],1e-10)
            if rate!=1:self.assertEqual(r['assumption_override']['relaxation_rate_per_h'],rate)
            else:self.assertNotIn('assumption_override',r)
            self.assertEqual([x['time_h'] for x in r['points'] if x['phase']=='post_dose'],[0,72,168,240])
    def test_comparison_arithmetic_and_no_statistics(self):
        base=self.r['scenarios'][1]['run']['points']
        for s in self.r['scenarios']:
            for key in ['concentration_nm','activity_percent']:
                expected=max(abs(a[key]-b[key]) for a,b in zip(s['run']['points'],base))
                self.assertEqual(s['maximum_sampled_absolute_difference_from_1_per_h'][key],expected)
        self.assertIsNone(self.r['confidence_interval']);self.assertFalse(self.r['equation_4_resolved'])
        self.assertFalse(self.r['clinical_prediction_validated']);self.assertFalse(self.r['ready_for_patient_simulation'])
        self.assertEqual(len(self.r['selected_times']),8)
    def test_rate_validation_and_finer_step_all_scenarios(self):
        for invalid in [0,False,float('nan'),float('inf'),11,'1']:
            with self.assertRaises(ValueError):build_timecourse(relaxation_rate_per_h=invalid)
        for s in self.r['scenarios']:
            fine=build_timecourse(max_step_h=0.01,relaxation_rate_per_h=s['assumed_relaxation_rate_per_h'])
            for a,b in zip(s['run']['points'],fine['points']):
                self.assertLess(abs(a['concentration_nm']-b['concentration_nm']),0.002)
                self.assertLess(abs(a['activity_percent']-b['activity_percent']),0.001)
    def test_hash(self):
        r=dict(self.r);h=r.pop('report_sha256')
        self.assertEqual(h,hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest())

class PageTests(unittest.TestCase):
    def setUp(self):
        from flask import Flask
        from landscape_ui import register_landscape
        app=Flask(__name__);app.config['TESTING']=True;app.add_url_rule('/','home',lambda:'Home');register_landscape(app)
        self.client=app.test_client();self.path='/landscape/simulation-lab/bortezomib-assumptions'
    def test_html_json_navigation(self):
        r=self.client.get(self.path);self.assertEqual(r.status_code,200);t=r.get_data(as_text=True)
        self.assertEqual(t.count('<svg '),2);self.assertIn('analyst-selected',t)
        self.assertEqual(t.count('class="nav-item active"'),1)
        self.assertEqual(r.headers['Cache-Control'],'no-store')
        self.assertEqual(len(self.client.get(self.path+'?format=json').json['scenarios']),3)
        self.assertIn(self.path,self.client.get('/landscape/simulation-lab/bortezomib-timecourse').get_data(as_text=True))
    def test_invalid_requests_and_fail_closed(self):
        for q in ['rate=1','patient_id=1','format=csv','format=json&format=html']:
            self.assertEqual(self.client.get(self.path+'?'+q).status_code,400)
        self.assertEqual(self.client.post(self.path).status_code,405)
        with patch('landscape_ui.bortezomib_assumption_pages.build_assumption_sensitivity',side_effect=ValueError()):
            self.assertEqual(self.client.get(self.path).status_code,503)
if __name__=='__main__':unittest.main()
